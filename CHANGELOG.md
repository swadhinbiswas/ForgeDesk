# Changelog

All notable changes to Forge Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-04-24

### Added

#### Production Readiness
- **Build Size Optimization** — Enhanced Nuitka configuration with 30+ aggressive `--nofollow-import-to` flags, post-build `strip_assets()` method (20-40% reduction), and `analyze_size()` method for optimization suggestions
- **Delta Updater** — Binary diff/patch updates using bsdiff, reducing update size from 30-50MB to 1-5MB with SHA-256 hash verification
- **E2E Integration Tests** — 45 comprehensive end-to-end tests covering app initialization, IPC bridge, event system, state management, window management, scope validation, error recovery, and router
- **Knowledge Graph** — AI-readable codebase analysis at `.understand-anything/knowledge-graph.json` (1327 nodes, 998 edges, 12 layers, 12 tour steps)

#### CI/CD & Governance
- **Optimized CI Pipeline** — Complete rewrite with Python 3.14 matrix, Cargo/uv/npm caching, concurrency control, CodeQL security scanning, dependency audit, and version alignment gate
- **Optimized Release Pipeline** — Pre-flight validation, multi-platform wheel builds, SHA-256 checksums, PyPI/NPM verification, rich GitHub Release notes
- **Branch Protection Rules** — Comprehensive `BRANCH_PROTECTION.md` with main/release branch rules, required status checks, merge strategy, and commit message standards
- **CODEOWNERS** — Automatic review assignment by component (Rust, Python, Frontend, DevOps, Docs, Security)
- **Dependabot** — Automated dependency updates for pip, Cargo, npm, and GitHub Actions
- **PR Template** — Structured pull request template with checklist
- **Issue Templates** — Bug report and feature request YAML forms
- **Security Policy** — Updated `SECURITY.md` with reporting timeline, disclosure policy, and security features

#### Documentation
- **API Reference** — Complete `API.md` with all 26+ APIs and 20+ plugins documented
- **Architecture Guide** — `ARCHITECTURE.md` with system overview, data flow, components, thread model, and extension points
- **Contributing Guide** — `CONTRIBUTING.md` with dev setup, coding standards, testing, and PR process
- **Updated README** — Production-ready with performance comparison, security features, and tech stack

#### Infrastructure & Workflow
- **Enterprise CI/CD Pipelines** — implemented full GitHub Actions matrices (`ci.yml` and `publish.yml`) for Rust/Python/Node multi-platform testing, Maturin compilation, and automatic PyPI/npm publishing securely via OIDC.
- **Astro-Style CLI UI** — entirely redesigned interactive scaffolding UI (`forge create`) using `questionary` and `rich`, themed identically to create-astro's beautiful prompts.
- **Iconify SVGs** — modernized documentation by replacing static unicode emojis with crisp, dynamic SVG icons throughout styling.
- **Production Governance** — authored formal branching strategies and deployment workflows via `PRODUCTION_BRANCH_RULES.md` and `RELEASE_PLAN_v3.md`.


#### Architecture
- **Python 3.14+ NoGIL/free-threaded** support — true parallel command execution
- **Modular Rust runtime** — decomposed `lib.rs` into `window/`, `platform/`, `events.rs`
- **PyO3 0.28** with free-threaded Python interop
- **22 API modules** — filesystem, shell, dialog, clipboard, notifications, tray, menu, system, screen, shortcuts, lifecycle, keychain, deep links, autostart, power, printing, drag-drop, window state, OS integration, serial, updater
- **20 builtin plugins** — database, crypto, i18n, themes, file watching, network, scheduler, telemetry, auth, archive, compression, cloud sync, media, memory cache, registry, serialization, fs tools, hardware, AI/ML
- **WebSocket client API** — persistent server connections with auto-reconnect
- **Background task system** — one-shot, persistent, and interval tasks with NoGIL parallelism
- **Streaming IPC / event channels** — push multiple messages per invoke for progress, data streams
- **HTTP client API** — full HTTP client exposed to JS SDK with download/upload progress
- **Cross-window messaging** — window-to-window event bus via Python backend
- **Content Security Policy** — auto-injected CSP headers for XSS protection

#### IPC Bridge
- Protocol versioning with `v1.0` envelope format
- Correlation IDs for request tracing
- `msgspec`-based strict payload validation
- Circuit breaker for automatic error recovery
- Rate limiting (calls/second)
- Error sanitization (strips filesystem paths)
- Request size limits (10MB max)

#### Security
- Capability-gated API access per window
- Path-scoped filesystem permissions (fnmatch glob patterns)
- Command allow/deny lists with strict mode
- Origin validation for WebView requests
- Window-scoped ACLs

#### Window Management
- Multi-window support with label-based routing
- Window state persistence (position, size, maximized)
- Native vibrancy effects (macOS/Windows)
- Window positioner (center, tray-anchor, screen-edge)

#### Lifecycle
- Close-to-tray support — minimize to system tray on close
- `on_ready` / `on_close` lifecycle hooks
- Crash reporter with structured error codes
- Support bundle export for diagnostics

#### CLI
- `forge create` — project scaffolding with plain, react, vue, svelte templates
- `forge dev` — hot reload with `watchfiles`
- `forge build` — production build via maturin/nuitka
- `forge sign` — macOS codesign/notarization, Windows signtool
- `forge release` — release manifest generation
- `forge doctor` — environment validation

#### Packaging
- macOS `.app` bundles with notarization
- Windows NSIS installers with code signing
- Linux AppImage generation
- Auto-updater with ed25519-signed manifests

#### Frontend SDK
- `window.__forge__` API with typed namespaces: `fs`, `clipboard`, `dialog`, `app`, `menu`, `tray`, `notifications`, `deepLink`, `runtime`, `updater`, `window`, `ws`, `http`, `tasks`, `channel`
- Dual transport: native IPC (desktop) + WebSocket (web mode)

### Changed
- Renamed PyPI package to `forgedesk`
- npm packages scoped under `@forgedesk/`
- Thread pool uses NoGIL-aware `ThreadPoolExecutor`
- Domain changed to `forgedesk.eu.cc`

### Fixed
- Fixed `error TS18003` in NPM workspace builds for API stub generation
- Fixed interactive CLI prompts hanging in CI/headless environments by properly piping offline arguments
- Removed dangling debug scripts and obsolete testing files from root directory
- Fixed mismatched `unsafe` blocks in `native_window.rs`
- WebKitGTK Wayland compositor crash on Linux
- CLI complex template absolute import paths
- Python linting issues (111 auto-fixed with ruff)

## [2.0.2] - 2024-05-31

### Fixed
- Fixed WebKitGTK Wayland compositor crash on Linux by disabling compositing mode automatically
- Fixed absolute import paths in the CLI complex template
- Renamed PyPI package to `forgedesk` and fixed metadata

## [1.0.0] - 2024-01-01

### Added

#### Core Framework
- `ForgeApp` class with `@app.command` decorator for exposing Python to JavaScript
- IPC Bridge for bidirectional Python-JavaScript communication
- Event system with `app.emit()` and `window.__forge__.on()`
- Window manager with full API for controlling window properties
- Configuration loader for `forge.toml` with validation

#### Built-in APIs
- **File System API** (`forge.fs`): read, write, exists, list, delete, mkdir
- **Dialog API** (`forge.dialog`): open_file, save_file, message dialogs
- **Clipboard API** (`forge.clipboard`): read, write clipboard content
- **System API** (`forge.app`): version, platform, info, exit
- **Tray API** (`forge.tray`): system tray icon and menu (optional)

#### CLI
- `forge create` - Scaffold new projects with templates (plain, react, vue, svelte)
- `forge dev` - Development mode with hot reload
- `forge build` - Build production binaries with PyInstaller
- `forge info` - Display system and project information

#### Security Features
- Command name validation (whitelist pattern)
- Path traversal prevention in file system API
- Input validation and sanitization
- Error message sanitization to prevent information leakage
- XSS prevention in event data
- Request size limits to prevent DoS

#### Templates
- Plain HTML/CSS/JS template
- React template with Vite
- Vue 3 template with Vite
- Svelte template with Vite

#### Examples
- **Hello Forge** - Minimal demo validating IPC functionality
- **Forge Notes** - Note-taking app demonstrating file system API

### Changed

- All API methods now have proper type hints
- Improved error messages with sanitization
- Enhanced documentation with security best practices

### Fixed

- Path traversal vulnerability in FileSystemAPI
- XSS vulnerability in event data emission
- Race condition in async command execution
- CLI template file copying for binary files
- Missing API command registrations

### Security

- Added SECURITY.md with vulnerability reporting process
- Added comprehensive security tests
- Implemented defense-in-depth for file operations
- Added null byte injection prevention
- Implemented symlink resolution and validation

## [3.0.5] - 2026-05-13

### Added
- Full mypy type annotation coverage across the core framework (153 type errors resolved)
- Type annotations for all API modules, builtins, CLI, and internals
- Type stubs for `requests` and `pyserial` dependencies

### Changed
- Bumped version to 3.0.5

### Fixed
- Resolved 1,385+ ruff lint issues across the entire codebase
  - Modernized type annotations (UP006, UP035, UP045)
  - Fixed import sorting (I001) across all modules
  - Removed unused imports (F401) and unused variables (F841)
  - Replaced `print()` calls with proper logging (T201)
  - Fixed exception chaining with `raise ... from err` (B904)
  - Fixed naming conventions (N805, N806, N815)
  - Fixed bare `except` and blind exception assertions (E722, B017)
  - Fixed async file operations (ASYNC230, ASYNC240)
  - Removed trailing whitespace and blank line whitespace (W291, W293)
- Formatted all 211 Python files with `ruff format` for consistent style
- Fixed 3 Rust clippy warnings:
  - Replaced `.map_or(false, ...)` with `.is_some_and(...)`
  - Replaced manual string stripping with `.strip_prefix()`
  - Added `#[allow(clippy::too_many_arguments)]` for PyO3 constructor
- Formatted all Rust files with `cargo fmt`
- Fixed invalid `# noqa` directive in `forge/channels.py`
- Fixed missing `json` import in `forge/bridge.py`
- Fixed duplicate module name conflict in example apps
- Fixed `ForgeApp.command` redefinition warning
- Fixed untracked `examples/complex_ai_app/` directory

### Infrastructure
- Migrated ruff linter config to `[tool.ruff.lint]` sub-section (deprecation fix)
- Added mypy exclude patterns for examples, docs, templates
