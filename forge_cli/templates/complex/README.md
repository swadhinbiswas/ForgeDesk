# {{PROJECT_NAME}}

A complex Forge desktop todo list application with modular architecture.

## Features

- Add, toggle, and delete todos
- Filter by All / Active / Completed
- Clear all completed todos
- Modular backend: handlers/ + services/

## Architecture

This template demonstrates separation of concerns:

```
src/
├── main.py              # App entry point
├── config.py            # Configuration
├── handlers/            # IPC command handlers
│   ├── __init__.py
│   ├── todo.py          # Todo IPC routes
│   └── system.py        # System IPC routes
├── services/            # Business logic
│   ├── __init__.py
│   ├── todo.py          # Todo domain logic
│   └── system.py        # System utilities
├── backend/
│   └── __init__.py
└── frontend/            # React frontend
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
| `todo_add` | `{text: string}` | Add a new todo |
| `todo_list` | — | Get all todos |
| `todo_toggle` | `{id: number}` | Toggle completion |
| `todo_delete` | `{id: number}` | Delete a todo |
| `todo_clear_completed` | — | Remove all completed |
| `get_system_info` | — | Get OS info |
| `analyze_data` | `{payload: string}` | Process data via service |

## Learn More

- [Forge Docs](https://forge-framework.dev/docs)
