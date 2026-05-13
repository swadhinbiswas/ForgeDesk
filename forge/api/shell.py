from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from forge.bridge import command

if TYPE_CHECKING:
    from ..config import ShellPermissions

logger = logging.getLogger(__name__)


def _read_stream(stream: Any, callback: Any) -> None:
    for line in iter(stream.readline, ""):
        if line:
            callback(line)
    stream.close()


class ShellAPI:
    """
    Strict shell execution capability.

    Security:
        - Only allows executing commands that match the allowlist defined in config
        - ``deny_execute`` blocks specific commands even if globally allowed
        - ``shell.open()`` validates URLs against ``allow_urls``/``deny_urls``
    """

    __forge_capability__ = "shell"

    def __init__(
        self,
        app: Any,
        base_dir: Path,
        permissions: bool | ShellPermissions = False,
    ) -> None:
        from forge.scope import ScopeValidator

        self._app = app
        self._base_dir = base_dir
        self._permissions = permissions

        # Build URL scope validator for shell.open()
        if hasattr(permissions, "allow_urls"):
            self._url_scope = ScopeValidator(
                allow_patterns=getattr(permissions, "allow_urls", []),
                deny_patterns=getattr(permissions, "deny_urls", []),
            )
        else:
            self._url_scope = ScopeValidator()

    def _is_allowed(self, command: str) -> bool:
        if self._permissions is False:
            return False
        if self._permissions is True:
            # If globally allowed without strict lists
            return True

        # Check deny_execute first — deny always wins
        deny_list = getattr(self._permissions, "deny_execute", [])
        if command in deny_list:
            return False

        # It's a ShellPermissions object
        return command in self._permissions.execute

    def _is_sidecar_allowed(self, name: str) -> bool:
        if self._permissions is False:
            return False
        if self._permissions is True:
            return True
        return hasattr(self._permissions, "sidecars") and name in getattr(
            self._permissions, "sidecars", []
        )

    def _get_sidecar_path(self, name: str) -> Path:
        if not self._is_sidecar_allowed(name):
            raise PermissionError(
                f"Execution of sidecar '{name}' is not allowed by shell permissions policy."
            )

        ext = ".exe" if sys.platform == "win32" else ""
        sidecar_path = self._base_dir / "bin" / f"{name}{ext}"

        if not sidecar_path.exists():
            raise FileNotFoundError(f"Sidecar binary '{name}' not found at {sidecar_path}")

        return sidecar_path

    @command("shell_sidecar")
    def sidecar(self, name: str, args: list[str] | None = None) -> dict[str, Any]:
        """
        Execute a bundled sidecar binary securely and wait for it.
        """
        args = args or []
        sidecar_path = self._get_sidecar_path(name)

        cmd_list = [str(sidecar_path)] + args
        try:
            result = subprocess.run(cmd_list, capture_output=True, text=True, check=False)
            return {"stdout": result.stdout, "stderr": result.stderr, "code": result.returncode}
        except Exception as e:
            logger.error(f"Sidecar execution failed {cmd_list}: {e}")
            raise RuntimeError(f"Sidecar execution failed: {e}") from e

    @command("shell_execute")
    def execute(self, command_name: str, args: list[str] | None = None) -> dict[str, Any]:
        """
        Execute a native shell command securely according to the configured allowlist.
        """
        if not self._is_allowed(command_name):
            raise PermissionError(
                f"Execution of '{command_name}' is not allowed by shell permissions policy."
            )

        args = args or []
        cmd_list = [command_name] + args
        try:
            result = subprocess.run(cmd_list, capture_output=True, text=True, check=False)
            return {"stdout": result.stdout, "stderr": result.stderr, "code": result.returncode}
        except Exception as e:
            logger.error(f"Command execution failed {cmd_list}: {e}")
            raise RuntimeError(f"Command execution failed: {e}") from e

    def _spawn_process(self, cmd_list: list[str]) -> dict[str, Any]:
        """Internal helper to spawn a process and stream output to IPC events."""
        try:
            # We must use bufsize=1 and universal_newlines to read line by line
            process = subprocess.Popen(
                cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
            )
            pid = process.pid

            def emit_stdout(line: str) -> None:
                self._app.events.emit("shell:stdout", {"pid": pid, "data": line})

            def emit_stderr(line: str) -> None:
                self._app.events.emit("shell:stderr", {"pid": pid, "data": line})

            threading.Thread(
                target=_read_stream, args=(process.stdout, emit_stdout), daemon=True
            ).start()
            threading.Thread(
                target=_read_stream, args=(process.stderr, emit_stderr), daemon=True
            ).start()

            def wait_for_exit() -> None:
                process.wait()
                self._app.events.emit("shell:exit", {"pid": pid, "code": process.returncode})

            threading.Thread(target=wait_for_exit, daemon=True).start()

            return {"pid": pid}
        except Exception as e:
            logger.error(f"Failed to spawn process {cmd_list}: {e}")
            raise RuntimeError(f"Failed to spawn process: {e}") from e

    @command("shell_spawn")
    def spawn(self, command_name: str, args: list[str] | None = None) -> dict[str, Any]:
        """
        Spawn a native shell command securely and stream output line by line over IPC events.
        Events emitted: shell:stdout, shell:stderr, shell:exit (with `pid` in payload).
        """
        if not self._is_allowed(command_name):
            raise PermissionError(
                f"Execution of '{command_name}' is not allowed by shell permissions policy."
            )

        args = args or []
        return self._spawn_process([command_name] + args)

    @command("shell_sidecar_spawn")
    def sidecar_spawn(self, name: str, args: list[str] | None = None) -> dict[str, Any]:
        """
        Spawn a sidecar securely and stream output line by line over IPC events.
        Events emitted: shell:stdout, shell:stderr, shell:exit (with `pid` in payload).
        """
        sidecar_path = self._get_sidecar_path(name)
        args = args or []
        return self._spawn_process([str(sidecar_path)] + args)

    @command("shell_open")
    def open(self, path: str) -> None:
        """
        Open a URL or path with the default system application.

        Security:
            - Requires general shell permission access
            - URLs are validated against ``allow_urls``/``deny_urls`` scopes
            - Deny patterns always override allow patterns
        """
        if self._permissions is False:
            raise PermissionError("Shell access is disabled.")

        # Check URL scopes for http/https URLs
        if path.startswith("http://") or path.startswith("https://"):
            if not self._url_scope.is_url_allowed(path):
                raise PermissionError(
                    f"Opening URL '{path}' is not allowed by shell URL scope policy."
                )

        path = os.path.abspath(path) if not path.startswith("http") else path

        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            logger.error(f"Failed to open '{path}': {e}")
            raise RuntimeError(f"Failed to open '{path}': {e}") from e
