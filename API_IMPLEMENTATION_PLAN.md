# Forge Framework Implementation Plan: Elevating to Tauri Equivalence

This document outlines the priority-based rollout strategy to implement the missing native APIs identified in `missing.md`.

## 🏗️ Phase 1: Core Desktop Foundations
These are non-negotiable for a professional desktop app experience.

1. **Screen & Displays API (`forge/api/screen.py`)** **(STARTING HERE)**
   - **Rust Backend:** Use `tao`'s `MonitorHandle` to get active monitors, bounding boxes, and scale factors.
   - **Python API:** `app.screen.get_monitors()`, `app.screen.primary()`.
2. **Global Shortcuts (`forge/api/shortcuts.py`)**
   - **Rust Backend:** Integrate `global-hotkey` crate.
   - **Python API:** `app.shortcuts.register("Cmd+Shift+X", callback)`.
3. **App Lifecycle & Single Instance (`forge/api/lifecycle.py`)**
   - **Rust Backend:** Platform-specific named pipes or `single-instance` crate.
   - **Python API:** `app.lifecycle.request_single_instance()`.

## 🛠️ Phase 2: OS Integration & UX
These APIs make the application feel truly native to the host operating system.

4. ~~Taskbar & Dock Integration (`forge/api/os_integration.py`)**
   - **Features:** Progress bars, badges, macOS dock bouncing.
5. ~~Autostart & Login Daemons (`forge/api/autostart.py`)**
   - **Features:** Register app to launch at boot/login.
6. ~~Power Monitor API~~ (`forge/api/power.py`)**
   - **Features:** Suspend/resume events, AC/battery state.

## 🔐 Phase 3: Tauri-Level Security & High-Performance IPC
Implementing the "Tauri Gap" architectural differences.

7. ~~Strict FS & Capability Scopes~~
   - **Features:** Change `permissions.fs = true` to `permissions.fs.read = ["$APPDATA/myapp"]`.
8. ~~**Secure Keychain Storage API (`forge/api/keychain.py`)**
   - **Features:** Encrypted credential vault using `keyring` crate.
9. ~~**Native Custom Protocol Streams (`forge://`)**
   - **Features:** Intercept web requests natively to stream fast buffers.

---

## 🚀 Execution: Progressing to Phase 3
Phase 1, 2, and 3 are complete. All native APIs implemented.

## 🎨 Phase 4: UI Vibrancy, Persistency & Native Feel
Focusing on making the framework feel like a native, robust, and highly *Pythonic* experience for developers.

10. **Transparent & Vibrancy Window Styling**
    - **Rust Backend:** Integrate `window-vibrancy` for native macOS Mica/Windows Acrylic.
    - **Python API:** `app.config.window.vibrancy = "sidebar"` (Abstracting the complexity into Python settings).
11. **Multi-Window State Persistency (`forge/api/window_state.py`)**
    - **Features:** Auto-save/restore window positions and sizes to prevent "window teleporting" using a pure Python persistent state manager.
12. ~~Native Drag & Drop API (`forge/api/drag_drop.py`)**
    - **Features:** Intercept heavy files natively and emit clean Python events (`@app.events.on("drag_drop")`) with native absolute paths.
13. **Printing and PDF Generation**
    - **Features:** Expose silent printing and PDF generation to the Python backend with zero overhead.
14. **Unified Build Tooling (`forge_cli/build.py`)**
    - **Features:** A seamless `forge build` command handling Vite, Python bundling, and native installer generation orchestrations in one Python-centric step.

---
## 🚀 Execution: Progressing to Phase 4
Phase 1, 2, and 3 are complete. Starting Phase 4 (UI Vibrancy, Persistency & Native Feel).
