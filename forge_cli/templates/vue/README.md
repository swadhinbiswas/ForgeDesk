# {{PROJECT_NAME}}

A Forge desktop todo list application built with Vue 3 and Python.

## Features

- Add, toggle, and delete todos
- Filter by All / Active / Completed
- Clear all completed todos
- Vue 3 Composition API with reactivity

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

## Frontend

```javascript
import { invoke } from "@forgedesk/api";

const todos = await invoke("todo_list");
await invoke("todo_add", { text: "Learn Vue" });
```

## Learn More

- [Forge Docs](https://forge-framework.dev/docs)
