# ⚡ Forge Framework

**Forge the future. Ship with Python.**

Build lightweight, cross-platform desktop applications using Python as the backend and any web technology (HTML/CSS/JS, React, Vue, Svelte) as the frontend — connected via a seamless IPC bridge.

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![Python](https://img.shields.io/badge/python-3.14%2B%20(NoGIL)-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

## ✨ Features

- **Native OS WebView** — Uses WKWebView (macOS), WebView2 (Windows), WebKitGTK (Linux) — NO Chromium bundling
- **Tiny App Size** — Final binaries under 20MB for basic apps
- **Simple IPC Bridge** — Call Python functions from JavaScript seamlessly
- **Typed State Injection** — `def handler(db: Database)` auto-receives managed instances (Tauri DX)
- **Deny-First Security** — Scoped filesystem/shell/URL permissions with glob patterns
- **Circuit Breaker** — Auto-disables commands that fail repeatedly, prevents cascading failures
- **Crash Reports** — Structured JSON crash reports with system context for post-mortem analysis
- **Beautiful CLI** — Scaffold, develop, build, doctor, and plugin management
- **Hot Reload** — Watch for file changes during development, auto-restart on config changes
- **Multiple Frontends** — Plain HTML, React, Vue, or Svelte templates
- **NoGIL Ready** — Designed for Python 3.14+ free-threaded mode with thread-safe primitives

## 🚀 Quick Start

### Installation

```bash
pip install forge-framework
```

Or install the Node-facing packages:

```bash
npm install @forgedesk/api
npm install -D @forgedesk/cli
npm install -D @forgedesk/vite-plugin vite
npm create forge-app@latest my-app
```

The npm wrappers bootstrap the Python runtime by delegating to `forge-framework`.

### Create a New Project

```bash
# Create a new project with the plain template
forge create my-app --template plain

# Or use React, Vue, or Svelte
forge create my-app --template react
forge create my-app --template vue
forge create my-app --template svelte
```

Or scaffold from npm:

```bash
npm create forge-app@latest my-app -- --template react
```

If your npm is pointed to a mirror that has not synced the latest package yet, use:

```bash
npx --registry=https://registry.npmjs.org @forgedesk/create-forge-app@latest my-app -- --template react
```

Generated projects retain template contract metadata in `forge.toml` so CLI diagnostics can detect incompatible or stale template outputs.

### Security Policy

Forge now supports basic IPC command policy controls in `forge.toml`:

```toml
[security]
allowed_commands = ["greet", "version", "plugin_hello"]
denied_commands = ["delete"]
expose_command_introspection = false
allowed_origins = ["https://app.example.com"]

[security.window_scopes]
main = ["filesystem", "dialogs"]
settings = ["clipboard"]
```

This allows production apps to reduce exposed backend surface area instead of shipping every registered command to every frontend. Forge now also forwards frontend origin and window label metadata on every IPC call, so the bridge can reject untrusted origins and enforce per-window capability scopes.

### Plugin Foundation

Forge now includes a Python plugin loading foundation:

```toml
[plugins]
enabled = true
modules = ["my_app_plugins.analytics"]
paths = ["plugins"]
```

Each plugin can expose a `register(app)` function and optional `manifest` metadata.

Desktop package outputs now also emit `forge-plugins.json`, which records discovered plugin manifests and version compatibility checks for release automation.

## 📦 Package Distribution

Forge now includes first-party package scaffolding for dual ecosystem distribution:

- [packages/api/README.md](packages/api/README.md) — `@forgedesk/api` typed JS bindings
- [packages/cli/README.md](packages/cli/README.md) — `@forgedesk/cli` Node wrapper around the Python CLI
- [packages/vite-plugin/README.md](packages/vite-plugin/README.md) — `@forgedesk/vite-plugin` frontend integration for Vite
- [packages/create-forge-app/README.md](packages/create-forge-app/README.md) — `@forgedesk/create-forge-app` npm scaffolder

This is the first step toward a Tauri-style install flow where frontend teams can start with npm while backend/runtime users can keep using pip.

Forge can now be prepared for publication to both registries:

- PyPI package: `forge-framework`
- npm packages: `@forgedesk/api`, `@forgedesk/cli`, `@forgedesk/vite-plugin`, and `@forgedesk/create-forge-app`

Release quality is enforced in CI with version-alignment checks, release-branch gating, release-manifest verification, and installer smoke tests before publishing.

Release automation is defined in:

- [.github/workflows/publish-python.yml](.github/workflows/publish-python.yml)
- [.github/workflows/publish-npm.yml](.github/workflows/publish-npm.yml)
- [.github/workflows/release-matrix.yml](.github/workflows/release-matrix.yml)
- [.github/workflows/signing-validation.yml](.github/workflows/signing-validation.yml)
- [RELEASE.md](RELEASE.md)

### Development

```bash
cd my-app
forge dev
```

Notes:
- `forge dev` now launches the app in a managed subprocess.
- With hot reload enabled, Forge watches project files and restarts the Python app when backend or frontend source files change.
- If `[dev].dev_server_command` and `[dev].dev_server_url` are configured, Forge starts the frontend dev server, waits for it to become ready, and points the native runtime at that URL.
- Use `forge dev --no-watch` to disable restart-on-change behavior.

### Build

```bash
forge build
```

### Environment Validation

```bash
forge doctor
forge doctor --output json
```

Package metadata and installer descriptors without a release manifest:

```bash
forge package --result-format json
```

Run signing and verification against an existing `forge-package.json`:

```bash
forge sign --result-format json
```

For CI or release automation, use machine-readable build results:

```bash
forge build --result-format json
```

To generate a release manifest with artifact digests for pipelines:

```bash
forge release --result-format json
```

Use `forge doctor --output json` before publishing to validate environment readiness, version alignment, and project health.

## 📖 Documentation

### Project Structure

```
my-app/
├── forge.toml          # App configuration
├── src/
│   ├── main.py         # Python backend
│   └── frontend/       # Web frontend
│       ├── index.html
│       ├── main.js
│       └── style.css
├── assets/
│   └── icon.png
└── dist/               # Build output
```

### forge.toml Configuration

```toml
[app]
name = "My App"
version = "1.0.0"
description = "My first Forge app"
authors = ["Your Name"]

[window]
title = "My App"
width = 1200
height = 800
resizable = true
fullscreen = false

[build]
entry = "src/main.py"
icon = "assets/icon.png"
output_dir = "dist"
single_binary = true

[dev]
frontend_dir = "src/frontend"
hot_reload = true
port = 5173
dev_server_command = "npm run dev"
dev_server_url = "http://127.0.0.1:5173"
dev_server_timeout = 20

[permissions]
filesystem = true
clipboard = true
dialogs = true
notifications = true
system_tray = false
updater = false

[protocol]
schemes = ["forge"]

[packaging]
app_id = "dev.forge.myapp"
product_name = "My App"
formats = ["dir", "appimage"]
category = "Utility"

[signing]
enabled = false
adapter = "auto"
identity = "Developer ID Application: Example Corp"
verify_command = "codesign --verify --deep"
notarize = false
notarize_command = "xcrun notarytool submit dist/MyApp.dmg --wait"
timestamp_url = "https://timestamp.example.com"

[updater]
enabled = false
endpoint = "https://updates.example.com/manifest.json"
channel = "stable"
check_on_startup = false
allow_downgrade = false
require_signature = true
staging_dir = ".forge-updater"
install_dir = "dist/current"
```

### Exposing Python to JavaScript

```python
# src/main.py
from forge import ForgeApp

app = ForgeApp()

@app.command
def greet(name: str) -> str:
    return f"Hello, {name}! From Python 🐍"

@app.command
def get_system_info() -> dict:
    import platform
    return {
        "os": platform.system(),
        "python": platform.python_version(),
    }

@app.command
async def read_file(path: str) -> str:
    with open(path, "r") as f:
        return f.read()

app.run()
```

### Calling Python from JavaScript

```javascript
import forge, { invoke, on } from "@forgedesk/api";

// Call a Python command
const result = await invoke("greet", { name: "Alice" });
console.log(result); // "Hello, Alice! From Python 🐍"

// Get system info
const info = await invoke("get_system_info");
console.log(info.os); // "Windows" / "Darwin" / "Linux"

// Use built-in APIs
await forge.clipboard.write("Hello, World!");
const text = await forge.clipboard.read();

// Application menu model
await forge.menu.set([
    {
        id: "file",
        label: "File",
        submenu: [
            { id: "file.open", label: "Open" },
            { type: "separator" },
            { id: "file.pin", label: "Pin", type: "checkbox", checked: true }
        ]
    }
]);
await forge.menu.trigger("file.open");

// System tray model
await forge.tray.setMenu([
    { label: "Open", action: "open" },
    { separator: true },
    { label: "Pin", action: "pin", checkable: true, checked: true }
]);
await forge.tray.trigger("open", { source: "frontend" });

// Desktop notifications
await forge.notifications.notify("Forge", "Background sync complete", {
    timeout: 4
});

// Deep link dispatch into the running app
await forge.deepLink.open("forge://notes/open?id=123");

// File operations
const content = await forge.fs.read("notes/my-note.txt");
await forge.fs.write("notes/my-note.txt", content);

// Dialogs
const path = await forge.dialog.open({
    title: "Open File",
    filters: [{ name: "Text", extensions: ["txt"] }]
});

// Window controls (native multiwindow on desktop, managed popup fallback on web)
const currentWindow = await forge.window.current();
const allWindows = await forge.window.list();
await forge.window.create({ label: "settings", route: "/settings", width: 900, height: 640 });
await forge.window.setTitle("Forge Notes");
await forge.window.setPosition(120, 80);
await forge.window.setSize(1280, 800);
await forge.window.setFullscreen(false);
await forge.window.focus();
const state = await forge.window.state();
console.log(state.width, state.height);
console.log(await forge.window.position());
console.log(await forge.window.isVisible());

// Updater metadata and manifest checks
const updaterConfig = await forge.updater.config();
const update = await forge.updater.check();
console.log(updaterConfig.channel, update.update_available);

// Signed updater flow
const verification = await forge.updater.verify();
if (verification.verified && update.update_available) {
    const result = await forge.updater.update({
        installDir: "dist/current"
    });
    console.log(result.apply.install_dir);
}
```

### Event System

```python
# Python emitting events
import time, threading

@app.command
def start_progress():
    def run():
        for i in range(101):
            app.emit("progress_update", {"value": i})
            time.sleep(0.05)
    threading.Thread(target=run).start()
```

```javascript
// JavaScript listening for events
on("progress_update", (data) => {
    document.getElementById("progress").value = data.value;
});

on("window:resized", (data) => {
    console.log("Window resized:", data.label, data.width, data.height);
});
```

## 🛠️ CLI Commands

| Command | Description |
|---------|-------------|
| `forge create <name>` | Scaffold a new project |
| `forge dev` | Start development mode with hot reload |
| `forge build` | Build a production binary |
| `forge package` | Build desktop artifacts and emit package/install metadata |
| `forge sign` | Sign and verify an existing package manifest |
| `forge release` | Build and generate a release manifest |
| `forge info` | Display system and project info |
| `forge doctor` | Validate environment with remediation hints |
| `forge plugin-add <name>` | Install and register a plugin |
| `python -m forge` | Alternative CLI entry point |

### CLI Diagnostics

- `forge info --output json` - Machine-readable environment and project details
- `forge doctor` - Human-readable prerequisite validation with fix suggestions
- `forge doctor --output json` - CI-friendly doctor results with exit code `0` on success and `1` on blocking issues
- `forge build --result-format json` - CI-friendly build results including target, selected builder, produced artifacts, and validation errors
- `forge package --result-format json` - Package manifests, installer descriptors, and generated installer artifacts
- `forge sign --result-format json` - Signing, verification, and notarization status for an existing build output
- `forge release --result-format json` - End-to-end build plus release manifest generation

- `forge doctor` and `forge info` also surface plugin/security config through project payloads.

## 📦 Built-in APIs

### File System (`forge.fs`)
- `read(path)` - Read file contents
- `write(path, content)` - Write to file
- `exists(path)` - Check if path exists
- `list(path)` - List directory contents
- `delete(path)` - Delete file/directory
- `mkdir(path)` - Create directory

### Dialogs (`forge.dialog`)
- `open(options)` - Open file dialog
- `save(options)` - Save file dialog
- `message(title, body, type)` - Message dialog

### Clipboard (`forge.clipboard`)
- `read()` - Read clipboard text
- `write(text)` - Write to clipboard

### System (`forge.app`)
- `version()` - Get app version
- `platform()` - Get platform name
- `info()` - Get system info
- `exit()` - Exit application

### Menu (`app.menu` / `window.__forge__.menu`)
- On Linux desktop builds, Forge now projects this model into a native menu bar and routes native selections back through `menu:select`.
- `set(items)` - Replace the active menu tree
- `get()` - Read the current menu model snapshot
- `clear()` - Remove all menu items
- `enable(id)` / `disable(id)` - Toggle item enabled state
- `check(id)` / `uncheck(id)` - Toggle item checked state
- `trigger(id, payload?)` - Emit a framework menu selection event

### Tray (`app.tray` / `window.__forge__.tray`)
- Enable the `system_tray` permission in `forge.toml` before use.
- `setIcon(path)` / `set_icon(path)` - Configure the tray icon asset
- `setMenu(items)` / `set_menu(items)` - Replace tray menu items
- `show()` / `hide()` - Toggle tray visibility
- `isVisible()` / `is_visible()` - Read visibility state
- `state()` - Inspect tray backend and menu state
- `trigger(action, payload?)` - Emit a framework tray selection event

### Notifications (`app.notifications` / `window.__forge__.notifications`)
- Enable the `notifications` permission in `forge.toml` before use.
- `notify(title, body, ...)` - Send a desktop notification with the best available backend
- `state()` - Inspect notification backend availability and the last sent notification
- `history(limit?)` - Read recent notification delivery metadata

### Deep Links (`app.deep_links` / `window.__forge__.deepLink`)
- Configure `[protocol].schemes` in `forge.toml` for accepted custom URL schemes.
- `open(url)` - Validate and dispatch a deep link into the running application
- `state()` - Inspect configured schemes and recent deep link history
- `protocols()` - Read configured protocol handler schemes

### Window (`app.window` / `window.__forge__.window`)
- `setTitle(title)` / `set_title(title)` - Update the window title
- `setPosition(x, y)` / `set_position(x, y)` - Move the window
- `setSize(width, height)` / `set_size(width, height)` - Resize the window
- `setFullscreen(enabled)` / `set_fullscreen(enabled)` - Toggle fullscreen
- `state()` - Read the cached window state snapshot
- `position()` - Read the cached window position
- `isVisible()` - Check visibility state
- `isFocused()` - Check focus state

### Runtime (`app.runtime` / `window.__forge__.runtime`)
- `health()` - Lightweight runtime health snapshot
- `diagnostics()` - Full diagnostics payload including updater, tray, notifications, and deep-link state
- `commands()` - Registered command manifest
- `protocol()` - Protocol compatibility details
- `plugins()` - Loaded plugin summary and manifest metadata
- `security()` - Effective IPC command allow/deny policy
- `lastCrash()` / `last_crash()` - Latest captured crash snapshot, if any
- `state()` - Runtime navigation/devtools state snapshot
- `logs(limit)` - Recent structured runtime logs
- `navigate(url)` / `reload()` / `back()` / `forward()` - Native runtime navigation controls
- `openDevtools()` / `closeDevtools()` / `toggleDevtools()` - Native devtools controls
- `exportSupportBundle(destination)` - Export a support bundle zip with diagnostics, logs, config, registry, and crash snapshot

### Updater (`app.updater` / `window.__forge__.updater`)
- `currentVersion()` / `current_version()` - Current app version used for update checks
- `channels()` - Supported release channels
- `config()` - Effective updater configuration snapshot
- `manifestSchema()` / `manifest_schema()` - Release manifest schema descriptor
- `generateManifest(options)` / `generate_manifest(...)` - Generate updater manifest metadata
- `check(manifestUrl?, currentVersion?)` / `check(...)` - Evaluate a local or remote release manifest
- `verify(manifestUrl?, publicKey?)` / `verify(...)` - Verify an Ed25519-signed release manifest
- `download(options)` / `download(...)` - Download the selected artifact and verify its checksum
- `apply(options)` / `apply(...)` - Extract and apply a downloaded artifact with backup/rollback support
- `update(options)` / `update(...)` - End-to-end check, verify, download, and apply flow

Updater notes:
- Sign manifests with Ed25519 and store the public key in `[updater].public_key`.
- Sign the canonical manifest JSON with `release.signature` omitted.
- Artifacts are checksum-verified before apply.
- Archive applies create a backup and roll back automatically on failure.

Packaging/signing notes:
- `forge build --result-format json` now includes protocol-handler, packaging, and signing contract metadata.
- `forge package --result-format json` emits `forge-package.json`, `forge-protocols.json`, and `forge-plugins.json` without requiring a release manifest.
- `forge sign --result-format json` consumes an existing `forge-package.json` and runs sign/verify/notarize adapters independently from the build step.
- `forge release --result-format json` writes `forge-release.json` with artifact digests, package metadata, signing status, and notarization status.
- Set `[packaging].app_id` for desktop builds that use custom protocols or signing.
- Configure `[signing]` metadata early; Forge surfaces contract warnings during build validation and supports default platform adapters when `identity` is set.
- Desktop builds now emit `forge-package.json` and `forge-protocols.json` into the build output directory.
- Desktop builds also emit format-specific installer descriptors based on `[packaging].formats`.
- Requested installer formats now fail hard when the required packaging toolchain is missing. Forge no longer emits placeholder `.dmg`, `.exe`, `.AppImage`, or `.flatpak` files.
- On Linux, desktop builds with `formats = ["deb"]` now also emit a real `.deb` installer artifact into the build output directory.
- On macOS, desktop builds with `formats = ["app"]` emit an `.app` bundle scaffold, and `formats = ["dmg"]` can produce a `.dmg` through `hdiutil`.
- On Windows, desktop builds with `formats = ["msi"]` emit a WiX source and build an `.msi` when `wixl` or WiX toolchain binaries are available, while `formats = ["nsis"]` can produce an NSIS installer through `makensis`.
- On Linux, desktop builds with `formats = ["appimage"]` can produce an AppImage through `appimagetool`, and `formats = ["flatpak"]` can produce a Flatpak bundle through `flatpak-builder` + `flatpak build-bundle`.
- On Linux, builds with configured custom protocols also emit a `.desktop` registration descriptor for `x-scheme-handler/...` integration.
- When `[signing].sign_command` or `[signing].verify_command` are configured, Forge runs them during `forge build` with `FORGE_BUILD_OUTPUT_DIR`, `FORGE_BUILD_ARTIFACTS`, and `FORGE_PACKAGE_MANIFEST` exported.
- Without custom commands, Forge uses default signing adapters where available: GPG on Linux, `codesign` on macOS, and `signtool` on Windows. `[signing].adapter` can force a concrete adapter. If `[signing].notarize` is enabled, Forge can also run `notarize_command` or `xcrun notarytool` on macOS.
- Generated frontend templates now default to `@forgedesk/api` plus `@forgedesk/vite-plugin`, so modern frontend stacks can stay npm-first while still targeting the Forge runtime.
- The repository now includes release-hardening workflows in [.github/workflows/release-matrix.yml](.github/workflows/release-matrix.yml) and [.github/workflows/signing-validation.yml](.github/workflows/signing-validation.yml) plus smoke/signing helpers under [scripts/ci](scripts/ci).

## 🎯 Examples

### Hello Forge

A minimal demo app validating IPC functionality:

```bash
cd examples/hello_forge
forge dev
```

### Forge Notes

A note-taking app demonstrating the file system API:

```bash
cd examples/forge_notes
forge dev
```

## 🔧 Development

### Setting Up

```bash
# Clone the repository
git clone https://github.com/forge-framework/forge.git
cd forge

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black forge/
ruff check forge/
```

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

Forge is inspired by:
- [Tauri](https://tauri.app/) — The Rust-based desktop framework
- [pywebview](https://pywebview.flowrl.com/) — Python webview library
- [Electron](https://www.electronjs.org/) — Cross-platform desktop apps

---

**Forge the future. Ship with Python.** 🚀
