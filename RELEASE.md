# Release Publishing Guide

## Python package (PyPI)

Forge publishes the Python runtime as `forge-framework`.

### Requirements
- Python 3.14
- Rust toolchain
- PyPI Trusted Publishing configured for the repository
- Project name reserved on PyPI

### Manual local build

```bash
python -m pip install maturin build twine
python -m maturin build --release --out dist
python -m build --sdist --outdir dist
python -m twine check dist/*
```

### Automated publish
- Workflow: [.github/workflows/publish-python.yml](.github/workflows/publish-python.yml)
- Trigger: GitHub Release `published`
- Auth model: PyPI Trusted Publishing via GitHub OIDC

## Node packages (npm)

Forge publishes these npm packages:
- `@forge/api`
- `@forge/cli`
- `@forge/vite-plugin`
- `create-forge-app`

### Requirements
- Package names reserved on npm
- `NPM_TOKEN` configured in repository secrets
- Scoped packages published as public

### Manual local dry-run

```bash
cd packages/api && npm pack
cd ../cli && npm pack
cd ../vite-plugin && npm pack
cd ../create-forge-app && npm pack
```

### Automated publish
- Workflow: [.github/workflows/publish-npm.yml](.github/workflows/publish-npm.yml)
- Trigger: GitHub Release `published`
- Auth model: npm token + provenance

## Pre-publish checklist

- Run `cargo check`
- Run `pytest -q tests/test_cli.py tests/test_app.py tests/test_config.py`
- Run `pytest -q tests/test_release_artifacts.py tests/test_release_branch_gate.py tests/test_signing_helpers.py tests/test_smoke_installers.py tests/test_version_alignment.py`
- Run package/release validation workflows
- Confirm release branch policy is satisfied for protected CI paths
- Confirm installer smoke tests pass for the target platform matrix
- Confirm `forge doctor --output json` succeeds in the release workspace
- Confirm `python scripts/ci/verify_version_alignment.py --workspace-root . --json` succeeds
- Confirm `python scripts/ci/verify_release_artifacts.py --build-result build-result.json` succeeds on a representative release payload
- Confirm version numbers match across:
  - [pyproject.toml](pyproject.toml)
  - [forge_cli/__init__.py](forge_cli/__init__.py)
  - `packages/*/package.json`
- Confirm package names are available and ownership is configured
- Confirm PyPI and npm credentials/trusted publishing are configured

## Current publish readiness

### Ready now
- Python package build metadata exists in [pyproject.toml](pyproject.toml)
- npm package manifests exist under [packages](packages)
- automated publish workflows now exist
- release manifest verification and branch gating helpers now exist
- installer smoke-test helpers now exist
- signing helper selectors now exist for Windows and macOS validation paths
- reusable version-alignment helper now exists for publish workflows
- v3.0.6 hardening pass (security, correctness, NoGIL safety) merged

### Still required before first public publish
- replace placeholder project email/URLs if needed
- confirm final GitHub org/repo and package ownership
- reserve package names on PyPI/npm if not already reserved
- run one test release to TestPyPI and npm dry-run locally or in CI

## v3.0.6 release

See [RELEASE_NOTES_v3.0.6.md](RELEASE_NOTES_v3.0.6.md) for the full
release notes. Summary:

- **Security:** custom protocol path traversal closed, updater
  forced to HTTPS with private-IP rejection, WebSocket origin
  allowlist hardened, browser opener restricted to safe URL
  schemes, PKCE store + cloud sync path containment added.
- **Correctness:** updater rewritten with mandatory signature
  verification, several attribute-name and import bugs fixed in
  the Python framework, CLI rmtree / WiX UpgradeCode / .deb AR
  archive / Nuitka `--linux-icon` all hardened.
- **NoGIL safety:** every shared in-memory dict now lock-protected;
  `forge.memory` exposes a locked `put`/`get`/`take` API used by
  both the Python writer and the Rust `forge-memory://` protocol
  handler.
