# @forgedesk/cli

Node wrapper for the Forge Python CLI.

## Requirements

- Python 3.14+ free-threaded runtime (`forge-framework`)
- Node.js 18+

## Install

```bash
npm install -D @forgedesk/cli
```

## Usage

```bash
npx forge create my-app --template react
npx forge dev
npx forge build
npx forge package --result-format json
npx forge sign --result-format json
```

If the Python Forge package is missing, the wrapper attempts to install `forge-framework` with `pip` unless `FORGE_SKIP_AUTO_INSTALL=1` is set.
The wrapper is intended to run against the same free-threaded Forge runtime used by the main framework.
