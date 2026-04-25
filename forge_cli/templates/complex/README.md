# {{PROJECT_NAME}}

A complex Forge desktop application with modular architecture.

## Project Structure

```
{{PROJECT_NAME}}/
├── src/
│   ├── main.py              # App entry point
│   ├── config.py            # Configuration
│   ├── handlers/            # IPC command handlers
│   │   ├── __init__.py
│   │   └── system.py
│   ├── services/            # Business logic
│   │   ├── __init__.py
│   │   └── system.py
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

## Architecture

This template demonstrates separation of concerns:

- **Handlers** (`src/handlers/`): Define IPC routes exposed to frontend
- **Services** (`src/services/`): Contain business logic and data processing
- **Config** (`src/config.py`): Centralized configuration

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
| `analyze_data` | `{payload: string}` | Processes data via service layer |

## Frontend

```jsx
import { invoke } from "@forgedesk/api";

const result = await invoke("greet", { name: "Complex" });
```

## Learn More

- [Forge Docs](https://forge-framework.dev/docs)
