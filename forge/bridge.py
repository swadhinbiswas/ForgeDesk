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
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import get_type_hints, Any, Callable, Dict, Optional

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
        self._command_validators: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="forge-ipc",
        )

        # Rate limiter state
        self._rate_window: deque = deque()
        self._rate_lock = threading.Lock()

        # Circuit breaker for error recovery
        from forge.recovery import CircuitBreaker
        self._circuit_breaker = CircuitBreaker()

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
        self.register_command(
            "__forge_log",
            self._handle_log,
            version=PROTOCOL_VERSION,
            internal=True,
        )

    def _handle_log(
        self,
        level: str = "info",
        message: str = "",
        source: str = "frontend",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Forward a log entry from the frontend to the Python logger."""
        # Try to find a logger on the app instance
        logger = getattr(self._app, "_logger", None) if self._app else None
        if logger and hasattr(logger, "log"):
            entry = logger.log(level, message, source=source, context=context)
            return {"logged": True, "level": level, "source": source}
        return {"logged": False, "reason": "no_logger_configured"}

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

    def _generate_validator(self, func: Callable) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
        """
        Generate a strict arguments validator for an IPC command using type hints (Python 3.14).
        Creates a dynamic msgspec Struct for the function signature.
        """
        try:
            import msgspec
            sig = inspect.signature(func)
            hints = get_type_hints(func)
            
            field_definitions = []
            has_var_keyword = False
            for name, param in sig.parameters.items():
                if param.kind == inspect.Parameter.VAR_KEYWORD:
                    has_var_keyword = True
                    continue
                if param.kind == inspect.Parameter.VAR_POSITIONAL:
                    continue

                if name in ("self", "cls", "state"):
                    continue
                
                param_type = hints.get(name, Any)
                
                try:
                    from forge.state import AppState
                    if param_type is AppState:
                        continue
                except ImportError:
                    pass
                
                if getattr(self, "_app", None) and getattr(self._app, "state", None):
                    if getattr(self._app.state, "has", None) and self._app.state.has(param_type):
                        continue
                        
                if param.default is inspect.Parameter.empty:
                    field_definitions.append((name, param_type))
                else:
                    field_definitions.append((name, param_type, param.default))
            
            # create named model
            model = msgspec.defstruct(f"{func.__name__}_Args", field_definitions)
            
            def validator(kwargs: Dict[str, Any]) -> Dict[str, Any]:
                try:
                    res = msgspec.convert(kwargs, type=model)
                    valid = {f: getattr(res, f) for f in res.__struct_fields__}
                    if has_var_keyword:
                        for k, v in kwargs.items():
                            if k not in valid:
                                valid[k] = v
                    return valid
                except msgspec.ValidationError as e:
                    raise ValueError(f"Payload validation failed: {e}") from None
                    
            return validator
        except Exception as e:
            logger.warning(f"Could not generate strict validator for {func.__name__}: {e}")
            return lambda kwargs: kwargs  # fallback to no-op validation

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
                    self._command_validators[cmd_name] = self._generate_validator(method)

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
            self._command_validators[name] = self._generate_validator(func)

    def get_command_registry(self) -> list[dict[str, Any]]:
        """Return registered command metadata for protocol introspection."""
        import typing

        def _extract_schema(func: Callable) -> dict[str, Any]:
            try:
                sig = inspect.signature(func)
                hints = typing.get_type_hints(func)
            except Exception:
                return {"args": [], "return_type": "Any"}

            args_schema = []
            for name, param in sig.parameters.items():
                if name == "self":
                    continue
                hint = hints.get(name)
                args_schema.append({
                    "name": name,
                    "type": str(hint) if hint else "Any",
                    "optional": param.default is not inspect.Parameter.empty,
                })
            
            return {
                "args": args_schema,
                "return_type": str(hints.get("return")) if "return" in hints else "Any",
            }

        with self._lock:
            registry = []
            for name, func in self._commands.items():
                schema = _extract_schema(func)
                registry.append({
                    "name": name,
                    "capability": self._command_capabilities.get(name),
                    "version": self._command_versions.get(name, PROTOCOL_VERSION),
                    "internal": self._command_internal.get(name, False),
                    "allowed": self._is_command_allowed(
                        name,
                        internal=self._command_internal.get(name, False),
                    ),
                    "schema": schema,
                })
            return sorted(registry, key=lambda item: item["name"])

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
        strict = self._is_strict_mode()
        if command_name in {"__forge_describe_commands", "__forge_protocol_info"} and not expose:
            return False
        if command_name in deny:
            return False
        if internal:
            return True
        if allow and command_name not in allow:
            return False
        if strict and not allow:
            # Strict mode with no allow list: block all non-internal commands
            return False
        return True

    def _is_strict_mode(self) -> bool:
        """Check whether the security strict_mode is enabled."""
        if self._app is None:
            return False
        config = getattr(self._app, "config", None)
        if config is None:
            return False
        security = getattr(config, "security", None)
        if security is None:
            return False
        val = getattr(security, "strict_mode", False)
        return val is True

    def _get_rate_limit(self) -> int:
        """Get the configured IPC rate limit (calls/sec). 0 = unlimited."""
        if self._app is None:
            return 0
        config = getattr(self._app, "config", None)
        if config is None:
            return 0
        security = getattr(config, "security", None)
        if security is None:
            return 0
        val = getattr(security, "rate_limit", 0)
        return int(val) if isinstance(val, (int, float)) else 0

    def _check_rate_limit(self) -> bool:
        """Return True if the call is allowed under the rate limit."""
        limit = self._get_rate_limit()
        if limit <= 0:
            return True
        now = time.monotonic()
        with self._rate_lock:
            # Purge entries older than 1 second
            while self._rate_window and self._rate_window[0] <= now - 1.0:
                self._rate_window.popleft()
            if len(self._rate_window) >= limit:
                return False
            self._rate_window.append(now)
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
        inspect = os.environ.get("FORGE_INSPECT") == "1"
        if inspect:
            try:
                msg_data = json.loads(raw_message)
                cmd = msg_data.get('command') or msg_data.get('cmd') or 'unknown'
                print(f"\n\033[36m[IPC REQ]\033[0m \033[1m{cmd}\033[0m: {raw_message[:500]}")
            except Exception:
                print(f"\n\033[36m[IPC REQ]\033[0m \033[1munknown\033[0m: {raw_message[:500]}")
                
        result = self._invoke_command_internal(raw_message)
        
        if inspect:
            print(f"\033[32m[IPC RES]\033[0m {result[:500]}")
            
        return result

    def _invoke_command_internal(self, raw_message: str) -> str:
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
        correlation_id: Optional[str] = None
        start_time = time.perf_counter()

        try:
            # 1. Size check (DoS prevention)
            if len(raw_message) > MAX_REQUEST_SIZE:
                return self._error_response(None, "Request too large")

            # 1b. Rate limit check
            if not self._check_rate_limit():
                return self._error_response(
                    None,
                    "Rate limit exceeded",
                    code="rate_limit_exceeded",
                )

            # 2. Parse JSON
            try:
                data = json.loads(raw_message)
            except Exception:
                return self._error_response(None, "Invalid JSON")

            if not isinstance(data, dict):
                return self._error_response(None, "Request must be a JSON object")

            msg_id = data.get("id")
            correlation_id = data.get("correlation_id") or str(uuid.uuid4())
            trace_requested = bool(data.get("trace") or data.get("include_meta"))

            protocol = data.get("protocol") or data.get("protocolVersion")
            if protocol is not None and str(protocol) not in SUPPORTED_PROTOCOL_VERSIONS:
                return self._error_response(
                    msg_id,
                    f"Unsupported protocol version: {protocol!r}",
                    code="unsupported_protocol",
                    correlation_id=correlation_id,
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
                    correlation_id=correlation_id,
                    meta=self._build_trace_meta(start_time, trace_requested),
                )

            # 4. Command name validation
            if not self._validate_command_name(cmd_name):
                return self._error_response(
                    msg_id,
                    f"Invalid command name: {cmd_name!r}",
                    code="invalid_command_name",
                    correlation_id=correlation_id,
                    meta=self._build_trace_meta(start_time, trace_requested, command_name),
                )

            # 5. Args validation
            args = data.get("args", {})
            if not isinstance(args, dict):
                return self._error_response(
                    msg_id,
                    "Args must be a JSON object",
                    code="invalid_args",
                    correlation_id=correlation_id,
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
                    correlation_id=correlation_id,
                    meta=self._build_trace_meta(start_time, trace_requested, command_name),
                )
            origin = meta.get("origin") if isinstance(meta.get("origin"), str) else None
            window_label = meta.get("window_label") if isinstance(meta.get("window_label"), str) else None

            if not self._is_origin_allowed(origin):
                return self._error_response(
                    msg_id,
                    f"Origin not allowed by security policy: {origin!r}",
                    code="origin_not_allowed",
                    correlation_id=correlation_id,
                    meta=self._build_trace_meta(start_time, trace_requested, command_name),
                )

            # 6. Command existence
            with self._lock:
                func = self._commands.get(cmd_name)
                capability = self._command_capabilities.get(cmd_name)
                cmd_version = self._command_versions.get(cmd_name, PROTOCOL_VERSION)
                internal = self._command_internal.get(cmd_name, False)

            if func is None:
                return self._error_response(
                    msg_id,
                    f"Unknown command: {cmd_name!r}",
                    code="unknown_command",
                    correlation_id=correlation_id,
                    meta=self._build_trace_meta(start_time, trace_requested, command_name),
                )

            if not self._is_command_allowed(cmd_name, internal=internal):
                return self._error_response(
                    msg_id,
                    f"Command not allowed by security policy: {cmd_name!r}",
                    code="command_not_allowed",
                    correlation_id=correlation_id,
                    meta=self._build_trace_meta(start_time, trace_requested, command_name, capability, cmd_version),
                )

            if capability and not self._is_capability_enabled(capability):
                return self._error_response(
                    msg_id,
                    f"Permission denied for command: {cmd_name!r} requires '{capability}'",
                    code="permission_denied",
                    correlation_id=correlation_id,
                    meta=self._build_trace_meta(start_time, trace_requested, command_name, capability, cmd_version),
                )

            if not self._is_window_capability_allowed(capability, window_label):
                return self._error_response(
                    msg_id,
                    f"Window scope denied for command: {cmd_name!r} on window {window_label!r}",
                    code="window_scope_denied",
                    correlation_id=correlation_id,
                    meta=self._build_trace_meta(start_time, trace_requested, command_name, capability, cmd_version),
                )

            # 7. Circuit breaker check
            if not self._circuit_breaker.is_allowed(cmd_name):
                return self._error_response(
                    msg_id,
                    f"Command temporarily disabled due to repeated failures: {cmd_name!r}",
                    code="circuit_open",
                    correlation_id=correlation_id,
                    meta=self._build_trace_meta(start_time, trace_requested, command_name, capability, cmd_version),
                )

            # 8. Execute
            try:
                # Apply Strict Payload Validation (Pydantic 3.14 hints)
                validator = self._command_validators.get(cmd_name)
                if validator:
                    try:
                        args = validator(args)
                    except ValueError as val_err:
                        return self._error_response(
                            msg_id,
                            str(val_err),
                            code="validation_error",
                            correlation_id=correlation_id,
                            meta=self._build_trace_meta(start_time, trace_requested, command_name, capability, cmd_version),
                        )
                
                result = self._execute_command(func, args)
                self._circuit_breaker.record_success(cmd_name)
                return self._success_response(
                    msg_id,
                    result,
                    correlation_id=correlation_id,
                    meta=self._build_trace_meta(start_time, trace_requested, command_name, capability, cmd_version),
                )
            except Exception as cmd_exc:
                self._circuit_breaker.record_failure(cmd_name)
                raise cmd_exc

        except Exception as exc:
            logger.exception("Unhandled error in IPC bridge")
            return self._error_response(
                msg_id,
                self._sanitize_error(exc),
                code="internal_error",
                correlation_id=correlation_id,
                meta=self._build_trace_meta(start_time, trace_requested, command_name),
            )

    def _build_trace_meta(
        self,
        start_time: float,
        include_meta: bool,
        command_name: Optional[str] = None,
        capability: Optional[str] = None,
        command_version: Optional[str] = None,
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
        if command_version is not None:
            meta["command_version"] = command_version
        return meta

    def _execute_command(self, func: Callable, args: Dict[str, Any]) -> Any:
        """
        Execute a command, handling both sync and async callables.

        State injection:
            If a command has a parameter named 'state' (type-hinted as
            AppState), the app's state container is automatically injected.
            This mirrors Tauri's State<T> auto-injection pattern.

        Args:
            func: The command callable.
            args: Keyword arguments to pass to the callable.

        Returns:
            The command's return value.
        """
        # Auto-inject AppState if the command requests it
        args = self._inject_state(func, args)

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

    def _inject_state(self, func: Callable, args: Dict[str, Any]) -> Dict[str, Any]:
        """Inject managed state into command arguments based on type hints.

        Supports two injection modes:

        1. **Container injection**: A parameter named ``state`` (or typed as
           ``AppState``) receives the full state container.

        2. **Typed injection**: Any parameter whose type hint matches a type
           registered via ``app.state.manage(instance)`` receives that specific
           instance.  E.g. ``def handler(db: Database)`` automatically receives
           the managed ``Database`` instance.

        Typed injection is zero-cost for commands that don't use managed types
        — we only inspect signatures when the app has a state container.

        Args:
            func: The command callable.
            args: Keyword arguments from the IPC message.

        Returns:
            Possibly-augmented args dict.
        """
        if self._app is None:
            return args

        state_container = getattr(self._app, "state", None)
        if state_container is None:
            return args

        try:
            sig = inspect.signature(func)
        except (ValueError, TypeError):
            return args

        # Try to get type hints (may fail for builtins/C extensions)
        try:
            import typing
            hints = typing.get_type_hints(func)
        except Exception:
            hints = {}

        injected = dict(args)

        for param_name, param in sig.parameters.items():
            # Skip if already provided by the IPC caller
            if param_name in injected:
                continue

            # Mode 1: Named 'state' → inject the AppState container
            if param_name == "state":
                injected["state"] = state_container
                continue

            # Mode 2: Typed injection → look up the type hint in managed state
            hint = hints.get(param_name)
            if hint is None:
                continue

            # Check if the hint matches AppState itself
            from forge.state import AppState
            if hint is AppState:
                injected[param_name] = state_container
                continue

            # Check if the hint is a managed type
            if isinstance(hint, type) and state_container.try_get(hint) is not None:
                injected[param_name] = state_container.try_get(hint)

        return injected

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

    def _success_response(
        self,
        msg_id: Any,
        result: Any,
        correlation_id: Optional[str] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> str:
        """Build a JSON success response with correlation tracking."""
        return json.dumps(
            {
                "type": "reply",
                "protocol": PROTOCOL_VERSION,
                "id": msg_id,
                "correlation_id": correlation_id,
                "timestamp": time.time(),
                "result": result,
                "error": None,
                "error_code": None,
                "error_detail": None,
                "meta": meta,
            }
        )

    def _error_response(
        self,
        msg_id: Any,
        error: str,
        code: str = "invalid_request",
        correlation_id: Optional[str] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> str:
        """Build a JSON error response with structured error detail."""
        return json.dumps(
            {
                "type": "reply",
                "protocol": PROTOCOL_VERSION,
                "id": msg_id,
                "correlation_id": correlation_id,
                "timestamp": time.time(),
                "result": None,
                "error": error,
                "error_code": code,
                "error_detail": {
                    "code": code,
                    "message": error,
                    "source": "bridge",
                },
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
