# Forge API Reference

Complete catalog of all built-in APIs, their methods, and required capabilities.

## Core APIs

### ForgeApp (`forge.app`)

The main application class. Entry point for all Forge applications.

```python
from forge import ForgeApp

app = ForgeApp()

@app.command
def greet(name: str) -> str:
    return f"Hello, {name}!"

app.run()
```

**Key Methods:**

| Method | Description |
| --- | --- |
| `command(fn)` | Register a command handler |
| `emit(event, data)` | Emit an event to the frontend |
| `run()` | Start the application |
| `state.manage(instance)` | Register a managed state instance |
| `has_capability(name)` | Check if a capability is enabled |

---

### IPCBridge (`forge.bridge`)

Handles command registration, validation, dispatch, and response serialization.

| Method | Description |
| --- | --- |
| `register(name, fn)` | Register a command handler |
| `invoke_command(raw_json)` | Execute a command from JSON message |
| `shutdown()` | Shut down the thread pool |

---

### AppState (`forge.state`)

Thread-safe typed state container for dependency injection.

```python
app.state.manage(Database("sqlite:///app.db"))

@app.command
def get_users(db: Database) -> list:
    return db.query("SELECT * FROM users")
```

| Method | Description |
| --- | --- |
| `manage(instance)` | Register a managed instance by its type |
| `get(cls)` | Retrieve a managed instance by type |
| `has(cls)` | Check if a type is managed |

---

## Built-in APIs

### FileSystem (`forge.api.fs`) — Capability: `filesystem`

| Method | Description |
| --- | --- |
| `read(path)` | Read file contents as string |
| `read_binary(path)` | Read file contents as bytes |
| `write(path, content)` | Write string to file |
| `exists(path)` | Check if path exists |
| `list_dir(path)` | List directory contents |
| `delete(path)` | Delete file |
| `mkdir(path)` | Create directory |
| `is_file(path)` | Check if path is a file |
| `is_dir(path)` | Check if path is a directory |

---

### Clipboard (`forge.api.clipboard`) — Capability: `clipboard`

| Method | Description |
| --- | --- |
| `read()` | Read clipboard text |
| `write(text)` | Write text to clipboard |

---

### Dialog (`forge.api.dialog`) — Capability: `dialogs`

| Method | Description |
| --- | --- |
| `open(options)` | Show open file dialog |
| `save(options)` | Show save file dialog |
| `message(title, body, type)` | Show message dialog |

---

### Shell (`forge.api.shell`) — Capability: `shell`

| Method | Description |
| --- | --- |
| `execute(command, args)` | Execute a shell command |
| `open(url_or_path)` | Open URL or path with default handler |

---

### Notifications (`forge.api.notification`) — Capability: `notifications`

| Method | Description |
| --- | --- |
| `notify(title, body, ...)` | Send a desktop notification |
| `state()` | Get notification backend state |
| `history(limit)` | Recent notification history |

---

### System Tray (`forge.api.tray`) — Capability: `system_tray`

| Method | Description |
| --- | --- |
| `set_icon(path)` | Set tray icon |
| `set_menu(items)` | Set tray menu items |
| `trigger(action, payload)` | Trigger tray action |
| `show()` / `hide()` | Toggle tray visibility |
| `is_visible()` | Check tray visibility |
| `state()` | Get tray state |

---

### Menu (`forge.api.menu`) — No capability required

| Method | Description |
| --- | --- |
| `set(items)` | Set application menu |
| `get()` | Get current menu model |
| `clear()` | Remove all menu items |
| `enable(id)` / `disable(id)` | Toggle item state |
| `trigger(id, payload)` | Trigger menu selection |

---

### Window (`forge.window`) — No capability required

| Method | Description |
| --- | --- |
| `set_title(title)` | Update window title |
| `set_size(width, height)` | Resize window |
| `set_position(x, y)` | Move window |
| `set_fullscreen(enabled)` | Toggle fullscreen |
| `state()` | Get window state snapshot |
| `position()` | Get window position |
| `is_visible()` | Check visibility |

---

### Window Manager (`forge.window.WindowManagerAPI`)

| Method | Description |
| --- | --- |
| `create(label, options)` | Create a new window |
| `close(label)` | Close a window |
| `list()` | List all windows |
| `get(label)` | Get window by label |
| `set_title(label, title)` | Set title for specific window |
| `set_size(label, w, h)` | Resize specific window |
| `focus(label)` | Focus specific window |
| `minimize(label)` / `maximize(label)` | Min/max |
| `show(label)` / `hide(label)` | Show/hide |

---

### Updater (`forge.api.updater`) — Capability: `updater`

| Method | Description |
| --- | --- |
| `check()` | Check for updates |
| `verify()` | Verify manifest signature |
| `download(options)` | Download update artifact |
| `apply(options)` | Apply downloaded update |
| `update(options)` | Full update flow |
| `config()` | Get updater configuration |

---

### Keychain (`forge.api.keychain`) — Capability: `keychain`

| Method | Description |
| --- | --- |
| `set_password(key, password)` | Store credential |
| `get_password(key)` | Retrieve credential |
| `delete_password(key)` | Delete credential |

---

### Shortcuts (`forge.api.shortcuts`) — Capability: `shortcuts`

| Method | Description |
| --- | --- |
| `register(accelerator, callback)` | Register global shortcut |
| `unregister(accelerator)` | Remove shortcut |
| `unregister_all()` | Remove all shortcuts |

---

### Deep Links (`forge.api.deep_link`) — Capability: `deep_links`

| Method | Description |
| --- | --- |
| `open(url)` | Dispatch a deep link |
| `state()` | Get deep link state |
| `protocols()` | Get configured protocols |

---

### Autostart (`forge.api.autostart`) — Capability: `autostart`

| Method | Description |
| --- | --- |
| `enable()` | Enable login autostart |
| `disable()` | Disable login autostart |
| `is_enabled()` | Check autostart status |

---

### Lifecycle (`forge.api.lifecycle`) — Capability: `lifecycle`

| Method | Description |
| --- | --- |
| `request_single_instance_lock(name)` | Ensure single instance |
| `relaunch()` | Relaunch the application |

---

## Error Recovery

### CircuitBreaker (`forge.recovery`)

```python
from forge import CircuitBreaker

cb = CircuitBreaker(failure_threshold=5, cooldown_seconds=30)
```

| Method | Description |
| --- | --- |
| `is_allowed(cmd)` | Check if command can execute |
| `record_success(cmd)` | Record successful execution |
| `record_failure(cmd)` | Record failed execution |
| `get_state(cmd)` | Get circuit state (closed/open/half_open) |
| `reset(cmd)` | Reset circuit for command |
| `snapshot()` | Diagnostic snapshot |

### CrashReporter (`forge.recovery`)

| Method | Description |
| --- | --- |
| `install()` | Install as global exception hook |
| `uninstall()` | Restore original hook |
| `get_recent_reports(count)` | Load recent crash reports |

### ErrorCode (`forge.recovery`)

Structured error codes: `INVALID_REQUEST`, `PERMISSION_DENIED`, `CIRCUIT_OPEN`, `INTERNAL_ERROR`, etc.
