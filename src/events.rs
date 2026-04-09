use pyo3::prelude::*;

/// User events for cross-thread communication between Python and the native event loop.
///
/// These events are sent via `EventLoopProxy<UserEvent>` from the `WindowProxy`
/// (which lives on arbitrary Python threads) to the main event loop thread.
pub enum UserEvent {
    /// Evaluate JavaScript in the WebView
    Eval(String, String),
    /// Navigate to a URL in the WebView
    LoadUrl(String, String),
    /// Reload the current page (label)
    Reload(String),
    /// Navigate backward in history (label)
    GoBack(String),
    /// Navigate forward in history (label)
    GoForward(String),
    /// Open webview devtools (label)
    OpenDevtools(String),
    /// Close webview devtools (label)
    CloseDevtools(String),
    /// Set window title from Python thread (label, title)
    SetTitle(String, String),
    /// Resize window from Python thread (label, width, height)
    Resize(String, f64, f64),
    /// Move the native window (label, x, y)
    SetPosition(String, f64, f64),
    /// Toggle fullscreen from Python thread (label, enabled)
    SetFullscreen(String, bool),
    /// Show or hide the native window (label, visible)
    SetVisible(String, bool),
    /// Set vibrancy (label, optional effect material)
    SetVibrancy(String, Option<String>),
    /// Minimize or restore the native window (label, minimized)
    SetMinimized(String, bool),
    /// Maximize or restore the native window (label, maximized)
    SetMaximized(String, bool),
    /// Toggle always-on-top (label, enabled)
    SetAlwaysOnTop(String, bool),
    /// Replace the native application menu model
    SetMenu(String),
    /// Focus the native window (label)
    Focus(String),
    /// Create an additional native window
    CreateWindow(crate::window::WindowDescriptor),
    /// Close a managed native window by label
    CloseLabel(String),
    /// Request the event loop to exit
    Close,
    /// Request monitors info
    GetMonitors(crossbeam_channel::Sender<String>),
    /// Request primary monitor info
    GetPrimaryMonitor(crossbeam_channel::Sender<String>),
    /// Request cursor position
    GetCursorPosition(crossbeam_channel::Sender<String>),
    /// Register global shortcut
    RegisterShortcut(String, crossbeam_channel::Sender<bool>),
    /// Unregister global shortcut
    UnregisterShortcut(String, crossbeam_channel::Sender<bool>),
    /// Unregister all global shortcuts
    UnregisterAllShortcuts(crossbeam_channel::Sender<bool>),
    /// Print the current page
    Print(String),
    /// Set progress bar value
    SetProgressBar(f64),
    /// Request user attention
    RequestUserAttention(Option<tao::window::UserAttentionType>),
    /// Get battery information
    PowerGetBatteryInfo(crossbeam_channel::Sender<String>),
    /// Apply an auto-update (url, option_signature, option_pub_key, sender_for_result)
    ApplyUpdate(
        String,
        Option<String>,
        Option<String>,
        crossbeam_channel::Sender<bool>,
    ),
}

/// Emit a window event to the Python callback.
///
/// The callback receives two arguments: (event_name: str, payload_json: str).
/// The label is merged into the payload object for consistency.
pub fn emit_window_event(
    callback: &Option<Py<PyAny>>,
    event_name: &str,
    label: &str,
    payload: serde_json::Value,
) {
    if let Some(cb) = callback {
        let payload_json = match payload {
            serde_json::Value::Object(mut object) => {
                object.insert(
                    "label".to_string(),
                    serde_json::Value::String(label.to_string()),
                );
                serde_json::Value::Object(object).to_string()
            }
            serde_json::Value::Null => serde_json::json!({ "label": label }).to_string(),
            other => serde_json::json!({ "label": label, "value": other }).to_string(),
        };
        Python::attach(|py| {
            if let Err(error) = cb.call1(py, (event_name, payload_json)) {
                eprintln!("[forge-core] window event callback error: {}", error);
            }
        });
    }
}

/// Clone a Python callback reference safely.
pub fn clone_py_callback(callback: &Option<Py<PyAny>>) -> Option<Py<PyAny>> {
    Python::attach(|py| callback.as_ref().map(|cb| cb.clone_ref(py)))
}
