# {{PROJECT_NAME}}

A Forge desktop application built with React and Python.

## Project Structure

```
{{PROJECT_NAME}}/
├── src/
│   ├── main.py              # Python backend (IPC commands)
│   ├── backend/
│   │   └── __init__.py
│   └── frontend/            # React frontend
│       ├── index.html
│       ├── main.jsx
│       ├── App.jsx
│       ├── App.css
│       └── index.css
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
./forge dev       # Desktop mode with hot reload
./forge serve     # Web mode
./forge build     # Production build
```

## Backend Commands

| Command | Args | Description |
|---------|------|-------------|
| `greet` | `{name: string}` | Returns a greeting |
| `get_system_info` | — | Returns OS info |
| `add_numbers` | `{a: number, b: number}` | Sum two numbers |

## Frontend

```jsx
import { invoke } from "@forgedesk/api";

const result = await invoke("greet", { name: "React" });
```

## Configuration

Edit `forge.toml` to customize window, permissions, and packaging.

## Learn More

- [Forge Docs](https://forge-framework.dev/docs)
