"""
Forge Configuration Module.

This module handles loading, parsing, and validating the forge.toml configuration file.
It provides a strongly-typed configuration object for the rest of the framework.
"""

from __future__ import annotations

import os
import re
import sys
from urllib.parse import urlparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomllib


_PROTOCOL_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*$")
_COMMAND_POLICY_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@dataclass
class AppConfig:
    """Application metadata configuration."""

    name: str = "Forge App"
    version: str = "1.0.0"
    description: str = "A Forge desktop application"
    authors: list[str] = field(default_factory=list)
    main_html: str = "src/frontend/index.html"


@dataclass
class WindowConfig:
    """Window appearance and behavior configuration."""

    title: str = "Forge App"
    width: int = 1200
    height: int = 800
    resizable: bool = True
    fullscreen: bool = False
    min_width: int = 400
    min_height: int = 300
    decorations: bool = True
    always_on_top: bool = False
    transparent: bool = False
    vibrancy: str | None = None  # macOS/Windows native blur materials (e.g. 'mica', 'acrylic', 'sidebar', 'hud')
    remember_state: bool = True  # Persist window position/size/maximized across restarts


@dataclass
class BuildConfig:
    """Build and bundling configuration."""

    entry: str = "src/main.py"
    icon: str | None = None
    output_dir: str = "dist"
    single_binary: bool = True


@dataclass
class ProtocolConfig:
    """Deep link / custom protocol handler configuration."""

    schemes: list[str] = field(default_factory=list)


@dataclass
class PackagingConfig:
    """Packaging metadata for desktop bundle generation."""

    app_id: str | None = None
    product_name: str | None = None
    formats: list[str] = field(default_factory=lambda: ["dir"])
    category: str | None = None


@dataclass
class SigningConfig:
    """Signing and release-hardening metadata."""

    enabled: bool = False
    adapter: str | None = None
    identity: str | None = None
    sign_command: str | None = None
    verify_command: str | None = None
    notarize: bool = False
    notarize_command: str | None = None
    timestamp_url: str | None = None


@dataclass
class ServerConfig:
    """Web server configuration for Forge web application mode.

    Forge v2.0 supports running as a standalone web application server
    in addition to native desktop mode. This config drives `forge serve`.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    workers: int = 4
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    static_dir: str | None = None
    auto_reload: bool = False
    ssl_cert: str | None = None
    ssl_key: str | None = None
    log_level: str = "info"


@dataclass
class DatabaseConfig:
    """Optional database configuration for Forge web apps."""

    url: str | None = None
    pool_size: int = 5
    echo: bool = False


@dataclass
class RoutesConfig:
    """Routing configuration for Forge web apps.

    Defines where the application discovers route handlers and
    which API prefix is used.
    """

    module: str = "src.routes"
    api_prefix: str = "/api"


@dataclass
class DevConfig:
    """Development mode configuration."""

    frontend_dir: str = "src/frontend"
    hot_reload: bool = True
    port: int = 5173
    dev_server_command: str | None = None
    dev_server_url: str | None = None
    dev_server_cwd: str | None = None
    dev_server_timeout: int = 20


@dataclass
class FileSystemPermissions:
    """Strict File System scopes.

    Paths support glob patterns (fnmatch) and environment variables:
        - ``$APPDATA/myapp/**`` — matches platform-specific app data
        - ``~/Documents/**``    — matches user documents
        - ``./data/**``         — matches relative to project root

    Deny patterns always override allow patterns.
    """
    read: list[str] = field(default_factory=list)
    write: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)

@dataclass
class ShellPermissions:
    """Strict Shell execution scopes.

    ``execute`` lists the exact command names that may be spawned.
    ``deny_execute`` blocks specific commands even if globally allowed.
    ``allow_urls`` restricts ``shell.open()`` to matching URL patterns.
    ``deny_urls`` blocks specific URL patterns from being opened.
    """
    execute: list[str] = field(default_factory=list)
    deny_execute: list[str] = field(default_factory=list)
    sidecars: list[str] = field(default_factory=list)
    allow_urls: list[str] = field(default_factory=list)
    deny_urls: list[str] = field(default_factory=list)

@dataclass
class PermissionsConfig:
    """API permissions configuration."""

    filesystem: bool | FileSystemPermissions = True
    shell: bool | ShellPermissions = False
    clipboard: bool = True
    dialogs: bool = True
    notifications: bool = True
    system_tray: bool = False
    global_shortcut: bool = False
    updater: bool = False
    keychain: bool = False
    screen: bool = True
    lifecycle: bool = True
    deep_link: bool = True
    os_integration: bool = True
    autostart: bool = True
    power: bool = True
    printing: bool = True
    window_state: bool = True
    drag_drop: bool = True


@dataclass
class SecurityConfig:
    """Runtime IPC exposure policy and command allow/deny controls."""

    allowed_commands: list[str] = field(default_factory=list)
    denied_commands: list[str] = field(default_factory=list)
    expose_command_introspection: bool = True
    allowed_origins: list[str] = field(default_factory=list)
    window_scopes: dict[str, list[str]] = field(default_factory=dict)
    strict_mode: bool = False
    rate_limit: int = 0  # Max IPC calls per second, 0 = unlimited


@dataclass
class PluginsConfig:
    """Plugin discovery and loading configuration."""

    enabled: bool = False
    modules: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)


@dataclass
class UpdaterConfig:
    """Updater configuration for release manifest checking."""

    enabled: bool = False
    endpoint: str | None = None
    channel: str = "stable"
    check_on_startup: bool = False
    allow_downgrade: bool = False
    public_key: str | None = None
    require_signature: bool = True
    staging_dir: str = ".forge-updater"
    install_dir: str | None = None
    preflight_check: bool = True


@dataclass
class ForgeConfig:
    """
    Main configuration container for a Forge application.

    This class holds all configuration sections parsed from forge.toml.
    """

    app: AppConfig = field(default_factory=AppConfig)
    window: WindowConfig = field(default_factory=WindowConfig)
    build: BuildConfig = field(default_factory=BuildConfig)
    protocol: ProtocolConfig = field(default_factory=ProtocolConfig)
    packaging: PackagingConfig = field(default_factory=PackagingConfig)
    signing: SigningConfig = field(default_factory=SigningConfig)
    dev: DevConfig = field(default_factory=DevConfig)
    permissions: PermissionsConfig = field(default_factory=PermissionsConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    plugins: PluginsConfig = field(default_factory=PluginsConfig)
    updater: UpdaterConfig = field(default_factory=UpdaterConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    routes: RoutesConfig = field(default_factory=RoutesConfig)

    # Path to the loaded config file
    config_path: Path | None = None

    @classmethod
    def from_file(cls, path: str | Path) -> ForgeConfig:
        """
        Load and parse a forge.toml configuration file.

        Args:
            path: Path to the forge.toml file.

        Returns:
            A fully populated ForgeConfig instance.

        Raises:
            FileNotFoundError: If the config file doesn't exist.
            ConfigValidationError: If the config contains invalid values.
        """
        config_path = Path(path).resolve()

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        return cls._from_dict(data, config_path)

    @classmethod
    def _from_dict(cls, data: dict[str, Any], config_path: Path) -> ForgeConfig:
        """
        Create a ForgeConfig from a dictionary (parsed TOML).

        Args:
            data: Dictionary containing the parsed TOML data.
            config_path: Path to the config file for reference.

        Returns:
            A validated ForgeConfig instance.

        Raises:
            ConfigValidationError: If validation fails.
        """
        config = cls(config_path=config_path)

        # Parse [app] section
        if "app" in data:
            app_data = data["app"]
            config.app = AppConfig(
                name=app_data.get("name", "Forge App"),
                version=app_data.get("version", "1.0.0"),
                description=app_data.get("description", "A Forge desktop application"),
                authors=app_data.get("authors", []),
                main_html=app_data.get("main_html", "src/frontend/index.html"),
            )

        # Parse [window] section
        if "window" in data:
            window_data = data["window"]
            config.window = WindowConfig(
                title=window_data.get("title", "Forge App"),
                width=_validate_int(window_data.get("width", 1200), "window.width", 100, 10000),
                height=_validate_int(window_data.get("height", 800), "window.height", 100, 10000),
                resizable=window_data.get("resizable", True),
                fullscreen=window_data.get("fullscreen", False),
                min_width=_validate_int(
                    window_data.get("min_width", 400), "window.min_width", 100, 10000
                ),
                min_height=_validate_int(
                    window_data.get("min_height", 300), "window.min_height", 100, 10000
                ),
                decorations=window_data.get("decorations", True),
                always_on_top=window_data.get("always_on_top", False),
                transparent=window_data.get("transparent", False),
                vibrancy=window_data.get("vibrancy", None),
                remember_state=window_data.get("remember_state", True),
            )

        # Parse [build] section
        if "build" in data:
            build_data = data["build"]
            config.build = BuildConfig(
                entry=build_data.get("entry", "src/main.py"),
                icon=build_data.get("icon"),
                output_dir=build_data.get("output_dir", "dist"),
                single_binary=build_data.get("single_binary", True),
            )

        if "protocol" in data:
            protocol_data = data["protocol"]
            config.protocol = ProtocolConfig(
                schemes=list(protocol_data.get("schemes", [])),
            )

        if "packaging" in data:
            packaging_data = data["packaging"]
            config.packaging = PackagingConfig(
                app_id=packaging_data.get("app_id"),
                product_name=packaging_data.get("product_name"),
                formats=list(packaging_data.get("formats", ["dir"])),
                category=packaging_data.get("category"),
            )

        if "signing" in data:
            signing_data = data["signing"]
            config.signing = SigningConfig(
                enabled=signing_data.get("enabled", False),
                adapter=signing_data.get("adapter"),
                identity=signing_data.get("identity"),
                sign_command=signing_data.get("sign_command"),
                verify_command=signing_data.get("verify_command"),
                notarize=signing_data.get("notarize", False),
                notarize_command=signing_data.get("notarize_command"),
                timestamp_url=signing_data.get("timestamp_url"),
            )

        # Parse [dev] section
        if "dev" in data:
            dev_data = data["dev"]
            config.dev = DevConfig(
                frontend_dir=dev_data.get("frontend_dir", "src/frontend"),
                hot_reload=dev_data.get("hot_reload", True),
                port=_validate_int(dev_data.get("port", 5173), "dev.port", 1024, 65535),
                dev_server_command=dev_data.get("dev_server_command"),
                dev_server_url=dev_data.get("dev_server_url"),
                dev_server_cwd=dev_data.get("dev_server_cwd"),
                dev_server_timeout=_validate_int(
                    dev_data.get("dev_server_timeout", 20), "dev.dev_server_timeout", 1, 600
                ),
            )

        # Parse [permissions] section
        if "permissions" in data:
            perm_data = data["permissions"]
            
            fs_val = perm_data.get("filesystem", True)
            if isinstance(fs_val, dict):
                fs_perm = FileSystemPermissions(
                    read=list(fs_val.get("read", [])),
                    write=list(fs_val.get("write", [])),
                    deny=list(fs_val.get("deny", [])),
                )
            else:
                fs_perm = bool(fs_val)

            shell_val = perm_data.get("shell", False)
            if isinstance(shell_val, dict):
                shell_perm = ShellPermissions(
                    execute=list(shell_val.get("execute", [])),
                    deny_execute=list(shell_val.get("deny_execute", [])),
                    sidecars=list(shell_val.get("sidecars", [])),
                    allow_urls=list(shell_val.get("allow_urls", [])),
                    deny_urls=list(shell_val.get("deny_urls", [])),
                )
            else:
                shell_perm = bool(shell_val)

            config.permissions = PermissionsConfig(
                filesystem=fs_perm,
                shell=shell_perm,
                clipboard=perm_data.get("clipboard", True),
                dialogs=perm_data.get("dialogs", True),
                notifications=perm_data.get("notifications", True),
                system_tray=perm_data.get("system_tray", False),
                global_shortcut=perm_data.get("global_shortcut", False),
                updater=perm_data.get("updater", False),
                keychain=perm_data.get("keychain", False),
                screen=perm_data.get("screen", True),
                lifecycle=perm_data.get("lifecycle", True),
                deep_link=perm_data.get("deep_link", True),
                os_integration=perm_data.get("os_integration", True),
                autostart=perm_data.get("autostart", True),
                power=perm_data.get("power", True),
                printing=perm_data.get("printing", True),
                window_state=perm_data.get("window_state", True),
                drag_drop=perm_data.get("drag_drop", True),
            )

        if "security" in data:
            security_data = data["security"]
            config.security = SecurityConfig(
                allowed_commands=list(security_data.get("allowed_commands", [])),
                denied_commands=list(security_data.get("denied_commands", [])),
                expose_command_introspection=security_data.get("expose_command_introspection", True),
                allowed_origins=list(security_data.get("allowed_origins", [])),
                window_scopes={
                    str(key): list(value)
                    for key, value in security_data.get("window_scopes", {}).items()
                },
                strict_mode=bool(security_data.get("strict_mode", False)),
                rate_limit=int(security_data.get("rate_limit", 0)),
            )

        if "plugins" in data:
            plugin_data = data["plugins"]
            config.plugins = PluginsConfig(
                enabled=plugin_data.get("enabled", False),
                modules=list(plugin_data.get("modules", [])),
                paths=list(plugin_data.get("paths", [])),
            )

        if "updater" in data:
            updater_data = data["updater"]
            config.updater = UpdaterConfig(
                enabled=updater_data.get("enabled", False),
                endpoint=updater_data.get("endpoint"),
                channel=updater_data.get("channel", "stable"),
                check_on_startup=updater_data.get("check_on_startup", False),
                allow_downgrade=updater_data.get("allow_downgrade", False),
                public_key=updater_data.get("public_key"),
                require_signature=updater_data.get("require_signature", True),
                staging_dir=updater_data.get("staging_dir", ".forge-updater"),
                install_dir=updater_data.get("install_dir"),
            )

        # Parse [server] section
        if "server" in data:
            srv_data = data["server"]
            config.server = ServerConfig(
                host=srv_data.get("host", "127.0.0.1"),
                port=_validate_int(srv_data.get("port", 8000), "server.port", 1, 65535),
                workers=_validate_int(srv_data.get("workers", 4), "server.workers", 1, 64),
                cors_origins=srv_data.get("cors_origins", ["*"]),
                static_dir=srv_data.get("static_dir"),
                auto_reload=srv_data.get("auto_reload", False),
                ssl_cert=srv_data.get("ssl_cert"),
                ssl_key=srv_data.get("ssl_key"),
                log_level=srv_data.get("log_level", "info"),
            )

        # Parse [database] section
        if "database" in data:
            db_data = data["database"]
            config.database = DatabaseConfig(
                url=db_data.get("url"),
                pool_size=_validate_int(db_data.get("pool_size", 5), "database.pool_size", 1, 100),
                echo=db_data.get("echo", False),
            )

        # Parse [routes] section
        if "routes" in data:
            rt_data = data["routes"]
            config.routes = RoutesConfig(
                module=rt_data.get("module", "src.routes"),
                api_prefix=rt_data.get("api_prefix", "/api"),
            )

        # Validate the complete config
        _validate_config(config)

        return config

    @classmethod
    def find_and_load(cls, start_path: str | Path | None = None) -> ForgeConfig:
        """
        Find and load forge.toml by searching up the directory tree.

        Args:
            start_path: Starting directory for the search. Defaults to current working directory.

        Returns:
            A loaded ForgeConfig instance.

        Raises:
            FileNotFoundError: If no forge.toml is found.
        """
        if start_path is None:
            import __main__
            if hasattr(sys, "frozen") or hasattr(__main__, "__compiled__"):
                start_path = Path(__main__.__file__).parent.resolve()
            else:
                start_path = Path.cwd()
        else:
            start_path = Path(start_path).resolve()

        current = start_path
        while current != current.parent:
            config_file = current / "forge.toml"
            if config_file.exists():
                return cls.from_file(config_file)
            current = current.parent

        raise FileNotFoundError(f"No forge.toml found in {start_path} or any parent directory")

    def get_base_dir(self) -> Path:
        """
        Get the base directory containing the config file.

        Returns:
            Absolute path to the directory containing forge.toml.
        """
        if self.config_path is None:
            return Path.cwd()
        return self.config_path.parent

    def get_entry_path(self) -> Path:
        """
        Get the absolute path to the Python entry point.

        Returns:
            Absolute path to the main.py file.
        """
        base = self.get_base_dir()
        return base / self.build.entry

    def get_frontend_path(self) -> Path:
        """
        Get the absolute path to the frontend directory.

        Returns:
            Absolute path to the frontend directory.
        """
        base = self.get_base_dir()
        return base / self.dev.frontend_dir

    def get_output_path(self) -> Path:
        """
        Get the absolute path to the output directory.

        Returns:
            Absolute path to the dist/build output directory.
        """
        base = self.get_base_dir()
        return base / self.build.output_dir


def _validate_int(value: Any, field_name: str, min_val: int, max_val: int) -> int:
    """
    Validate that a value is an integer within a specified range.

    Args:
        value: The value to validate.
        field_name: Name of the field for error messages.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.

    Returns:
        The validated integer value.

    Raises:
        ConfigValidationError: If the value is invalid.
    """
    if not isinstance(value, int):
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ConfigValidationError(
                f"{field_name} must be an integer, got {type(value).__name__}"
            )

    if value < min_val or value > max_val:
        raise ConfigValidationError(
            f"{field_name} must be between {min_val} and {max_val}, got {value}"
        )

    return value


def _validate_config(config: ForgeConfig) -> None:
    """
    Perform cross-field validation on the complete config.

    Args:
        config: The ForgeConfig to validate.

    Raises:
        ConfigValidationError: If validation fails.
    """
    # Window dimensions must be consistent
    if config.window.min_width > config.window.width:
        raise ConfigValidationError(
            f"window.min_width ({config.window.min_width}) cannot be greater than "
            f"window.width ({config.window.width})"
        )

    if config.window.min_height > config.window.height:
        raise ConfigValidationError(
            f"window.min_height ({config.window.min_height}) cannot be greater than "
            f"window.height ({config.window.height})"
        )

    if config.updater.channel not in {"stable", "beta", "nightly"}:
        raise ConfigValidationError(
            f"updater.channel must be one of stable, beta, nightly, got {config.updater.channel!r}"
        )

    if config.dev.dev_server_url is not None:
        parsed = urlparse(config.dev.dev_server_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigValidationError(
                "dev.dev_server_url must be a valid http(s) URL when provided"
            )

    if not config.updater.staging_dir:
        raise ConfigValidationError("updater.staging_dir cannot be empty")

    reserved_schemes = {"http", "https", "file", "ftp", "ws", "wss"}
    for scheme in config.protocol.schemes:
        if not isinstance(scheme, str) or not scheme:
            raise ConfigValidationError("protocol.schemes entries must be non-empty strings")
        if not _PROTOCOL_SCHEME_RE.match(scheme):
            raise ConfigValidationError(
                f"protocol.schemes contains invalid scheme {scheme!r}; use lowercase RFC 3986 names"
            )
        if scheme in reserved_schemes:
            raise ConfigValidationError(
                f"protocol.schemes cannot use reserved scheme {scheme!r}"
            )

    if not config.packaging.formats or not all(
        isinstance(item, str) and item for item in config.packaging.formats
    ):
        raise ConfigValidationError("packaging.formats must contain at least one non-empty string")

    if config.signing.notarize and not config.signing.enabled:
        raise ConfigValidationError("signing.notarize requires signing.enabled = true")

    if config.signing.adapter is not None and config.signing.adapter not in {
        "auto",
        "custom",
        "gpg",
        "codesign",
        "signtool",
    }:
        raise ConfigValidationError(
            "signing.adapter must be one of auto, custom, gpg, codesign, signtool"
        )

    if config.signing.timestamp_url is not None:
        parsed = urlparse(config.signing.timestamp_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigValidationError(
                "signing.timestamp_url must be a valid http(s) URL when provided"
            )

    for field_name, values in {
        "security.allowed_commands": config.security.allowed_commands,
        "security.denied_commands": config.security.denied_commands,
    }.items():
        if not isinstance(values, list):
            raise ConfigValidationError(f"{field_name} must be a list of command names")
        for command_name in values:
            if not isinstance(command_name, str) or not _COMMAND_POLICY_NAME_RE.match(command_name):
                raise ConfigValidationError(
                    f"{field_name} contains invalid command name {command_name!r}"
                )

    overlap = set(config.security.allowed_commands) & set(config.security.denied_commands)
    if overlap:
        raise ConfigValidationError(
            "security.allowed_commands and security.denied_commands cannot overlap"
        )

    if not isinstance(config.security.allowed_origins, list):
        raise ConfigValidationError("security.allowed_origins must be a list of origins")
    for origin in config.security.allowed_origins:
        if not isinstance(origin, str) or not origin.strip():
            raise ConfigValidationError("security.allowed_origins entries must be non-empty strings")
        origin = origin.strip()
        if origin.startswith("forge://"):
            continue
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigValidationError(
                f"security.allowed_origins contains invalid origin {origin!r}"
            )

    allowed_scope_values = {
        "filesystem",
        "shell",
        "clipboard",
        "dialogs",
        "notifications",
        "system_tray",
        "global_shortcut",
        "updater",
        "system",
        "all",
        "*",
    }
    if not isinstance(config.security.window_scopes, dict):
        raise ConfigValidationError("security.window_scopes must be a table mapping labels to capability lists")
    for label, scopes in config.security.window_scopes.items():
        if not isinstance(label, str) or not label.strip():
            raise ConfigValidationError("security.window_scopes labels must be non-empty strings")
        if not isinstance(scopes, list):
            raise ConfigValidationError(
                f"security.window_scopes.{label} must be a list of capability names"
            )
        for capability in scopes:
            if not isinstance(capability, str) or capability not in allowed_scope_values:
                raise ConfigValidationError(
                    f"security.window_scopes.{label} contains invalid capability {capability!r}"
                )

    if not isinstance(config.plugins.modules, list) or not isinstance(config.plugins.paths, list):
        raise ConfigValidationError("plugins.modules and plugins.paths must be lists when provided")

    for module_name in config.plugins.modules:
        if not isinstance(module_name, str) or not module_name.strip():
            raise ConfigValidationError("plugins.modules entries must be non-empty strings")

    for plugin_path in config.plugins.paths:
        if not isinstance(plugin_path, str) or not plugin_path.strip():
            raise ConfigValidationError("plugins.paths entries must be non-empty strings")

    # Validate entry point exists (relative to config location)
    if config.config_path is not None:
        entry_path = config.get_entry_path()
        if not entry_path.exists():
            # Don't fail here - the file might be created later
            pass  # We'll validate this at runtime instead


def load_config(path: str | Path | None = None) -> ForgeConfig:
    """
    Convenience function to find and load a forge.toml configuration.

    Args:
        path: Optional path to search for forge.toml.

    Returns:
        A loaded ForgeConfig instance.
    """
    if path and Path(path).is_file():
        return ForgeConfig.from_file(path)
    return ForgeConfig.find_and_load(path)


class ConfigValidationError(Exception):
    """Exception raised when forge.toml validation fails."""

    pass
