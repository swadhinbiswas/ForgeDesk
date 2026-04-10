# @forgedesk/create-forge-app

Scaffold Forge applications from npm.

## Requirements

- Python 3.14+ free-threaded runtime (`forge-framework`)
- Node.js 18+

## Usage

```bash
npx @forgedesk/create-forge-app@latest my-app -- --template react
```

If your npm client is configured to a mirror that has not synced the latest release yet, use the npm registry explicitly:

```bash
npx --registry=https://registry.npmjs.org @forgedesk/create-forge-app@latest my-app -- --template react
```

The bootstrapper delegates to the Forge Python CLI and installs `forge-framework` with `pip` when needed.
This keeps the npm starter flow aligned with the no-GIL Forge runtime.
