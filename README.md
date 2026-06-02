<div align="center">
  <img src="branding/forgedesk-logo.svg" alt="ForgeDesk" width="180" />
</div>

<h1 align="center">ForgeDesk</h1>

<p align="center"><strong>A desktop application framework with a Python backend, a Rust core, and a web frontend.</strong></p>

<p align="center">
  <a href="https://pypi.org/project/forgedesk/"><img src="https://img.shields.io/pypi/v/forgedesk" alt="PyPI" /></a>
  <a href="https://www.npmjs.com/package/@forgedesk/api"><img src="https://img.shields.io/npm/v/@forgedesk/api" alt="npm" /></a>
  <a href="https://github.com/swadhinbiswas/ForgeDesk/blob/master/LICENSE"><img src="https://img.shields.io/github/license/swadhinbiswas/ForgeDesk" alt="License" /></a>
  <a href="https://github.com/swadhinbiswas/ForgeDesk/actions"><img src="https://img.shields.io/github/actions/workflow/status/swadhinbiswas/ForgeDesk/ci.yml?branch=master" alt="CI" /></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.14t-blue" alt="Python 3.14 free-threaded" />
  <img src="https://img.shields.io/badge/rust-1.83%2B-orange" alt="Rust" />
  <img src="https://img.shields.io/badge/node-20%2B-339933" alt="Node" />
  <img src="https://img.shields.io/badge/platform-windows%20%7C%20macos%20%7C%20linux-lightgrey" alt="Platforms" />
</p>

---

## What is ForgeDesk?

ForgeDesk is a framework for building cross-platform desktop applications. It pairs a **Python 3.14 free-threaded** runtime with a **Rust** core compiled to native code, and renders the UI through the operating system's webview via [`wry`](https://github.com/tauri-apps/wry) and [`tao`](https://github.com/tauri-apps/tao).

Unlike Electron, ForgeDesk does not bundle Chromium. The browser engine is the one already on the user's machine, which keeps binaries small (≈ 20–30 MB) and idle memory low (≈ 30 MB). Unlike PyWebView, the IPC layer is a purpose-built, capability-scoped bridge rather than a generic HTTP shim.

```
┌──────────────────────────────────────────────────────────────┐
│                        Webview (UI)                          │
│   React · Vue · Svelte · Next.js · Astro · vanilla JS        │
└────────────────────┬─────────────────────────────────────────┘
                     │  msgspec JSON over WebSocket / HTTP
                     ▼
┌──────────────────────────────────────────────────────────────┐
│           Rust core (forge-core) — PyO3 extension            │
│   tao (windowing) · wry (webview) · IPC router · updater    │
└────────────────────┬─────────────────────────────────────────┘
                     │  PyO3 ABI
                     ▼
┌──────────────────────────────────────────────────────────────┐
│         Python 3.14 free-threaded (NoGIL) host process       │
│   forge.app · forge.api.* · forge.builtins.* · forge.cli     │
└──────────────────────────────────────────────────────────────┘
```

## Why

- **Native webview, not Chromium.** No bundled engine, no licensing surprises, smaller download, less RAM.
- **Python-first business logic.** Heavy data work, ML inference, and integrations stay in Python where the ecosystem lives.
- **True parallelism on Python.** Free-threaded 3.14 means command handlers can run concurrently across cores.
- **Scoped, capability-based IPC.** Every command declares a capability. File and URL access are validated against explicit scopes.
- **Bring your own UI.** Works with any framework that produces a static bundle. The CLI scaffolds React, Next.js, Vue, Svelte, and Astro projects with Vite + HMR.

## Installation

```bash
pip install forgedesk        # or: uv pip install forgedesk
npm install -g @forgedesk/cli
```

Requirements: Python 3.14t (free-threaded), Node.js 20+, and a Rust toolchain (only required for building the Rust extension from source; pre-built wheels are published for the common targets).

## Quick start

```bash
# Scaffold a new project interactively
forge create my-app
cd my-app

# Install JS dependencies and start the dev server with HMR
npm install
forge dev

# Build a production binary
forge build
```

`forge create` is an interactive TUI built on `questionary` and `rich`. It prompts for:

- Project name and target directory
- UI framework (React, Next.js, Vue, Svelte, Astro, or vanilla)
- Package manager (`npm`, `pnpm`, `bun`, `yarn`)
- Optional Tailwind CSS

The generated project contains a `src/main.py` (Python entry point), a `frontend/` directory (UI bundle), and a `forge.toml` (build config). Hot reload watches both the Python source and the frontend bundle.

## Defining a backend command

```python
# src/main.py
from forge import ForgeApp

app = ForgeApp()


@app.command
def fetch_system_data(username: str) -> dict:
    """Return a greeting plus platform info for the dashboard."""
    import platform
    return {
        "message": f"Welcome back, {username}!",
        "os": platform.system(),
        "kernel": platform.release(),
    }


if __name__ == "__main__":
    app.run()
```

## Calling it from the frontend

```tsx
import { invoke } from "@forgedesk/api";
import { useEffect, useState } from "react";

type SystemData = { message: string; os: string; kernel: string };

export function Greeting({ name }: { name: string }) {
  const [data, setData] = useState<SystemData | null>(null);

  useEffect(() => {
    invoke<SystemData>("fetch_system_data", { username: name }).then(setData);
  }, [name]);

  return <h1>{data?.message ?? "Loading…"}</h1>;
}
```

The `@forgedesk/api` package provides typed wrappers around `invoke`, `listen`, window management, and the full API surface. Types are bundled.

## Architecture in one screen

| Layer | Language | Role |
|---|---|---|
| `frontend/` | TypeScript / JSX | UI bundle, served by Vite in dev, bundled in release |
| IPC bridge | `msgspec` JSON over WebSocket | Strict, fast payload validation; correlation IDs for tracing |
| `forge-core` | Rust (PyO3 extension) | Window lifecycle, webview host, IPC router, updater, tray, menus |
| `forge.app` | Python | Command registry, dependency injection, router composition |
| `forge.api.*` | Python | Filesystem, dialogs, clipboard, shell, notifications, screen, … |
| `forge.builtins.*` | Python | Database, crypto, scheduler, telemetry, i18n, cloud sync, … |
| `forge_cli` | Python | `forge create / dev / build / doctor` |

The Rust core owns the event loop and all OS resources. Python never touches `tao` or `wry` directly — it talks to the Rust side through PyO3-bound functions. This keeps the Python layer free of platform-specific code and makes the whole stack testable on any platform.

## Capabilities and security

Every command declares a capability string. The framework rejects invocations whose capability is not in the active permission set.

```toml
# forge.toml
[permissions]
allow = ["fs", "dialog", "notifications", "websocket"]

[permissions.fs]
scope = ["./data/**", "$APPDATA/**/*.json"]
max_file_size = "50MB"
```

Additional security primitives:

- **Custom protocols** (`forge://`, `forge-asset://`, `forge-memory://`) canonicalize all paths and reject responses that escape the project base.
- **URL allowlist** for the system browser — `file://` and `javascript:` are refused by default.
- **WebSocket origin allowlist** — scheme + host + optional port matching, no `startswith` confusion.
- **Updater** — HTTPS only, TLS 1.2 minimum, private/loopback/link-local IPs rejected, Ed25519 signature verification mandatory, bsdiff delta updates.
- **Path containment** — every filesystem and cloud-sync entry point resolves and checks the path against an explicit root.

## Performance

Measured on a Linux x86_64 dev box, idle, single window, simple "hello world" UI:

| Metric | ForgeDesk | Electron (reference) |
|---|---|---|
| Binary size | 22 MB | 165 MB |
| Idle RSS | 32 MB | 110 MB |
| Active RSS (after 100 IPC calls) | 48 MB | 290 MB |
| Cold start to first paint | 0.4 s | 2.1 s |
| Round-trip IPC latency (p50) | 0.6 ms | 6 ms |

Numbers will vary by platform and UI complexity; the IPC delta comes from skipping Chromium and from validating payloads with `msgspec` instead of `json.loads`.

## Project layout

```
.
├── src/                       # Rust core (forge-core, PyO3 extension)
│   ├── window/                # tao + wry bindings
│   ├── platform/              # tray, menu, notifications
│   ├── events.rs              # UserEvent routing
│   └── updater.rs             # Delta updater + signature verification
├── forge/                     # Python framework
│   ├── app.py                 # ForgeApp, command registration
│   ├── bridge.py              # msgspec IPC, correlation, error sanitisation
│   ├── channels.py            # Cross-window messaging
│   ├── events.py              # Lock-free event emitter (NoGIL safe)
│   ├── memory.py              # Shared buffer registry
│   ├── state.py               # Typed DI container
│   ├── tasks.py               # Background task manager
│   ├── api/                   # Filesystem, dialog, clipboard, …
│   └── builtins/              # Database, crypto, scheduler, …
├── forge_cli/                 # forge create / dev / build / doctor
├── packages/                  # npm SDK (@forgedesk/api, /cli, /vite-plugin, /create-forge-app)
├── tests/                     # pytest + Rust tests + e2e lifecycle
├── examples/                  # Reference apps (notes, movies, chat, complex_app)
└── .github/workflows/         # ci, release-matrix, publish-python, publish-npm
```

## Development

```bash
# Set up
git clone https://github.com/swadhinbiswas/ForgeDesk
cd ForgeDesk
uv sync                        # Python deps into .venv
maturin develop --release      # build & install the Rust extension
cd packages/api && npm install && npm run build && cd -

# Run tests
cargo test --all-features
uv run pytest -q
uv run pytest -q tests/test_e2e_lifecycle.py
```

The repo uses:

- **Rust** 1.83+ with `rustfmt` and `clippy` enforced in CI
- **Python** 3.14t, formatted with `ruff format`, linted with `ruff check`
- **TypeScript** with `tsc --noEmit` in CI
- **GitHub Actions** for CI across Linux / macOS / Windows

## Releasing

The release process is fully scripted and triggered by tagging:

```bash
# 1. Bump versions (pyproject.toml, Cargo.toml, forge/__init__.py,
#    forge_cli/__init__.py, package.json, packages/*/package.json)
# 2. Update CHANGELOG.md and RELEASE_NOTES_vX.Y.Z.md
# 3. Tag
git tag -s -a v3.0.6 -m "v3.0.6"
git push --follow-tags
gh release create v3.0.6 --title "v3.0.6" --notes-file RELEASE_NOTES_v3.0.6.md
```

Tagging triggers `publish-python.yml` (PyPI via Trusted Publishing / OIDC) and `publish-npm.yml` (npm). Signing keys are loaded from repository secrets; no long-lived tokens are checked in. See [RELEASE.md](RELEASE.md) for the full publish checklist.

## Status

v3.0.6 — production-ready. The framework is API-stable within the 3.x line; breaking changes will be announced with a 6-month deprecation window and reflected in the minor version.

| Component | Status |
|---|---|
| `forge-core` (Rust) | Stable |
| `forge` (Python) | Stable |
| `@forgedesk/api`, `@forgedesk/cli` | Stable |
| `@forgedesk/vite-plugin` | Stable |
| `@forgedesk/create-forge-app` | Stable |
| Delta updater | Stable, Ed25519-signed |
| WiX / NSIS / .deb / .dmg / AppImage packaging | Stable |

## Contributing

Bug reports and PRs are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR — it covers the commit message format, the version-alignment requirement, and the CI gates that have to pass.

Security issues: see [SECURITY.md](SECURITY.md) for the disclosure process. Please do not file public issues for vulnerabilities.

## License

[MIT](LICENSE) — Copyright (c) the ForgeDesk contributors.
