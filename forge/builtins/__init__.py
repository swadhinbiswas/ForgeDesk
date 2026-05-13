"""Built-in extension IPC modules (database, auth, crypto, fs_tools, i18n, archive, etc.).

Enable in ``forge.toml``::

    [permissions]
    forge_extensions = true

    [builtin_plugins]
    database = true
    crypto = true
    compression = true
    # ... per subsystem (see :class:`forge.config.BuiltinPluginsConfig`)

Serial hardware uses ``permissions.serial = true`` (separate capability).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forge.app import ForgeApp


def setup_builtin_plugins(app: ForgeApp) -> None:
    """Register IPC commands for enabled built-in extensions."""
    from forge.builtins.registry import register_builtin_plugins

    register_builtin_plugins(app)
