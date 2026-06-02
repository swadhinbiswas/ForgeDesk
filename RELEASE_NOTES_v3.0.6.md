# Forge Framework v3.0.6 — Hardening & Correctness

**Release date:** 2026-06-03
**Type:** Patch (security + bug fixes, no breaking API changes)
**Upgrade recommendation:** All 3.0.x users should upgrade.

This release closes several security, correctness, and NoGIL-safety
issues uncovered during a full audit of the Rust core, Python
framework, and CLI. **No public API was removed**; only behaviour
that was clearly unsafe or broken has been changed.

---

## Highlights

### Security

- **Custom protocol path traversal** closed in `forge://` —
  the Rust `forge://`, `forge-asset://`, and `forge-memory://`
  protocol handlers now canonicalise the resolved path and refuse
  any response whose canonical form escapes the project base
  directory.
- **Updater hardened against SSRF** — manifest and artifact
  downloads are HTTPS-only, TLS 1.2 minimum, and any host that
  resolves to a loopback / private / link-local / multicast /
  reserved IP is rejected. `file://` paths are confined to the
  application base directory.
- **WebSocket origin allowlist** no longer uses `startswith` —
  `wss://api.example.com.evil.com` can no longer masquerade as
  `wss://api.example.com`. Origins are now matched on scheme +
  host + optional port.
- **Browser opener URL allowlist** — `webbrowser.open` is now
  restricted to `http`, `https`, `mailto`, `tel`, and `sms`.
  `file://`, `javascript:`, `data:`, and similar schemes are
  rejected to prevent local-file disclosure from the JS frontend.
- **Argument injection hardening** for `xdg-open` and macOS
  `open` — leading-`-` paths are prefixed with `./` and a `--`
  separator is passed so paths cannot be reinterpreted as flags.
- **PKCE store** is now lock-protected with a 600 s TTL.
- **Cloud sync upload** resolves against `app.config.get_base_dir()`
  and refuses any path that escapes it.

### Correctness

- **Updater** rewritten end-to-end: signature verification is
  mandatory, the bsdiff patch buffer is sized from the u64 LE
  header in the patch bytes (with a 1 GiB cap), and the
  post-patch restart no longer races the `NamedTempFile` guard
  with `self_replace`.
- **Serial API** no longer crashes on a missing `from forge.events
  import emit`; it now holds the app reference and serialises
  access to its connection list.
- **LLM-local task** uses the public `tasks.start` API and
  respects the cancellation event.
- **Channels** correctly pass `target_label` through to
  `evaluate_script` so cross-window events reach the right window
  instead of broadcasting to all of them.
- **Window manager API** passes the window label on every proxy
  call, so secondary windows are no longer silently redirected
  to the main window.
- **Bridge async dispatch** no longer deadlocks the worker
  thread; coroutines are scheduled via
  `asyncio.run_coroutine_threadsafe(...).result(timeout=30)`
  instead of `ensure_future(...).result()`.
- **Comma-form `except`** clauses are now proper tuples across
  all eight remaining sites.
- **CLI `rmtree`** validates the target is a direct child of the
  current working directory before deleting.
- **Nuitka `--linux-icon`** is only passed on Linux, so
  cross-platform builds no longer fail on non-Linux hosts.
- **WiX `UpgradeCode`** is derived from a UUID5 of the product
  safe name when no explicit value is supplied, removing the
  literal `PUT-GUID-HERE` placeholder that WiX rejects.
- **AR archive member names** in `.deb` output now match the
  exact 16-byte names dpkg expects.
- **Provenance commit SHA** in the build report is read from
  `git rev-parse HEAD` instead of the literal placeholder
  `"abc123"`.
- **Child window position** is now honoured on all platforms.
- **Default vbox fallback** no longer panics if the GTK vbox
  cannot be obtained.

### NoGIL / free-threaded safety

- `forge/memory.py` exposes a lock-backed `put`/`get`/`take`
  API; both the Python writer path and the Rust
  `forge-memory://` protocol handler go through it.
- `forge/api/window_state.py` and `forge/api/notification.py`
  guard their in-memory state dicts/lists with
  `threading.Lock`.
- `forge/builtins/i18n.py` and `forge/builtins/database.py`
  now serialise concurrent access; the database module uses
  per-connection locks with the safe
  `check_same_thread=True` sqlite default.
- `forge/builtins/auth.py` PKCE store is lock-protected.
- `forge/events.py` correctly awaits async listeners via
  `asyncio.run(...)` when no event loop is running.

### Removed

- `fix_all.py` and `fix_manylinux.py` — both applied
  undiscriminating regex rewrites over the entire repository
  and would have silently broken unrelated code. Both are now
  deleted.

---

## Upgrade notes

There are **no breaking changes** in this release. The version
bump from 3.0.5 to 3.0.6 reflects the security content and the
newly added defensive checks.

- Application code does not need to change.
- The manifest `provenance.source_commit` value now reflects
  the real `git rev-parse HEAD` (or `"uncommitted"`); CI
  consumers that previously compared against the literal
  `"abc123"` should switch to the new value.
- The WiX `UpgradeCode` derived from a product safe name is
  stable, so existing products will continue to receive
  major-upgrade migrations as before. To preserve a previously
  hand-rolled `UpgradeCode`, pass it explicitly through the
  build configuration.

## Verification

- `cargo check` — clean, no warnings.
- `python -m py_compile` — clean on all 14 edited Python files.
- No new tests added in this pass; the changes are
  defensive/hardening and the existing test suite already
  exercises the surface.

## Contributors

This release was prepared by the Forge maintainers following a
full code audit. See `CHANGELOG.md` for the full per-file list.
