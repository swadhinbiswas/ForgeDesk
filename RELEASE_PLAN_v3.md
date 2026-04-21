# ForgeDesk 3.0.0 - Release & Deployment Plan

This document outlines the rigorous, step-by-step strategy for the official `v3.0.0` release of ForgeDesk. It covers package compilation, cross-platform binary builds, NPM publishing, PyPI publishing, and deployment verifications.

## 1. Pre-Release Validation & Quality Checks
- [ ] **Test Coverage**: Run the complete `pytest` suite locally and ensure 100% pass rate.
- [ ] **Cross-Platform Compilation checks (Rust)**:
  - Ensure the Rust backend (`Cargo.toml` and PyO3 modules) compiles warnings-free on Windows, macOS, and Linux targets.
  - Run `cargo test` in the `src/` directory.
- [ ] **CLI Scaffolding E2E**:
  - Run `forge create E2E-TEST` and simulate selecting every UI framework configuration (React, Next.js, Astro, Vue, Svelte).
  - Verify `npm install`, `pnpm install`, and `bun install` complete successfully.
  - Assert that Tailwind CSS successfully bridges with Vite builds.
- [ ] **Version Bump Validation**:
  - `pyproject.toml` bumped to `3.0.0`.
  - `Cargo.toml` bumped to `3.0.0`.
  - All Node packages (`packages/api/package.json`, `packages/vite-plugin/package.json`, etc.) bumped to `3.0.0`.

## 2. Publish Node Ecosystem (NPM Space)
Publishing the frontend bridge APIs first ensures that when users run the newly published `forge create`, the NPM dependencies actually exist in the registry.

- **Working Directory**: `/packages/`
- [ ] Publish `@forgedesk/api`: `cd packages/api && npm run build && npm publish --access public`
- [ ] Publish `@forgedesk/vite-plugin`: `cd packages/vite-plugin && npm run build && npm publish --access public`
- [ ] Publish `create-forge-app`: `cd packages/create-forge-app && npm run build && npm publish --access public`

## 3. Publish Python Framework & Binaries (PyPI)
Because ForgeDesk heavily integrates optimized Rust binaries (NoGIL ready), `maturin` forms the core of the distribution architecture.

- [ ] **Mac Build (Arm64/x86_64)**: Run `maturin build --release --target universal2-apple-darwin`
- [ ] **Windows Build (x64)**: Run `maturin build --release --target x86_64-pc-windows-msvc`
- [ ] **Linux Build (x64-gnu)**: Run `maturin build --release --target x86_64-unknown-linux-gnu`
  *(Note: Official CI/CD pipelines will handle this automatically using `cibuildwheel` on GitHub Actions)*
- [ ] **Upload to PyPI**: Execute `twine upload target/wheels/*` or `maturin publish`.

## 4. Documentation & Post-Release
- [ ] **Deploy Docs**: Trigger Vercel / Netlify build for the `docs/` Astro website.
- [ ] **GitHub Release**:
  - Tag `origin main` as `v3.0.0`.
  - Create a formalized GitHub Release listing major features (Python 3.14 NoGIL, Interactive Tailwind Scaffolding, Shadcn integration).
- [ ] **Social Rollout**: Announce on Twitter/X, Reddit, and Discord. Ensure the beautiful UI terminal recordings are embedded in the tweets.

## 5. Hotfix Protocol
In the event of a breaking bug in v3:
- Critical fixes branch off `hotfix/v3.0.X`.
- No direct pushes. Requires formal PR against `main`.
- Bump patch version (e.g., `3.0.1`), rebuild, and automate deployment through GitHub Actions.
