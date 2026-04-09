# @forgedesk/vite-plugin

Vite integration for Forge frontends.

## Requirements

- Forge runtime embedded in a Python 3.14+ free-threaded app
- Vite 5+

## Install

```bash
npm install -D vite @forgedesk/vite-plugin
```

## Usage

```js
import { defineConfig } from "vite";
import { forgeVitePlugin } from "@forgedesk/vite-plugin";

export default defineConfig({
  plugins: [forgeVitePlugin()],
});
```

The plugin injects `forge.js` into `index.html` and exposes `__FORGE_DEV_SERVER_URL__` at build time.
