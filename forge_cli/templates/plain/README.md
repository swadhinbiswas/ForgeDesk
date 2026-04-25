# {{PROJECT_NAME}}

A Forge desktop todo list application built with Python and web technologies.

## Features

- Add, toggle, and delete todos
- Filter by All / Active / Completed
- Clear all completed todos
- Thread-safe backend with real-time updates

## Project Structure

```
{{PROJECT_NAME}}/
├── src/
│   ├── main.py              # Python backend (IPC commands)
│   ├── backend/
│   │   └── __init__.py
│   └── frontend/            # Web frontend
│       ├── index.html
│       ├── main.js
│       └── style.css
├── assets/
│   └── icon.png             # App icon
├── forge.toml               # App configuration
├── package.json             # Node dependencies
├── requirements.txt         # Python dependencies
└── .gitignore
```

## Quick Start

```bash
# Navigate to project
cd {{PROJECT_NAME}}

# Start development server (desktop mode)
./forge dev

# Or start web mode
./forge serve

# Build for production
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

## Frontend

The frontend communicates with the Python backend through the `@forgedesk/api` IPC bridge.

```javascript
import { invoke } from "@forgedesk/api";

// Add a todo
await invoke("todo_add", { text: "Buy groceries" });

// List all todos
const todos = await invoke("todo_list");

// Toggle completion
await invoke("todo_toggle", { id: 1 });
```

## Configuration

Edit `forge.toml` to customize:
- Window size, title, decorations
- Permissions (filesystem, clipboard, dialogs, etc.)
- Packaging formats (AppImage, DMG, MSI, etc.)

## Learn More

- [Forge Documentation](https://forge-framework.dev/docs)
