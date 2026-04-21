# Forge Framework v3.0.0 🚀

The highly anticipated **v3.0.0** of Forge is finally here! This blockbuster release brings monumental upgrades across the entire stack, solidifying our status as the ultimate modern Python alternative for native desktop development. 

We've focused heavily on developer experience, architecture upgrades, and shipping enterprise-grade production infrastructure. 

## Highlights

### 🎨 Beautiful New CLI Experience
We've completely overhauled the `forge create` scaffolding wizard. Modeled after the beloved `create-astro`, our new CLI utilizes `questionary` and `rich` to provide a highly interactive, beautifully styled, and keyboard-friendly project creation flow.

### ⚙️ Parallelism with NoGIL Python
Forge v3.0 fully leverages **Python 3.14+ NoGIL/free-threaded** capabilities! Background tasks, bidirectional IPC channels, and network workers now execute truly in parallel without standard Python global-interpreter-lock contention. 

### 🏗️ Complete CI/CD Workflows
Enterprise teams rejoice! By popular demand, we have authored robust GitHub Action pipelines mapping end-to-end continuous integration (`ci.yml`) and automated OpenID Connect (OIDC) publishing points (`publish.yml`) directly against npm & PyPI. This provides out-of-the-box matrix verification on Windows, Linux, and macOS.

### 📖 Flawless Documentation
Through replacing static emojis with dynamic SVG icons (via [Iconify](https://iconify.design/)) alongside a sweeping restructure of architecture diagrams, our `README.md` and auxiliary docs are slick, legible, and highly informative. Furthermore, our new `PRODUCTION_BRANCH_RULES.md` provides definitive structural guidance for large teams operating Forge projects.

## Additional Changes & Fixes
- `100%` Typescript validation pass against stubs, fixing API build processes.
- Scoped all npm packages successfully beneath the `@forgedesk/` namespace to enforce brand security.
- Dropped orphaned developer artifacts to completely clean the root scaffolding workspace.
- 22 new API modules injected into `lib.rs` and the Python bridge, featuring HTTP clients and cross-window WebSocket messaging!
- Headless CLI capabilities patched: `forge create` arguments correctly parse into silent overrides.

---
### Updating to v3.0.0

Update the Python CLI system wide:
```bash
uv pip install --upgrade forgedesk
```

When building a new app, ensure your generated `package.json` receives the newest scope:
```json
  "devDependencies": {
    "@forgedesk/api": "^3.0.0",
    "@forgedesk/vite-plugin": "^3.0.0"
  }
```