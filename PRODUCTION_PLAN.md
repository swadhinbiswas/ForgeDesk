# Forge Framework - Production Grade Implementation Plan [COMPLETED]

Achieving full Tauri-level parity with Python 3.14 (NoGIL/free-threading support).

## 1. Multi-Window Architecture (Rust) [IMPLEMENTED]
- **Goal:** Move window management out of Python shims into a Rust-managed registry.
- **Implementation:**
  - `src/native_window.rs` successfully tracks and routes `Event::UserEvent` to specific isolated WebViews with `HashMap<WindowId, RuntimeWindow>` and string labels.
  - Python IPC bridge correctly passes and expects `window_label` and `origin` window routing contexts (`forge/bridge.py`).

## 2. Granular Security Scopes (Rust/Python) [IMPLEMENTED]
- **Goal:** Replace boolean capability flags (`fs = true`) with strict directory-based JSON schema scopes.
- **Implementation:**
  - Created `forge/scope.py` using `fnmatch` logic to restrict all OS paths strictly mapping to $APPDATA/home expansions.
  - Refactored `forge/api/fs.py` so operations validate heavily against these active scopes.

## 3. Strict IPC Payload Validation (Python) [IMPLEMENTED]
- **Goal:** Prevent remote execution, prototype pollution, or fuzzing via malicious IPC messages.
- **Implementation:**
  - Upgraded `forge/bridge.py` routing layer.
  - Dynamically extracts and converts command signatures to Pydantic models.
  - Enforces type safety + restricts kwargs on all IPC invocations prior to executing.

## 4. Python Backend Hot-Reload [IMPLEMENTED]
- **Goal:** Make local development fast, deterministic, and debuggable.
- **Implementation:**
  - Upgraded development loop in `forge_cli/main.py` using `watchfiles` to monitor project directory.
  - Automatically performs a clean full-process restart via `os.execv` on changes to `.py` or `.toml` files.
  - Leaves frontend file changes to the frontend dev server for simple page reloads.

## 5. Unified Packager & Installers (CLI) [IMPLEMENTED]
- **Goal:** Provide a single-command build pipeline (`forge build`) to produce native distribution artifacts instead of just Python directories.
- **Implementation:**
  - Upgraded `forge_cli/bundler.py` logic.
  - Automatically scaffolds macOS (`.app`/`Contents`/`MacOS`) wrapping standard `Info.plist`.
  - Automatically generates `installer.nsi` scripts dynamically targeting compiled artifacts for precise Windows `.exe`/`.msi` builds.
  - Automatically wraps Linux builds into standard `AppDir` with `AppRun` bindings before invoking `appimagetool`.

---
*Roadmap agreed upon for April 2026.*


## 7. Auto-Update Applicator (Rust) [IMPLEMENTED]
- **Goal:** Handle background downloading, verification, and hot-swapping of updates matching Tauri's self-updater.
- **Implementation:**
  - Implemented `src/updater.rs` leveraging `reqwest` and `self-replace`.
  - Added strict `ed25519-dalek` signature verification before any binary swapping occurs.
  - Bound `WindowProxy.apply_update` IPC endpoint to safely trigger the download & background replace without locking the UI thread.
- **Goal:** Allow the desktop app to bypass macOS Gatekeeper, Windows SmartScreen, and enterprise AV without user warnings.
- **Implementation:** 
  - Upgraded `forge_cli/main.py`.
  - **macOS:** Dynamically injects `--options=runtime` and `--entitlements` during `codesign`. Executes a deep 'inside-out' signing algorithm on `.app` bounds. Supports `xcrun notarytool` with ENV integrations and fully implements the final `xcrun stapler` process to allow offline Gatekeeper approval.
  - **Windows:** Before invoking `signtool` on the outermost `.msi`/`.exe`, it systematically scans the build directory and applies an Authenticode hash to all internal binaries (`.dll`, `.exe`, `.pyd`), silencing SmartScreen alarms.


## 6. Code Signing & CI/CD Pipelines (Security) [IMPLEMENTED]
- **Goal:** Allow the desktop app to bypass macOS Gatekeeper, Windows SmartScreen, and enterprise AV without user warnings.
- **Implementation:** 
  - Upgraded `forge_cli/main.py`.
  - **macOS:** Dynamically injects `--options=runtime` and `--entitlements` during `codesign`. Executes a deep 'inside-out' signing algorithm on `.app` bounds. Supports `xcrun notarytool` with ENV integrations and fully implements the final `xcrun stapler` process to allow offline Gatekeeper approval.
  - **Windows:** Before invoking `signtool` on the outermost `.msi`/`.exe`, it systematically scans the build directory and applies an Authenticode hash to all internal binaries (`.dll`, `.exe`, `.pyd`), silencing SmartScreen alarms.

## 8. Native OS GUI Consolidation (Rust) [IMPLEMENTED]
- **Goal:** Move Tray, Dialogs, and Menus from Python polyfills into the Rust core using `tao`, `wry`, `muda`, `tray-icon`, etc.
- **Implementation:**
  - Integrated `muda` for cross-platform native application menus.
  - Replaced Tkinter/PyQt shims with `rfd` and `wry` dialogs.
  - Implemented `tray-icon` for native system tray integration directly in the Rust loop.
  - Updated the Python and JS bridges to communicate with the native Rust implementations via `WindowProxy`.
