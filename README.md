<div align="center">
  <img src="branding/forgedesk-logo.svg" alt="ForgeDesk Logo" width="220" />
</div>

<h1 align="center">ForgeDesk</h1>

<div align="center">
  <strong>The fast, modern, and secure way to build desktop applications with Python.</strong>
</div>
<br />

<div align="center">
  <a href="https://pypi.org/project/forgedesk/"><img src="https://img.shields.io/pypi/v/forgedesk.svg?style=for-the-badge&color=blue" alt="PyPI version" /></a>
  <a href="https://www.npmjs.com/package/@forgedesk/api"><img src="https://img.shields.io/npm/v/@forgedesk/api.svg?style=for-the-badge&color=cb3837" alt="NPM version" /></a>
  <img src="https://img.shields.io/badge/python-3.14+ (Free--Threading)-blue?style=for-the-badge" alt="Python" />
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey?style=for-the-badge" alt="Platform" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License" />
  <a href="https://github.com/swadhinbiswas/ForgeDesk/actions"><img src="https://img.shields.io/github/actions/workflow/status/swadhinbiswas/ForgeDesk/ci.yml?style=for-the-badge" alt="CI Status" /></a>
</div>

---

**ForgeDesk** is a next-generation framework designed to give you the ultimate desktop app development experience. It combines the heavy data-processing capabilities of **Python**, the memory safety and performance of a **Rust** backend, and the UI flexibility of **Modern Web Frameworks**.

By leveraging OS-native WebViews (via `wry` and `tao`) instead of bundling Chromium, ForgeDesk produces incredibly lightweight binaries that launch instantly and consume a fraction of the RAM of typical Electron apps.

## <img src="https://api.iconify.design/lucide/sparkles.svg" width="28" height="28" align="top" /> Why Choose ForgeDesk?

- <img src="https://api.iconify.design/logos/python.svg" width="20" height="20" align="top" /> **Python-First & Blazing Fast**: Built natively for Python 3.14 Free-Threading (`NoGIL`). Say goodbye to the Global Interpreter Lock and hello to true multi-core processing, bridged through a highly optimized Rust core layer.
- <img src="https://api.iconify.design/lucide/palette.svg?color=%23ff5e00" width="20" height="20" align="top" /> **Beautiful CLI Experience**: An interactive, Astro-inspired terminal setup wizard. Scaffold your entire application architecture in seconds.
- <img src="https://api.iconify.design/lucide/zap.svg?color=%23eab308" width="20" height="20" align="top" /> **Bring Your Own UI**: First-class, out-of-the-box support for **React**, **Next.js**, **Vue**, **Svelte**, **Astro**, and Vanilla JS.
- <img src="https://api.iconify.design/lucide/wind.svg?color=%2306b6d4" width="20" height="20" align="top" /> **Zero-Config Tailwind CSS**: The CLI can automatically install and configure Tailwind CSS, PostCSS, and inject your CSS entry directives with a single keypress.
- <img src="https://api.iconify.design/lucide/lock.svg?color=%23ef4444" width="20" height="20" align="top" /> **Security by Design**: A meticulously scoped file and URL runtime model ensures your users are always safe from path traversal and unauthorized IPC cross-site scripting.
- <img src="https://api.iconify.design/lucide/package.svg" width="24" height="24" align="top" /> **NPM Ecosystem Integration**: Native `@forgedesk/api` packages that feel completely natural for frontend developers, alongside seamless Vite + HMR integration.
- <img src="https://api.iconify.design/lucide/window.svg" width="20" height="20" align="top" /> **Multi-Window Support**: Create and manage multiple native windows with full IPC routing.
- <img src="https://api.iconify.design/lucide/shield.svg" width="20" height="20" align="top" /> **Auto-Updates with Delta Patching**: Built-in updater with Ed25519 signature verification and binary diff updates (1-5MB vs 30-50MB).

---

## <img src="https://api.iconify.design/lucide/rocket.svg" width="28" height="28" align="top" /> Quick Start

Getting started is incredibly easy. Ensure you have Python 3.14+ and Node.js installed, then run the ForgeDesk wizard:

```bash
# 1. Install the CLI
uv pip install forgedesk
# (or `pip install forgedesk`)

# 2. Launch the interactive scaffolding wizard
forge create
```

**The beautiful terminal UI will ask you seamlessly to configure:**
1. Your project directory name.
2. Your favorite UI framework (React, Next.js, Vue, Svelte, Astro).
3. Your preferred Node package manager (`npm`, `pnpm`, `bun`).
4. Whether you'd like **Tailwind CSS** automatically configured.

```bash
# 3. Enter your project directory
cd your-new-app

# 4. Start the development server (Hot Module Replacement included!)
forge dev
```

When you are ready to ship to production, building a highly optimized binary is just as easy:
```bash
forge build
```

---

## <img src="https://api.iconify.design/lucide/brain.svg" width="28" height="28" align="top" /> Architecture & IPC Bridge

ForgeDesk provides a seamless IPC (Inter-Process Communication) bridge between your Python backend and your JavaScript frontend. You write your system logic in Python, and your UI logic in TypeScript/JavaScript.

### 1. The Backend (Python)
Define your backend logic using decorators. ForgeDesk handles the asynchronous routing and thread pool management underneath.

```python
# src/main.py
from forge import ForgeApp
import platform

app = ForgeApp()

@app.command
def fetch_system_data(username: str) -> dict:
    """Fetch system stats to display on the UI."""
    return {
        "message": f"Welcome back, {username}!",
        "os": platform.system(),
        "status": "ready"
    }

if __name__ == "__main__":
    app.run()
```

### 2. The Frontend (TypeScript / React)
Call your Python commands natively from your frontend code using our typed NPM package.

```tsx
import { invoke } from "@forgedesk/api";
import { useState, useEffect } from "react";

export default function App() {
  const [data, setData] = useState(null);

  useEffect(() => {
    invoke("fetch_system_data", { username: "Admin" }).then(setData);
  }, []);

  return (
    <div>
      <h1>{data?.message}</h1>
      <p>OS: {data?.os}</p>
    </div>
  );
}
```

---

## <img src="https://api.iconify.design/lucide/layers.svg" width="28" height="28" align="top" /> Core Features

### 26+ Built-in APIs
- **File System** — Secure file operations with scope validation
- **Dialogs** — Native open/save/folder/message dialogs
- **Clipboard** — Read/write text, HTML, and images
- **Shell** — Execute commands with stdout streaming
- **Notifications** — Desktop toast notifications
- **Menus** — Native application and context menus
- **System Tray** — Tray icons with menus
- **Global Shortcuts** — System-wide keyboard shortcuts
- **Auto-Updates** — Ed25519 signed updates with delta patching
- **Keychain** — OS-native secure credential storage
- **Screen** — Monitor info, DPI, cursor position
- **Power** — Battery state, suspend/resume events
- **Deep Linking** — Custom protocol handlers (`myapp://`)
- **WebSocket** — Real-time bidirectional communication
- **And more...**

### 20+ Built-in Plugins
- **AI/ML** — OpenAI, ONNX Runtime, local LLM (llama.cpp)
- **Database** — SQLite, PostgreSQL, MongoDB
- **Crypto** — Hashing, encryption, signatures
- **Network** — HTTP client, REST API helpers
- **File Watch** — Real-time file change detection
- **Scheduler** — Cron-like task scheduling
- **i18n** — Internationalization support
- **Theme** — Light/dark mode management
- **And more...**

---

## <img src="https://api.iconify.design/lucide/gauge.svg" width="28" height="28" align="top" /> Performance

| Metric | ForgeDesk | Electron |
|--------|-----------|----------|
| **Binary Size** | 20-30MB | 150MB+ |
| **RAM (Idle)** | ~30MB | ~100MB |
| **RAM (Active)** | ~50MB | ~300MB |
| **Startup Time** | <1s | 2-5s |
| **IPC Latency** | <1ms | 5-10ms |

---

## <img src="https://api.iconify.design/lucide/shield.svg" width="28" height="28" align="top" /> Security

- **Capability System** — Enable/disable APIs per configuration
- **Scope Validation** — Path and URL access control with glob patterns
- **IPC Security** — Command validation, size limits, error sanitization
- **Code Signing** — macOS notarization + Windows Authenticode
- **Ed25519 Signatures** — Cryptographic update verification

---

## <img src="https://api.iconify.design/lucide/book-open.svg" width="28" height="28" align="top" /> Documentation

- **[API Reference](API.md)** — Complete API documentation
- **[Architecture](ARCHITECTURE.md)** — System design and internals
- **[Contributing](CONTRIBUTING.md)** — How to contribute

---

## <img src="https://api.iconify.design/lucide/test-tube.svg" width="28" height="28" align="top" /> Testing

```bash
# Python tests (634 tests)
uv run pytest -v

# Rust tests
cargo test --all-features

# E2E integration tests
uv run pytest tests/test_e2e_lifecycle.py -v

# With coverage
uv run pytest --cov=forge --cov-report=html
```

---

## <img src="https://api.iconify.design/lucide/building.svg" width="28" height="28" align="top" /> Building

```bash
# Development build
maturin develop

# Release build
maturin build --release

# Platform-specific builds
maturin build --release --target x86_64-unknown-linux-gnu
maturin build --release --target x86_64-pc-windows-msvc
maturin build --release --target universal2-apple-darwin

# Package installers
forge build --format appimage  # Linux
forge build --format dmg       # macOS
forge build --format nsis      # Windows
```

---

## <img src="https://api.iconify.design/lucide/git-branch.svg" width="28" height="28" align="top" /> CI/CD

ForgeDesk includes complete GitHub Actions workflows:

- **ci.yml** — Rust (clippy, fmt, test), Python (ruff, pytest), Node (build)
- **release-matrix.yml** — Cross-platform release builds with artifact generation
- **publish-python.yml** — PyPI wheel and sdist publishing (triggered on release)
- **publish-npm.yml** — NPM package publishing (triggered on release)
- **signing-validation.yml** — Code signing verification

> **Note:** Registry publishing to PyPI and NPM is performed automatically when a GitHub Release is published. The `release-matrix.yml` workflow only generates platform-specific build artifacts and does not publish to registries.

---

## <img src="https://api.iconify.design/lucide/code.svg" width="28" height="28" align="top" /> Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React, Vue, Svelte, Next.js, Astro |
| **IPC** | msgspec JSON, WebSocket, HTTP |
| **Backend** | Python 3.14+ (NoGIL), PyO3 |
| **Core** | Rust (Tao, Wry, Tokio) |
| **Build** | Maturin, Nuitka, Vite |
| **Signing** | Ed25519, macOS notarization, Windows Authenticode |

---

## <img src="https://api.iconify.design/lucide/file-text.svg" width="28" height="28" align="top" /> License

ForgeDesk is released under the [MIT License](LICENSE).

---

<div align="center">
  <strong>Built with ❤️ by the ForgeDesk Team</strong>
</div>
