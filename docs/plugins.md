# Forge Plugin Guide

Write, distribute, and install Forge plugins.

## Plugin Structure

A Forge plugin is a Python module with a `register(app)` function:

```python
# my_plugin.py
def register(app):
    """Called when the plugin is loaded."""
    
    @app.command
    def plugin_hello() -> str:
        return "Hello from my plugin!"
    
    @app.command
    def plugin_status() -> dict:
        return {"name": "my-plugin", "version": "1.0.0", "active": True}

# Optional: Plugin manifest for capability enforcement
manifest = {
    "name": "my-plugin",
    "version": "1.0.0",
    "description": "A sample Forge plugin",
    "capabilities": ["clipboard", "notifications"],
    "forge_version": ">=2.0.0",
}
```

## Configuration

Register plugins in `forge.toml`:

```toml
[plugins]
enabled = true
modules = ["my_plugin", "forge_plugin_analytics"]
paths = ["plugins"]  # Also scan this directory for plugins
```

## Installing Plugins

### Via CLI

```bash
forge plugin-add forge-plugin-auth
```

This:
1. Installs the package via `pip install forge-plugin-auth`
2. Registers `forge_plugin_auth` in `forge.toml`

### Manually

```bash
pip install forge-plugin-auth
```

Then add to `forge.toml`:

```toml
[plugins]
modules = ["forge_plugin_auth"]
```

## Plugin Lifecycle

1. **Discovery** — Modules listed in `[plugins].modules` and `.py` files in `[plugins].paths`
2. **Validation** — Manifests checked for capability requirements and version compatibility
3. **Registration** — `register(app)` called with the ForgeApp instance
4. **Runtime** — Plugin commands available via IPC like any built-in command

## Using State in Plugins

Plugins can inject and consume managed state:

```python
class AnalyticsService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.events: list = []
    
    def track(self, event: str, data: dict):
        self.events.append({"event": event, "data": data, "ts": time.time()})

def register(app):
    # Register managed state
    service = AnalyticsService(api_key="ak_123")
    app.state.manage(service)
    
    @app.command
    def track_event(event: str, data: dict, analytics: AnalyticsService):
        # AnalyticsService is auto-injected by type hint!
        analytics.track(event, data)
        return {"tracked": True}
```

## Capability Enforcement

Plugin manifests declare required capabilities:

```python
manifest = {
    "capabilities": ["filesystem", "shell"]
}
```

At build time, `forge build` validates that all plugin capabilities are enabled
in `[permissions]`. Missing capabilities generate warnings in the build output.

## Publishing Plugins

Distribute as standard PyPI packages:

```bash
# Package structure
forge-plugin-auth/
├── pyproject.toml
├── forge_plugin_auth/
│   ├── __init__.py      # Contains register() and manifest
│   └── auth.py          # Implementation
└── README.md
```

Name convention: `forge-plugin-<name>` (PyPI) → `forge_plugin_<name>` (Python module)

## Plugin Contracts

Plugins can expose a contract for build-time validation:

```python
manifest = {
    "name": "forge-plugin-auth",
    "version": "2.1.0",
    "forge_version": ">=2.0.0",
    "capabilities": ["keychain"],
    "config_schema": {
        "auth.provider": {"type": "string", "required": True},
        "auth.redirect_url": {"type": "string", "required": False},
    }
}
```

The contract is recorded in `forge-plugins.json` during `forge build` for
release automation and compatibility tracking.
