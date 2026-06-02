# Changelog

All notable changes to Forge Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.6] - 2026-06-03

### Security

- **`forge://` custom protocol** — `src/window/builder.rs` now canonicalises
  the resolved asset path and rejects responses whose canonical form
  escapes the project base directory. Previously a maliciously crafted
  URL such as `forge://app/../../../../etc/passwd` could be returned as
  a 200 OK with arbitrary file contents.
- **Updater SSRF** — `forge/api/updater.py` now forces HTTPS for both
  manifest and artifact downloads, resolves the host and rejects any
  IP in the loopback / private / link-local / multicast / reserved
  ranges, requires TLS 1.2 or higher, and confines `file://` paths
  to the application base directory.
- **WebSocket origin allowlist** — `forge/api/websocket.py` no longer
  matches patterns with `url.startswith`. Origins are now parsed with
  `urllib.parse.urlparse` and matched on scheme + host + optional port
  to prevent suffix-confusion attacks
  (`wss://api.example.com.evil.com` cannot match `wss://api.example.com`).
- **Browser opener URL scheme allowlist** — `forge/api/opener.py` and
  `forge/api/system.py` now only forward `http`, `https`, `mailto`,
  `tel`, and `sms` to `webbrowser.open`. `file://`, `javascript:`,
  `data:`, and shell-injection-bearing schemes are rejected.
- **Open-path argument defanging** — leading `-` filenames are prefixed
  with `./` and `--` separators are passed to `open`/`xdg-open` so
  paths cannot be interpreted as command-line flags.
- **OAuth PKCE store** — `forge/builtins/auth.py` now guards
  `_pkce_store` with a `threading.Lock` and purges entries older
  than 600 s, preventing verifier leakage under NoGIL.
- **Cloud-sync path containment** — `forge/builtins/cloud_sync.py`
  resolves the upload path against `app.config.get_base_dir()` and
  refuses anything that escapes, and rejects anything that is not
  a regular file.

### Fixed

- **Rust updater** — `src/updater.rs` rewritten: signature verification
  is now mandatory, downloads are HTTPS-only with a custom redirect
  policy, the bsdiff patch buffer is sized from the u64 LE header in
  the patch bytes (capped at 1 GiB), and the post-patch restart uses
  `Command::spawn()` followed by `std::process::exit(0)` so the
  `NamedTempFile` guard no longer races with `self_replace`.
- **Window builder response unwraps** — `forge-asset://` and
  `forge-memory://` responses no longer `unwrap()` a `Result` from
  the PyO3 call; missing entries are converted into 404 responses.
- **Default vbox fallback** — `src/native_window.rs` no longer
  panics on `default_vbox()`; it now returns a `Result` with a
  descriptive error.
- **Serial API** — `forge/api/serial.py` no longer imports a
  non-existent `forge.events.emit`; it now holds the app reference
  and serialises access to `_connections` with a `threading.Lock`.
- **LLM-local task** — `forge/builtins/llm_local.py` now uses
  `self._app.tasks.start(name, _stream_task)` and respects the
  supplied `cancel_event` instead of the removed `tasks.spawn`.
- **Channels target** — `forge/channels.py` now passes
  `target_label` through to `proxy.evaluate_script`, fixing
  cross-window event delivery that was previously broadcasting to
  every window.
- **Window manager API** — `forge/window.py` `WindowManagerAPI`
  proxy methods now pass the window label on every call so they
  reach the right window rather than defaulting to `"main"`.
- **Dialog capability name** — `forge/api/dialog.py` now declares
  the `"dialogs"` capability to match the `Permissions.dialogs`
  table.
- **Positioner attribute** — `forge/api/positioner.py` now reads
  `app.screen` instead of the non-existent `app._screen_api`.
- **Async bridge wait** — `forge/bridge.py` no longer deadlocks
  the worker thread by calling `asyncio.ensure_future(...).result()`;
  it now schedules via
  `asyncio.run_coroutine_threadsafe(...).result(timeout=30)`.
- **Comma-form except clauses** — all eight remaining
  `except A, B:` statements in `forge_cli/main.py`,
  `forge/api/fs.py`, `forge/builtins/archive.py`,
  `forge/builtins/file_watch.py`, `examples/forge_notes/src/main.py`,
  and `tests/test_fs_api.py` are now `except (A, B):`.
- **CLI rmtree** — `forge_cli/main.py` validates that the target
  is a direct child of the current working directory before
  deleting, rejecting empty names, `..`, `/`, and NUL bytes.
- **VERSION drift** — `forge_cli/main.py`, `pyproject.toml`,
  `Cargo.toml`, `forge/__init__.py`, `forge_cli/__init__.py`,
  and the four `packages/*/package.json` files all moved to
  `3.0.6` together.
- **WiX UpgradeCode** — `forge_cli/manifests.py` now derives a
  deterministic UUID5 from the product safe name when no explicit
  `upgrade_code` is supplied, so the installer no longer ships
  with the literal placeholder `PUT-GUID-HERE` that WiX rejects.
- **`.deb` AR member names** — `forge_cli/main.py` `_write_ar_archive`
  now writes the exact 16-byte member names dpkg expects
  (`debian-binary`, `control.tar.gz`, `data.tar.*`) without the
  BSD-ar trailing-slash convention and rejects names that would
  overflow the field.
- **Nuitka `--linux-icon`** — only passed on Linux so cross-platform
  builds no longer fail when the flag is forwarded to macOS or
  Windows Nuitka.
- **Provenance commit SHA** — the build report's
  `provenance.source_commit` is now read from `git rev-parse HEAD`
  (or `"uncommitted"`) instead of the literal placeholder
  `"abc123"`.
- **Child-window position** — `src/native_window.rs` now honours
  the `x`/`y` fields in `WindowDescriptor` (via
  `WindowBuilder::with_position` on Windows/macOS and
  `gtk_window.move_` after build on Linux).
- **Window state cache** — `forge/api/window_state.py` now uses a
  separate `_cache_lock` so the in-memory state dict is no longer
  mutated from event-callback threads without serialisation.
- **Notification history** — `forge/api/notification.py` now
  protects `_history` with a `threading.Lock` and preserves list
  identity when trimming the deque.
- **I18n bundles** — `forge/builtins/i18n.py` now guards
  `_bundles` with a `threading.Lock` for NoGIL safety.
- **Event async fallback** — `forge/events.py` now awaits async
  listeners via `asyncio.run(...)` when no event loop is running,
  so coroutine listeners are no longer silently dropped.
- **forge.memory registry** — `forge/memory.py` now exposes
  `put`/`get`/`take` helpers backed by a `threading.Lock`;
  `bridge.py` and the `forge-memory://` Rust protocol handler
  go through the helper so the cross-thread dict is no longer
  read and written without serialisation.

### Removed

- **`fix_all.py`** — deleted. The regex-based rewrite was
  destructive (it rewrote both `pathlib.Path.read_bytes` and
  unrelated identifiers and silently broke the build).
- **`fix_manylinux.py`** — deleted. It applied the same kind of
  glob-and-rewrite pass over the entire repository with no
  filtering, which is incompatible with the previous script.

### Verified false alarms (no change required)

- `forge/builtins/serialization.py` uses `msgpack`, not `pickle`.
- `forge/builtins/automation.py` uses `pyautogui`, no subprocess.
- `forge/builtins/telemetry.py` is already lock-protected.
- `forge/builtins/scheduler.py` timer fires a sync IPC, not async.
- `forge/state.py` `AppState` is already fully locked.
- `forge/builtins/memory_cache.py` is already locked.

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
