# Migrating from Electron to Forge

A practical comparison guide for teams moving from Electron to Forge.

## Why Migrate?

| Metric | Electron | Forge |
|--------|----------|-------|
| Binary size | ~150–200 MB | ~15–25 MB |
| RAM usage | ~150–300 MB | ~30–80 MB |
| Startup time | ~2–5 seconds | ~0.5–1 second |
| Bundled runtime | Chromium + Node.js | OS WebView + Python |
| Backend language | JavaScript/Node.js | Python |
| Security model | Process isolation | Capability-based permissions |

## Concept Mapping

### Main Process → Python Backend

**Electron:**
```javascript
// main.js
const { app, BrowserWindow, ipcMain } = require('electron');

ipcMain.handle('greet', (event, name) => {
  return `Hello, ${name}!`;
});
```

**Forge:**
```python
# src/main.py
from forge import ForgeApp

app = ForgeApp()

@app.command
def greet(name: str) -> str:
    return f"Hello, {name}!"

app.run()
```

### IPC Communication

**Electron:**
```javascript
// Renderer
const result = await window.electronAPI.greet('Alice');
```

**Forge:**
```javascript
// Frontend
import { invoke } from '@forge/api';
const result = await invoke('greet', { name: 'Alice' });
```

### Window Management

**Electron:**
```javascript
const win = new BrowserWindow({ width: 800, height: 600 });
win.loadFile('index.html');
```

**Forge** (configured in `forge.toml`):
```toml
[window]
title = "My App"
width = 800
height = 600
```

Or programmatically:
```python
app.window.create(label="settings", route="/settings", width=900, height=640)
```

### State Management

**Electron:** Manual — store in main process variables or use electron-store.

**Forge:** Built-in typed state container with auto-injection:
```python
app.state.manage(Database("sqlite:///app.db"))

@app.command
def get_users(db: Database) -> list:
    # Database auto-injected by type hint!
    return db.query("SELECT * FROM users")
```

### File System Access

**Electron:**
```javascript
const fs = require('fs');
const data = fs.readFileSync(path, 'utf8');
```

**Forge (frontend):**
```javascript
const data = await forge.fs.read(path);
```

**Forge (backend):**
```python
@app.command
def read_config() -> dict:
    with open("config.json") as f:
        return json.load(f)
```

### System Tray

**Electron:**
```javascript
const tray = new Tray('/path/to/icon.png');
tray.setContextMenu(Menu.buildFromTemplate([
  { label: 'Show', click: () => win.show() },
  { label: 'Quit', click: () => app.quit() },
]));
```

**Forge:**
```toml
# forge.toml
[permissions]
system_tray = true
```

```javascript
await forge.tray.setIcon('assets/icon.png');
await forge.tray.setMenu([
  { label: 'Show', action: 'show' },
  { label: 'Quit', action: 'quit' },
]);
```

### Notifications

**Electron:**
```javascript
new Notification({ title: 'Hello', body: 'World' }).show();
```

**Forge:**
```javascript
await forge.notifications.notify('Hello', 'World');
```

## Security Comparison

| Feature | Electron | Forge |
|---------|----------|-------|
| Process isolation | ✅ Separate processes | ❌ Single process |
| Capability gating | ❌ Everything exposed | ✅ Per-capability opt-in |
| Path scoping | ❌ Full filesystem | ✅ Deny-first glob patterns |
| Command filtering | ❌ All IPC exposed | ✅ Allow/deny lists |
| Window scopes | ❌ Uniform access | ✅ Per-window capabilities |
| Origin checking | ❌ Not built-in | ✅ Origin validation |
| Error sanitization | ❌ Manual | ✅ Automatic path redaction |

## Build Comparison

**Electron:**
```bash
npx electron-builder
# Produces ~150MB installer
```

**Forge:**
```bash
forge build
# Produces ~20MB binary

forge build --result-format json
# CI-friendly JSON output with artifact manifests
```

## Migration Checklist

- [ ] Replace `main.js` with `src/main.py`
- [ ] Move `ipcMain.handle()` calls to `@app.command` decorators
- [ ] Replace `require('electron')` APIs with `@forge/api` imports
- [ ] Create `forge.toml` with your window and permission config
- [ ] Enable only the permissions you actually use
- [ ] Replace `electron-store` with `app.state.manage()`
- [ ] Update build scripts to use `forge build`
- [ ] Test with `forge dev` + `forge doctor`
