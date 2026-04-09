# Forge Architecture

Forge is a "Tauri for Python" framework. It bridges web technologies (HTML/CSS/JS) with a high-performance Rust native core and a Python 3.14+ (NoGIL) backend to create secure, lightweight desktop applications.

## Layer Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (JS/TS)                      │
│  React / Vue / Svelte / Plain HTML+CSS+JS               │
│  @forge/api ─── invoke("cmd", args) ─── on("event")    │
├─────────────────────────────────────────────────────────┤
│                    IPC Bridge (Python)                    │
│  forge/bridge.py ─── JSON messages ─── Thread pool      │
│  Strict Pydantic Validation │ Scoped Capability Checks │
├─────────────────────────────────────────────────────────┤
│                    Runtime (Python)                       │
│  forge/app.py ─── ForgeApp ─── API modules              │
│  State │ Events │ Plugins │ Config │ Lifecycle           │
├─────────────────────────────────────────────────────────┤
│                    Native Core (Rust)                     │
│  src/native_window.rs ─── src/window/mod.rs              │
│  Wry / Tao WebView │ Multi-Window Registry │ GUI (muda) │
└─────────────────────────────────────────────────────────┘
```

## 1. Native Core (Rust)
The lowest layer handles tight OS integration, bypassing massive UI bloat frameworks (like Electron/CEF).
- **Multi-Window System**: Built on `tao` and `wry`, maintaining a Rust-owned registry of active WebView windows with unique UUIDs. The Python and JS layers only see the Window labels.
- **Native OS GUI Consolidation**: Features like System Trays (`tray-icon`), context menus (`muda`), and File Pickers (`rfd`) run directly in Rust, interacting safely with native OS C APIs instead of relying on Python shims or browser WebAPIs, ensuring pure native event-loops.
- **Auto-Updater**: Background downloaded `Reqwest` payloads are strictly matched to an `Ed25519` key, swappable via `self-replace` without ever blocking the UI/event loop.

## 2. Python 3.14 (Free-Threading / NoGIL)
Because Forge uses **Python 3.14+ Free-Threading**, it removes the typical asynchronous UI bottleneck.
- Commands from the WebView immediately jump into a concurrent thread pool (`ThreadPoolExecutor`) executed safely bypassing the Global Interpreter Lock (GIL). 
- Python hot-reloads instantly during development (`forge dev` via `watchfiles` and `os.execv`) retaining active Window processes or cleanly spinning them back up.

## 3. IPC Bridge (Strict Type Validation)
Commands traverse from JS to Python through a tightly guarded bridge:
- Signatures derived via Python 3.14 type hints (`typing.get_type_hints`) instantly synthesize into exact **Pydantic schemas**.
- Unexpected kwargs, un-allowed execution scopes, or spoofed commands are rejected *before* Python evaluates the core function payload. 
