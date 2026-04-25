# {{PROJECT_NAME}}

A Forge desktop application built with Python and web technologies.

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

The following Python commands are exposed to the frontend via IPC:

| Command | Args | Description |
|---------|------|-------------|
| `greet` | `{name: string}` | Returns a greeting message |
| `get_system_info` | — | Returns OS, Python version, platform |
| `add_numbers` | `{a: number, b: number}` | Returns sum of two numbers |

## Frontend

The frontend is built with Vite and communicates with the Python backend
through the `@forgedesk/api` IPC bridge.

```javascript
import { invoke } from "@forgedesk/api";

const result = await invoke("greet", { name: "World" });
console.log(result); // "Hello, World! Welcome to {{PROJECT_NAME}} 🚀"
```

## Configuration

Edit `forge.toml` to customize:
- Window size, title, decorations
- Permissions (filesystem, clipboard, dialogs, etc.)
- Packaging formats (AppImage, DMG, MSI, etc.)
- Auto-updater settings

## Learn More

- [Forge Documentation](https://forge-framework.dev/docs)
- [API Reference](https://forge-framework.dev/docs/api)
