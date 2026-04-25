# {{PROJECT_NAME}}

A Forge desktop application built with Svelte 5 and Python.

## Project Structure

```
{{PROJECT_NAME}}/
├── src/
│   ├── main.py              # Python backend
│   ├── backend/
│   │   └── __init__.py
│   └── frontend/            # Svelte frontend
│       ├── index.html
│       ├── main.js
│       ├── App.svelte
│       └── style.css
├── assets/
│   └── icon.png
├── forge.toml
├── package.json
├── requirements.txt
└── .gitignore
```

## Quick Start

```bash
cd {{PROJECT_NAME}}
./forge dev
./forge serve
./forge build
```

## Backend Commands

| Command | Args | Description |
|---------|------|-------------|
| `greet` | `{name: string}` | Returns a greeting |
| `get_system_info` | — | Returns OS info |
| `add_numbers` | `{a: number, b: number}` | Sum two numbers |

## Frontend

```javascript
import { invoke } from "@forgedesk/api";

const result = await invoke("greet", { name: "Svelte" });
```

## Learn More

- [Forge Docs](https://forge-framework.dev/docs)
