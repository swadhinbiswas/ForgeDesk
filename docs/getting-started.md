# Getting Started with Forge

Build cross-platform desktop apps with Python + Web technologies in under 5 minutes.

## Prerequisites

- **Python 3.10+** (3.14+ recommended for NoGIL performance)
- **Rust toolchain** (for the native WebView core)
- **Node.js 18+** (optional, for frontend dev server)

## Installation

```bash
pip install forge-framework
```

## Create Your First App

```bash
forge create my-app --template plain
cd my-app
```

This generates:

```
my-app/
├── forge.toml          # App configuration
├── src/
│   ├── main.py         # Python backend
│   └── frontend/       # Web frontend
│       ├── index.html
│       ├── main.js
│       └── style.css
└── assets/
    └── icon.png
```

## Write Your Backend

```python
# src/main.py
from forge import ForgeApp

app = ForgeApp()

@app.command
def greet(name: str) -> str:
    return f"Hello, {name}! 🐍"

@app.command
def add(a: int, b: int) -> int:
    return a + b

app.run()
```

## Call Python from JavaScript

```javascript
import { invoke } from "@forge/api";

// Call any registered Python command
const greeting = await invoke("greet", { name: "World" });
const sum = await invoke("add", { a: 3, b: 4 });
```

## Run in Development Mode

```bash
forge dev
```

This starts the app with:
- **Hot reload** — file changes trigger automatic restart
- **IPC inspector** — `forge dev --inspect` logs all bridge traffic

## Build for Production

```bash
forge build
```

Produces a standalone binary using Nuitka or maturin.

## What's Next?

- **[Architecture Guide](architecture.md)** — How Rust, Python, and JS layers interact
- **[Security Guide](security.md)** — Capability model, scopes, and CSP
- **[API Reference](api-reference.md)** — All built-in APIs
- **[Plugin Guide](plugins.md)** — Writing and publishing plugins
