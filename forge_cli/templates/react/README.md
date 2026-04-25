# {{PROJECT_NAME}}

A Forge desktop todo list application built with React and Python.

## Features

- Add, toggle, and delete todos
- Filter by All / Active / Completed
- Clear all completed todos
- React hooks for state management

## Project Structure

```
{{PROJECT_NAME}}/
├── src/
│   ├── main.py              # Python backend
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
| `todo_add` | `{text: string}` | Add a new todo |
| `todo_list` | — | Get all todos |
| `todo_toggle` | `{id: number}` | Toggle completion |
| `todo_delete` | `{id: number}` | Delete a todo |
| `todo_clear_completed` | — | Remove all completed |
| `get_system_info` | — | Get OS info |

## Frontend

```jsx
import { invoke } from "@forgedesk/api";

const todos = await invoke("todo_list");
await invoke("todo_add", { text: "Learn React" });
```

## Learn More

- [Forge Docs](https://forge-framework.dev/docs)
