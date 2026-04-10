---
title: Troubleshooting Installation
description: Common setup issues and fixes for ForgeDesk.
---

## Python Package Not Found

If `pip install forgedesk` fails:

- Verify Python version: `python --version`
- Upgrade pip: `python -m pip install --upgrade pip`
- Try clean environment: `python -m venv .venv && source .venv/bin/activate`

## Linux WebView Crashes on Wayland

If the app exits immediately under Wayland, set:

```bash
export WEBKIT_DISABLE_COMPOSITING_MODE=1
```

Newer ForgeDesk versions set this automatically for common Linux Wayland sessions.

## Rust Toolchain Missing

```bash
rustup show
cargo --version
```

If unavailable, reinstall Rust using the command in [Prerequisites](./prerequisites/).

## Build Fails on Windows

- Confirm Visual C++ Build Tools is installed
- Confirm WebView2 runtime is available
- Open a new terminal after installation so environment variables reload
