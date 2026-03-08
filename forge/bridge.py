"""
Forge IPC Bridge (v2.0).

High-performance, security-hardened IPC bridge for communication between
the JavaScript frontend and the Python backend.

Features:
    - Command name validation (prevents injection attacks)
    - Error sanitization (strips paths, limits length)
    - Request size limits (DoS prevention)
    - Async command support (coroutines dispatched to event loop)
    - Thread pool dispatch for NoGIL parallel execution (Python 3.14+)

In free-threaded Python 3.14+, commands dispatched to the thread pool
run truly in parallel without GIL contention.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# ─── Constants ───
PROTOCOL_VERSION = "1.0"
SUPPORTED_PROTOCOL_VERSIONS = {"1", "1.0"}
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_COMMAND_NAME_LENGTH = 100
MAX_ERROR_MESSAGE_LENGTH = 500

# Valid command names: start with letter or underscore, then alphanumeric/underscore
_COMMAND_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class IPCBridge:
    """
    Security-hardened IPC bridge for Forge applications.

    Handles command registration, validation, dispatch, and response
    serialization. Supports both synchronous and async commands.

    Args:
        app: The ForgeApp instance (or mock for testing).
        commands: Optional dict of {name: callable} to pre-register.
        max_workers: Thread pool size for parallel command execution.

    In Python 3.14+ free-threaded mode, the thread pool executes commands
    truly in parallel across multiple CPU cores.
    """

    def __init__(
        self,
        app: Any = None,
        commands: Dict[str, Callable] | None = None,
        max_workers: int = 4,
    ) -> None:
        self._app = app
        self._commands: Dict[str, Callable] = {}
        self._command_capabilities: Dict[str, str | None] = {}
        self._command_versions: Dict[str, str] = {}
        self._command_internal: Dict[str, bool] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="forge-ipc",
        )

        self._register_internal_commands()

        # Register any pre-supplied commands
        if commands:
            for name, func in commands.items():
                self._commands[name] = func
                self._command_capabilities[name] = getattr(func, "_forge_capability", None)
                self._command_versions[name] = str(getattr(func, "_forge_version", PROTOCOL_VERSION))
                self._command_internal[name] = bool(getattr(func, "_forge_internal", False))

    def _register_internal_commands(self) -> None:
        """Register internal protocol introspection commands."""
        self.register_command(
            "__forge_describe_commands",
            self._describe_commands,
            version=PROTOCOL_VERSION,
            internal=True,
        )
        self.register_command(
            "__forge_protocol_info",
            self._protocol_info,
            version=PROTOCOL_VERSION,
            internal=True,
        )

    def _describe_commands(self) -> dict[str, Any]:
        """Return protocol and command registry metadata for introspection."""
        return {
            "protocol": PROTOCOL_VERSION,
            "commands": self.get_command_registry(),
        }

    def _protocol_info(self) -> dict[str, Any]:
        """Return protocol support information for the active bridge."""
        return {
            "current": PROTOCOL_VERSION,
            "supported": sorted(SUPPORTED_PROTOCOL_VERSIONS),
        }

    # ─── Command Registration ───

    def register_commands(self, api_instance: Any) -> None:
        """
        Register all public methods of an API instance as commands.

        Methods starting with '_' are skipped. Methods decorated with
        @command get their custom name if set.

        Args:
            api_instance: Object whose public methods become IPC commands.
        """
        api_capability = getattr(api_instance, "__forge_capability__", None)
        for name, method in inspect.getmembers(api_instance, predicate=inspect.ismethod):
            if not name.startswith("_"):
                cmd_name = getattr(method, "_forge_cmd", name)
                capability = getattr(method, "_forge_capability", api_capability)
                with self._lock:
                    self._commands[cmd_name] = method
                    self._command_capabilities[cmd_name] = capability
                    self._command_versions[cmd_name] = str(
                        getattr(method, "_forge_version", PROTOCOL_VERSION)
                    )
                    self._command_internal[cmd_name] = bool(
                        getattr(method, "_forge_internal", False)
                    )

    def register_command(
        self,
        name: str,
        func: Callable,
        capability: Optional[str] = None,
        version: Optional[str] = None,
        internal: bool = False,
    ) -> None:
        """
        Register a single callable as a named command.

        Args:
            name: The command name (must pass validation).
            func: The callable to execute when the command is invoked.

        Raises:
            ValueError: If the command name is invalid.
        """
        if not self._validate_command_name(name):
            raise ValueError(f"Invalid command name: {name!r}")
        with self._lock:
            self._commands[name] = func
            self._command_capabilities[name] = capability or getattr(
                func, "_forge_capability", None
            )
            self._command_versions[name] = str(version or getattr(func, "_forge_version", PROTOCOL_VERSION))
            self._command_internal[name] = bool(internal or getattr(func, "_forge_internal", False))

    def get_command_registry(self) -> list[dict[str, Any]]:
        """Return registered command metadata for protocol introspection."""
        with self._lock:
            return sorted(
                [
                    {
                        "name": name,
                        "capability": self._command_capabilities.get(name),
                        "version": self._command_versions.get(name, PROTOCOL_VERSION),
                        "internal": self._command_internal.get(name, False),
                        "allowed": self._is_command_allowed(
                            name,
                            internal=self._command_internal.get(name, False),
                        ),
                    }
                    for name in self._commands
                ],
                key=lambda item: item["name"],
            )

    def _command_policy(self) -> tuple[set[str], set[str], bool]:
        if self._app is None:
            return set(), set(), True

        config = getattr(self._app, "config", None)
        security = getattr(config, "security", None)
        if security is None:
            return set(), set(), True

        allow = {item for item in getattr(security, "allowed_commands", []) if isinstance(item, str)}
        deny = {item for item in getattr(security, "denied_commands", []) if isinstance(item, str)}
        expose = bool(getattr(security, "expose_command_introspection", True))
        return allow, deny, expose

    def _is_command_allowed(self, command_name: str, *, internal: bool = False) -> bool:
        allow, deny, expose = self._command_policy()
        if command_name in {"__forge_describe_commands", "__forge_protocol_info"} and not expose:
            return False
        if command_name in deny:
            return False
        if internal:
            return True
        if allow and command_name not in allow:
            return False
        return True

    def _is_capability_enabled(self, capability: str) -> bool:
        """Check whether a capability is enabled for the attached app."""
        if not capability:
            return True

        if self._app is None:
            return True

        checker = getattr(self._app, "has_capability", None)
        if callable(checker):
            return bool(checker(capability))

        config = getattr(self._app, "config", None)
        permissions = getattr(config, "permissions", None)
        if permissions is None:
            return True

        return bool(getattr(permissions, capability, False))

    def _is_origin_allowed(self, origin: str | None) -> bool:
        if not origin or self._app is None:
            return True

        checker = getattr(self._app, "is_origin_allowed", None)
        if callable(checker):
            return bool(checker(origin))
        return True

    def _is_window_capability_allowed(self, capability: str | None, window_label: str | None) -> bool:
        if not capability:
            return True

        if self._app is None:
            return True

        checker = getattr(self._app, "has_capability", None)
        if callable(checker):
            try:
                return bool(checker(capability, window_label=window_label))
            except TypeError:
                return bool(checker(capability))
        return self._is_capability_enabled(capability)

    # ─── Validation ───

    def _validate_command_name(self, name: Any) -> bool:
        """
        Validate that a command name is safe.

        Rules:
            - Must be a string
            - Must not be empty
            - Must start with a letter or underscore
            - Must contain only alphanumeric characters and underscores
            - Must not exceed MAX_COMMAND_NAME_LENGTH

        Args:
            name: The command name to validate.

        Returns:
            True if valid, False otherwise.
        """
        if not isinstance(name, str):
            return False
        if not name:
            return False
        if len(name) > MAX_COMMAND_NAME_LENGTH:
            return False
        return bool(_COMMAND_NAME_RE.match(name))

    # ─── Error Sanitization ───

    def _sanitize_error(self, exc: Exception) -> str:
        """
        Sanitize an error message for safe transmission to the frontend.

        Removes filesystem paths and limits message length to prevent
        information leakage.

        Args:
            exc: The exception to sanitize.

        Returns:
            A sanitized error string safe to send to the frontend.
        """
        msg = str(exc)

        # Remove common path prefixes (home dirs, cwd, etc.)
        for path in [os.getcwd(), os.path.expanduser("~"), "/home", "C:\\Users"]:
            if path:
                msg = msg.replace(path, "<redacted>")

        # Remove anything that looks like an absolute path
        msg = re.sub(r"(/[a-zA-Z0-9._\-]+){3,}", "<redacted>", msg)
        msg = re.sub(r"([A-Z]:\\[a-zA-Z0-9._\-\\]+)", "<redacted>", msg)

        # Truncate
        if len(msg) > MAX_ERROR_MESSAGE_LENGTH:
            msg = msg[:MAX_ERROR_MESSAGE_LENGTH] + "..."

        return msg

    # ─── Command Invocation ───

    def invoke_command(self, raw_message: str) -> str:
        """
        Parse, validate, and execute an IPC command from a raw JSON string.

        This is the main entry point called by the Rust IPC handler.
        Returns a JSON string response.

        Security checks performed:
            1. Request size limit
            2. JSON parse validation
            3. Required fields check ('command', 'id')
            4. Command name validation
            5. Args type validation (must be dict)
            6. Command existence check
            7. Error sanitization on failure

        Args:
            raw_message: The raw JSON string from the frontend.

        Returns:
            JSON string with {id, result} or {id, error}.
        """
        msg_id = None
        trace_requested = False
        command_name: Optional[str] = None
        start_time = time.perf_counter()

        try:
            # 1. Size check (DoS prevention)
            if len(raw_message) > MAX_REQUEST_SIZE:
                return self._error_response(None, "Request too large")

            # 2. Parse JSON
            try:
                data = json.loads(raw_message)
            except Exception:
                return self._error_response(None, "Invalid JSON")

            if not isinstance(data, dict):
                return self._error_response(None, "Request must be a JSON object")

            msg_id = data.get("id")
            trace_requested = bool(data.get("trace") or data.get("include_meta"))

            protocol = data.get("protocol") or data.get("protocolVersion")
            if protocol is not None and str(protocol) not in SUPPORTED_PROTOCOL_VERSIONS:
                return self._error_response(
                    msg_id,
                    f"Unsupported protocol version: {protocol!r}",
                    code="unsupported_protocol",
                    meta=self._build_trace_meta(start_time, trace_requested),
                )

            # 3. Required fields
            cmd_name = data.get("command") or data.get("cmd")
            command_name = cmd_name
            if not cmd_name:
                return self._error_response(
                    msg_id,
                    "Missing 'command' field",
                    code="missing_command",
                    meta=self._build_trace_meta(start_time, trace_requested),
                )

            # 4. Command name validation
            if not self._validate_command_name(cmd_name):
                return self._error_response(
                    msg_id,
                    f"Invalid command name: {cmd_name!r}",
                    code="invalid_command_name",
                    meta=self._build_trace_meta(start_time, trace_requested, command_name),
                )

            # 5. Args validation
            args = data.get("args", {})
            if not isinstance(args, dict):
                return self._error_response(
                    msg_id,
                    "Args must be a JSON object",
                    code="invalid_args",
                    meta=self._build_trace_meta(start_time, trace_requested, command_name),
                )

            meta = data.get("meta", {})
            if meta is None:
                meta = {}
            if not isinstance(meta, dict):
                return self._error_response(
                    msg_id,
                    "Meta must be a JSON object when provided",
                    code="invalid_meta",
                    meta=self._build_trace_meta(start_time, trace_requested, command_name),
                )
            origin = meta.get("origin") if isinstance(meta.get("origin"), str) else None
            window_label = meta.get("window_label") if isinstance(meta.get("window_label"), str) else None

            if not self._is_origin_allowed(origin):
                return self._error_response(
                    msg_id,
                    f"Origin not allowed by security policy: {origin!r}",
                    code="origin_not_allowed",
                    meta=self._build_trace_meta(start_time, trace_requested, command_name),
                )

            # 6. Command existence
            with self._lock:
                func = self._commands.get(cmd_name)
                capability = self._command_capabilities.get(cmd_name)
                internal = self._command_internal.get(cmd_name, False)

            if func is None:
                return self._error_response(
                    msg_id,
                    f"Unknown command: {cmd_name!r}",
                    code="unknown_command",
                    meta=self._build_trace_meta(start_time, trace_requested, command_name),
                )

            if not self._is_command_allowed(cmd_name, internal=internal):
                return self._error_response(
                    msg_id,
                    f"Command not allowed by security policy: {cmd_name!r}",
                    code="command_not_allowed",
                    meta=self._build_trace_meta(start_time, trace_requested, command_name, capability),
                )

            if capability and not self._is_capability_enabled(capability):
                return self._error_response(
                    msg_id,
                    f"Permission denied for command: {cmd_name!r} requires '{capability}'",
                    code="permission_denied",
                    meta=self._build_trace_meta(start_time, trace_requested, command_name, capability),
                )

            if not self._is_window_capability_allowed(capability, window_label):
                return self._error_response(
                    msg_id,
                    f"Window scope denied for command: {cmd_name!r} on window {window_label!r}",
                    code="window_scope_denied",
                    meta=self._build_trace_meta(start_time, trace_requested, command_name, capability),
                )

            # 7. Execute
            result = self._execute_command(func, args)
            return self._success_response(
                msg_id,
                result,
                meta=self._build_trace_meta(start_time, trace_requested, command_name, capability),
            )

        except Exception as exc:
            logger.exception("Unhandled error in IPC bridge")
            return self._error_response(
                msg_id,
                self._sanitize_error(exc),
                code="internal_error",
                meta=self._build_trace_meta(start_time, trace_requested, command_name),
            )

    def _build_trace_meta(
        self,
        start_time: float,
        include_meta: bool,
        command_name: Optional[str] = None,
        capability: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Build timing metadata for traced IPC responses."""
        if not include_meta:
            return None

        duration_ms = round((time.perf_counter() - start_time) * 1000, 3)
        meta: dict[str, Any] = {"duration_ms": duration_ms}
        if command_name is not None:
            meta["command"] = command_name
        if capability is not None:
            meta["capability"] = capability
        return meta

    def _execute_command(self, func: Callable, args: Dict[str, Any]) -> Any:
        """
        Execute a command, handling both sync and async callables.

        Args:
            func: The command callable.
            args: Keyword arguments to pass to the callable.

        Returns:
            The command's return value.
        """
        if inspect.iscoroutinefunction(func):
            # Run async command -- create a new loop if needed
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # Already in an async context -- schedule and return
                import concurrent.futures

                future = concurrent.futures.Future()

                async def _run():
                    try:
                        result = await func(**args)
                        future.set_result(result)
                    except Exception as e:
                        future.set_exception(e)

                asyncio.ensure_future(_run())
                return future.result(timeout=30)
            else:
                return asyncio.run(func(**args))
        else:
            return func(**args)

    def invoke_command_threaded(self, raw_message: str, callback: Callable[[str], None]) -> None:
        """
        Execute an IPC command asynchronously on the thread pool.

        In Python 3.14+ free-threaded mode, this enables true parallel
        command execution across multiple CPU cores.

        Args:
            raw_message: The raw JSON string from the frontend.
            callback: Function to call with the JSON response string.
        """

        def _run() -> None:
            result = self.invoke_command(raw_message)
            callback(result)

        self._executor.submit(_run)

    # ─── Response Serialization ───

    def _success_response(self, msg_id: Any, result: Any, meta: Optional[dict[str, Any]] = None) -> str:
        """Build a JSON success response."""
        return json.dumps(
            {
                "type": "reply",
                "protocol": PROTOCOL_VERSION,
                "id": msg_id,
                "result": result,
                "error": None,
                "error_code": None,
                "meta": meta,
            }
        )

    def _error_response(
        self,
        msg_id: Any,
        error: str,
        code: str = "invalid_request",
        meta: Optional[dict[str, Any]] = None,
    ) -> str:
        """Build a JSON error response."""
        return json.dumps(
            {
                "type": "reply",
                "protocol": PROTOCOL_VERSION,
                "id": msg_id,
                "result": None,
                "error": error,
                "error_code": code,
                "meta": meta,
            }
        )

    # ─── Cleanup ───

    def shutdown(self) -> None:
        """Shut down the thread pool executor."""
        self._executor.shutdown(wait=False)


def requires_capability(capability: str) -> Callable:
    """
    Decorator to declare that a command requires a named capability.

    Args:
        capability: Capability name from the Forge permission model.
    """

    def decorator(func: Callable) -> Callable:
        func._forge_capability = capability  # type: ignore[attr-defined]
        return func

    return decorator


def command(
    name: Optional[str] = None,
    capability: Optional[str] = None,
    version: str = PROTOCOL_VERSION,
) -> Callable:
    """
    Decorator to mark a method as a Forge IPC command.

    Can be used with or without arguments:
        @command()
        def my_handler(self): ...

        @command("custom_name")
        def my_handler(self): ...

    Args:
        name: Optional custom command name. If None, uses the function name.

    Returns:
        Decorated function with _forge_cmd attribute set.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._forge_cmd = name or func.__name__  # type: ignore[attr-defined]
        if capability is not None:
            wrapper._forge_capability = capability  # type: ignore[attr-defined]
        wrapper._forge_version = version  # type: ignore[attr-defined]
        return wrapper

    return decorator
