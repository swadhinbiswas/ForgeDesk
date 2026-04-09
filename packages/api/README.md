# @forgedesk/api

Typed JavaScript bindings for the Forge runtime.

## Requirements

- Forge runtime embedded in a Python 3.14+ free-threaded app

## Install

```bash
npm install @forgedesk/api
```

## Usage

```js
import forge, { invoke, isForgeAvailable } from "@forgedesk/api";

if (isForgeAvailable()) {
  const version = await forge.app.version();
  const state = await forge.window.state();
  const result = await invoke("greet", { name: "Forge" });
  console.log(version, state, result);
}
```

This package expects the Forge runtime to inject `window.__forge__`.
