# Forge Framework API Analysis

Based on a deep and rigorous analysis of the `forge-framework` codebase, here is a brutal assessment of what APIs are present and what essential APIs are entirely missing to consider this a fully complete desktop application framework on par with industry standards like Electron or Tauri.

## Currently Implemented APIs

The framework provides a strong foundation with the following modules:
1. **Window / Webview / Setup** (`app.py`): Control single/multi window positions, sizes, states, devtools, ipc, capabilities.
2. **File System** (`fs.py`): Basic file interactions.
3. **Dialogs** (`dialog.py`): Native open, save, message box dialogs.
4. **Notifications** (`notification.py`): Desktop notifications.
5. **Deep Linking** (`deep_link.py`): Protocol schema bindings (`myapp://`).
6. **Clipboard** (`clipboard.py`): Read/write text to system clipboard.
7. **Menu** (`menu.py`): Native application menus and context menus.
8. **Tray** (`tray.py`): System tray/menu bar icons and simple menus.
9. **System** (`system.py`): Environment vars, OS info, opening standard URLs/files, checking basic state.
10. **Updater** (`updater.py`): OTA and app update management.

---

## 🛑 MISSING APIs (The Brutal Truth)

To build *any* kind of professional desktop application (e.g., media players, hardware flashers, background sync tools, advanced window managers), the framework currently lacks several fundamental desktop APIs.

### 1. Global Shortcuts / Hotkeys API (`global_shortcut.py`)
- **Missing feature:** Ability to register system-wide keyboard shortcuts that trigger even when the application is minimized, out of focus, or running only in the system tray. 
- **Use case:** Screenshots tools, quick-summon search bars (like Spotlight/Raycast), media playback controls.

### 2. Screen & Displays API (`screen.py`)
- **Missing feature:** Querying connected monitors, primary display, geometry (X, Y bounds), work areas (geometry excluding taskbars/docks), and DPI scale factors.
- **Use case:** Spawning contextual child windows correctly on the monitor where the user's cursor currently is, or managing multi-monitor dashboard behaviors.

### 3. Native Network & Custom Protocols API (`protocol.py` or native Fetch)
- **Missing feature:** A way to register custom schemes (e.g., `forge://`) to intercept webview requests and stream local/dynamic data securely, bypassing CORS and browser restrictions natively.
- **Use case:** Streaming huge video files from disk without fully loading them into memory, or fetching third-party APIs without dealing with strict local CORS policies.

### 4. Power & Hardware State Monitor API (`power.py`)
- **Missing feature:** Listening to OS-level power events: suspend, resume, screen locked, screen unlocked, running on battery, and AC state.
- **Use case:** Pausing a heavy background task when the user goes on battery power or resuming a WebSocket sync when the laptop wakes up from sleep.

### 5. Secure Storage / Keychain API (`keychain.py`)
- **Missing feature:** Access to the OS's native secure credential managers (macOS Keychain, Windows Credential Vault, Linux Secret Service).
- **Use case:** Storing OAuth tokens, database passwords, and user credentials safely rather than in plaintext config files or `localStorage`.

### 6. App Lifecycle & Single Instance API (`app_lifecycle.py`)
- **Missing feature:** Native single-instance locking (`request_single_instance_lock()`), automatic focus of the existing instance if a second one is launched, and seamless `relaunch()` logic.
- **Use case:** Preventing users from opening 5 instances of a heavy desktop application simultaneously.

### 7. OS Integration & Taskbar API (`os_integration.py`)
- **Missing feature:** Managing the taskbar/dock icon visually. Missing macOS dock bouncing, taskbar/dock progress bars, window badges (e.g., "5 unread messages"), and Windows Jump Lists.
- **Use case:** Download managers showing a progress bar on the taskbar icon; chat applications badging unread notification counts natively.

### 8. Autostart / Login Items API (`autostart.py`)
- **Missing feature:** Programmatic registration to launch the application automatically when the OS boots/user logs in (in the background or minimized).
- **Use case:** Cloud sync clients, background daemons, or menu bar utility tools.

### 9. Hardware & Device Interfaces (WebUSB/WebSerial emulation or Native pass-through)
- **Missing feature:** Exposing native hardware interfaces (USB, Serial ports, Bluetooth) safely to the front-end, or providing a structured backend wrapper.
- **Use case:** IoT flashed tools, keyboard configuration software, local hardware controllers.

### 10. Native Drag & Drop API
- **Missing feature:** Listening contextually to dragging native files OVER the window and out of the window. 
- **Use case:** Dragging an image from the webview out to the user's Desktop to save it, or dragging 50 files into the UI without the webview crashing.

### 11. Printing and PDF Generation API
- **Missing feature:** Giving the webview direct access to system printers (`print()`, `printToPDF()`) silently without user interaction.
- **Use case:** Point-of-Sale (POS) systems, receipt/invoice generation, automated ticketing.

---

## 🚀 The "Tauri Gap" (What it takes to be on par with Tauri)

Beyond just a list of raw APIs, reaching **Tauri's level of maturity** requires a fundamental shift in architecture, Developer Experience (DX), and security modeling. Based on your `PLAN.md` and current Python/Rust hybrid architecture (`app.py`, `lib.rs`, `plugin.py`), here is the brutal analysis of the framework's shortcomings compared to Tauri:

### 1. The Isolation Pattern & IPC Security
- **Tauri's Strength:** Tauri uses an "Isolation Pattern" where an injected iframe intercepts all IPC messages to prevent the frontend from directly invoking arbitrary backend code if the webview is compromised (XSS attacks). Messages are cryptographically signed.
- **Forge's Gap:** Forge's IPC (Rust `->` Python `->` JS) relies on a basic string-based schema (`_on_ipc_message`). If an attacker gets XSS in the frontend, they can arbitrary call any permitted `forge.invoke()` command. Furthermore, Tauri implements **Strict Scopes** (e.g., allowing `$FS/read` *only* in `C:\Users\John\AppData\Local\MyApp\data`). Forge's capability model (`has_capability`) is strictly boolean—it turns an API on or off entirely, without sandboxing paths or URLs.

### 2. State Management & Dependency Injection
- **Tauri's Strength:** You can register a native `Mutex<State>` in Rust, and Tauri will automatically inject it into any command handler that asks for it, heavily optimizing thread-safe state sharing.
- **Forge's Gap:** You are forced to manually manage global/singleton state in Python (`app.state()` or custom singletons). Handlers rely on closures or classes rather than elegant Dependency Injection of strongly-typed state pointers.

### 3. Build Tooling & Bundlers (The hardest part)
- **Tauri's Strength:** The magic of `tauri build` is that it orchestrates the Frontend bundler (Vite, Webpack), Cargo compilation, code signing, and automatically generates OS-native installers: `.msi` via WiX, `.app` / `.dmg` on Mac, and `.deb` / `.AppImage` on Linux dynamically.
- **Forge's Gap:** Your `PLAN.md` admits CLI determinism is "Not yet production-grade" and orchestration is "Partial". Generating native installers (like an MSI or an actual `.app` bundle, beyond simple scripts like `sign_macos.py`) is extremely complex. Developers must piece together frontend builds and backend bundlers. Without a unified `forge build` that outputs a `.dmg` and `.msi` in one click, it cannot compete with Tauri's DX.

### 4. Zero-Overhead ABI / Memory passing
- **Tauri's Strength:** Moving a 50MB array of bytes from Rust to JS can be done via raw buffers or highly optimized WRY streams with near-zero copy overhead. 
- **Forge's Gap:** Data must be serialized in Rust, deserialized into Python via PyO3, transformed by backend logic, serialized to JSON (or MessagePack), and sent to JS. This double-hop architecture introduces serious performance bottlenecks for heavy applications (e.g., video editing, CAD tools) compared to Tauri.

### 5. Multi-Window State Persistency
- **Tauri's Strength:** A first-party plugin saves window size, position, maximization state, and monitor bindings securely, ensuring that when the app restarts, it looks exactly identical to when it closed, preventing "window teleporting".
- **Forge's Gap:** Current windows (`app.py` `WindowAPI`) initialize using simple configs. Developers have to manually listen to resize/move events, write to the filesystem (`fs.py`), and load those coordinates dynamically on process start.

### 6. Transparent & Vibrancy Window Styling
- **Tauri's Strength:** First-class support for `window-vibrancy` (macOS visual materials like `hudWindow`, `popover`) and Windows Mica / Acrylic API blending directly in the Rust bindings.
- **Forge's Gap:** By reviewing `src/lib.rs`, the window configuration only exposes `set_fullscreen`, `set_always_on_top`, `set_menu`, and raw sizing. There is no mapping to `NSVisualEffectView` or Win32 `DwmEnableBlurBehindWindow`. You cannot build beautiful modern "glass" UIs.

### 7. Core Mobile Support (iOS / Android)
- **Tauri's Strength:** Tauri 2.0 treats mobile as a first-class citizen, wrapping WKWebView on iOS and WebView on Android.
- **Forge's Gap:** Strictly desktop-bound.

### Conclusion: The Immediate Roadmap
To become the "Python equivalent of Tauri", Forge must instantly prioritize:
1. **Granular FS/Network Scopes** (Path-based sandboxing, not just booleans).
2. **Transparent / Mac-Mica Windowing APIs** (To appeal to UI designers).
3. **One-Command Installers** (`forge build` producing ready-to-ship `.msi` and `.dmg`).
