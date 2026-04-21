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

```typescript
// src/frontend/App.tsx
import { invoke } from "@forgedesk/api";
import { useEffect, useState } from "react";

export default function App() {
    const [sysData, setSysData] = useState<{message: string, os: string}>();

    useEffect(() => {
        async function loadData() {
            const data = await invoke("fetch_system_data", { username: "Developer" });
            setSysData(data);
        }
        loadData();
    }, []);

    return (
        <div className="p-8 bg-slate-900 text-white min-h-screen">
            <h1 className="text-3xl font-bold">{sysData?.message}</h1>
            <p className="mt-4 text-emerald-400">Running on: {sysData?.os}</p>
        </div>
    );
}
```

---

## <img src="https://api.iconify.design/lucide/package.svg" width="24" height="24" align="top" /> The Ecosystem

ForgeDesk is highly modular to ensure a separation of concerns and a fast developer experience:

- **<img src="https://api.iconify.design/logos/python.svg" width="20" height="20" align="top" /> PyPI Packages**: 
  - `forgedesk`: The core application framework, CLI, Backend Runtime, and PyO3/Rust WebView integrations.
- **<img src="https://api.iconify.design/lucide/globe.svg" width="20" height="20" align="top" /> NPM Packages**: 
  - `@forgedesk/api`: The frontend IPC bindings for communicating with Python.
  - `@forgedesk/vite-plugin`: Seamless Vite integration, ensuring frontend Hot Module Replacement (HMR) works perfectly inside the desktop window during development.
  - `create-forge-app`: Node-centric initializers for bootstrapping applications directly via `npx` or `bunx`.

---

## <img src="https://api.iconify.design/lucide/shield-check.svg" width="28" height="28" align="top" /> Enterprise Ready

ForgeDesk v3.0.0+ introduces full enterprise-level CI/CD and security rules. If you are examining our codebase or planning to contribute, please review our internal protocols:

- [Production Branch Rules & Engineering Strategy](PRODUCTION_BRANCH_RULES.md)
- [Official Release & Deployment Plan](RELEASE_PLAN_v3.md)
- [Security Protocol](SECURITY.md)

---

## <img src="https://api.iconify.design/lucide/handshake.svg" width="28" height="28" align="top" /> Contributing

We love contributions! ForgeDesk is built by the community, for the community. To run the framework locally for development:

```bash
# Clone the repository
git clone https://github.com/swadhinbiswas/ForgeDesk.git
cd ForgeDesk/forge-framework

# Create a virtual environment using uv
uv venv
source .venv/bin/activate

# Install the package in editable mode with development dependencies
uv pip install -e ".[dev]"

# Run the test suite
pytest
```

## <img src="https://api.iconify.design/lucide/file-text.svg" width="28" height="28" align="top" /> License

ForgeDesk is open-source software licensed under the **MIT License**. See the [LICENSE](LICENSE) file for more information.
