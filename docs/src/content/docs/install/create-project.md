---
title: Create Project
description: Create and run your first ForgeDesk application.
---

## Scaffold a New App

```bash
forge create my-app --template plain
cd my-app
```

## Start Development

```bash
forge dev
```

This launches your native window with hot reload enabled.

## Build Release Artifacts

```bash
forge build
```

## Use Frontend Framework Templates

If you want a richer frontend setup:

```bash
forge create my-app --template react
```

or use the npm ecosystem:

```bash
npm create @forgedesk/create-forge-app@latest
```

## Continue

- [Project architecture](../architecture/)
- [API reference](../api-reference/)
