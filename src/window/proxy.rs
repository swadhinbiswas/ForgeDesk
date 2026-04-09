use pyo3::prelude::*;
use tao::event_loop::EventLoopProxy;

use crate::events::UserEvent;
use crate::window::WindowDescriptor;

/// WindowProxy — A lightweight, thread-safe handle for sending commands
/// to the native window's event loop.
///
/// This is separated from NativeWindow to avoid PyO3 borrow conflicts:
/// NativeWindow.run() holds a mutable borrow for the event loop, so Python
/// code inside the IPC callback cannot call methods on NativeWindow directly.
/// WindowProxy holds only a clone of the EventLoopProxy, which is Send+Sync,
/// so it can safely be used from the IPC callback without touching NativeWindow.
#[pyclass(from_py_object)]
#[derive(Clone)]
pub struct WindowProxy {
    pub proxy: EventLoopProxy<UserEvent>,
}

#[pymethods]
impl WindowProxy {
    /// Send JavaScript to the WebView for evaluation (thread-safe, non-blocking).
    pub fn evaluate_script(&self, label: String, script: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::Eval(label, script))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Failed to send script to event loop",
                )
            })
    }

    /// Navigate the live webview to a URL.
    pub fn load_url(&self, label: String, url: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::LoadUrl(label, url))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send navigation event")
            })
    }

    /// Reload the active webview page.
    #[pyo3(signature = (label="main".to_string()))]
    pub fn reload(&self, label: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::Reload(label))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send reload event")
            })
    }

    /// Navigate backward in browser history.
    #[pyo3(signature = (label="main".to_string()))]
    pub fn go_back(&self, label: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::GoBack(label))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send go-back event")
            })
    }

    /// Dynamically change the window vibrancy/material
    #[pyo3(signature = (label="main".to_string(), vibrancy=None))]
    pub fn set_vibrancy(&self, label: String, vibrancy: Option<String>) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::SetVibrancy(label, vibrancy))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Failed to send set-vibrancy event",
                )
            })
    }

    /// Navigate forward in browser history.
    #[pyo3(signature = (label="main".to_string()))]
    pub fn go_forward(&self, label: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::GoForward(label))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send go-forward event")
            })
    }

    /// Open native webview devtools.
    #[pyo3(signature = (label="main".to_string()))]
    pub fn open_devtools(&self, label: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::OpenDevtools(label))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Failed to send open-devtools event",
                )
            })
    }

    /// Close native webview devtools.
    #[pyo3(signature = (label="main".to_string()))]
    pub fn close_devtools(&self, label: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::CloseDevtools(label))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Failed to send close-devtools event",
                )
            })
    }

    /// Set the window title at runtime (thread-safe).
    #[pyo3(signature = (title, label="main".to_string()))]
    pub fn set_title(&self, title: String, label: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::SetTitle(label, title))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send title update")
            })
    }

    /// Resize the window at runtime (thread-safe).
    #[pyo3(signature = (width, height, label="main".to_string()))]
    pub fn set_size(&self, width: f64, height: f64, label: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::Resize(label, width, height))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send resize event")
            })
    }

    /// Move the window at runtime.
    #[pyo3(signature = (x, y, label="main".to_string()))]
    pub fn set_position(&self, x: f64, y: f64, label: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::SetPosition(label, x, y))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send position event")
            })
    }

    /// Toggle fullscreen mode at runtime.
    #[pyo3(signature = (enabled, label="main".to_string()))]
    pub fn set_fullscreen(&self, enabled: bool, label: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::SetFullscreen(label, enabled))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send fullscreen event")
            })
    }

    /// Show or hide the native window.
    #[pyo3(signature = (visible, label="main".to_string()))]
    pub fn set_visible(&self, visible: bool, label: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::SetVisible(label, visible))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send visibility event")
            })
    }

    /// Focus the native window.
    #[pyo3(signature = (label="main".to_string()))]
    pub fn focus(&self, label: String) -> PyResult<()> {
        self.proxy.send_event(UserEvent::Focus(label)).map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send focus event")
        })
    }

    /// Minimize or restore the native window.
    #[pyo3(signature = (minimized, label="main".to_string()))]
    pub fn set_minimized(&self, minimized: bool, label: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::SetMinimized(label, minimized))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send minimized event")
            })
    }

    /// Maximize or restore the native window.
    #[pyo3(signature = (maximized, label="main".to_string()))]
    pub fn set_maximized(&self, maximized: bool, label: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::SetMaximized(label, maximized))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send maximized event")
            })
    }

    /// Toggle always-on-top at runtime.
    #[pyo3(signature = (always_on_top, label="main".to_string()))]
    pub fn set_always_on_top(&self, always_on_top: bool, label: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::SetAlwaysOnTop(label, always_on_top))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Failed to send always-on-top event",
                )
            })
    }

    /// Replace the native application menu model.
    pub fn set_menu(&self, menu_json: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::SetMenu(menu_json))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send menu update")
            })
    }

    /// Create a managed native child window.
    pub fn create_window(&self, descriptor_json: String) -> PyResult<()> {
        let descriptor: WindowDescriptor =
            serde_json::from_str(&descriptor_json).map_err(|error| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                    "Invalid window descriptor: {}",
                    error
                ))
            })?;
        self.proxy
            .send_event(UserEvent::CreateWindow(descriptor))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Failed to send create-window event",
                )
            })
    }

    /// Close a managed native child window by label.
    pub fn close_window_label(&self, label: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::CloseLabel(label))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Failed to send close-window event",
                )
            })
    }

    /// Close the native window.
    pub fn close(&self) -> PyResult<()> {
        self.proxy.send_event(UserEvent::Close).map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send close event")
        })
    }

    /// Get all monitors
    pub fn get_monitors(&self) -> PyResult<String> {
        let (tx, rx) = crossbeam_channel::bounded(1);
        self.proxy
            .send_event(UserEvent::GetMonitors(tx))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to request monitors")
            })?;
        rx.recv().map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to receive monitors")
        })
    }

    /// Get primary monitor
    pub fn get_primary_monitor(&self) -> PyResult<String> {
        let (tx, rx) = crossbeam_channel::bounded(1);
        self.proxy
            .send_event(UserEvent::GetPrimaryMonitor(tx))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Failed to request primary monitor",
                )
            })?;
        rx.recv().map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to receive primary monitor")
        })
    }

    /// Get global cursor position
    pub fn get_cursor_position(&self) -> PyResult<String> {
        let (tx, rx) = crossbeam_channel::bounded(1);
        self.proxy
            .send_event(UserEvent::GetCursorPosition(tx))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Failed to request cursor position",
                )
            })?;
        rx.recv().map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to receive cursor position")
        })
    }

    /// Register a global shortcut
    pub fn register_shortcut(&self, accelerator: String) -> PyResult<bool> {
        let (tx, rx) = crossbeam_channel::bounded(1);
        self.proxy
            .send_event(UserEvent::RegisterShortcut(accelerator, tx))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Failed to send register shortcut event",
                )
            })?;
        rx.recv().map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Failed to receive shortcut registration status",
            )
        })
    }

    /// Unregister a global shortcut
    pub fn unregister_shortcut(&self, accelerator: String) -> PyResult<bool> {
        let (tx, rx) = crossbeam_channel::bounded(1);
        self.proxy
            .send_event(UserEvent::UnregisterShortcut(accelerator, tx))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Failed to send unregister shortcut event",
                )
            })?;
        rx.recv().map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Failed to receive shortcut unregistration status",
            )
        })
    }

    /// Unregister all global shortcuts
    pub fn unregister_all_shortcuts(&self) -> PyResult<bool> {
        let (tx, rx) = crossbeam_channel::bounded(1);
        self.proxy
            .send_event(UserEvent::UnregisterAllShortcuts(tx))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Failed to send unregister all shortcuts event",
                )
            })?;
        rx.recv().map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Failed to receive shortcut unregistration status",
            )
        })
    }

    pub fn print(&self, label: String) -> PyResult<()> {
        self.proxy
            .send_event(UserEvent::Print(label))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send print event")
            })?;
        Ok(())
    }

    pub fn os_set_progress_bar(&self, progress: f64) -> PyResult<bool> {
        self.proxy
            .send_event(UserEvent::SetProgressBar(progress))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Failed to send progress bar event",
                )
            })?;
        Ok(true)
    }

    pub fn os_request_user_attention(&self, type_str: String) -> PyResult<bool> {
        let attention_type = match type_str.as_str() {
            "critical" => Some(tao::window::UserAttentionType::Critical),
            "informational" => Some(tao::window::UserAttentionType::Informational),
            _ => None,
        };
        self.proxy
            .send_event(UserEvent::RequestUserAttention(attention_type))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Failed to send user attention event",
                )
            })?;
        Ok(true)
    }

    pub fn power_get_battery_info(&self) -> PyResult<String> {
        let (tx, rx) = crossbeam_channel::bounded(1);
        self.proxy
            .send_event(UserEvent::PowerGetBatteryInfo(tx))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Failed to send power get battery info event",
                )
            })?;
        rx.recv().map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to receive battery info")
        })
    }

    pub fn apply_update(
        &self,
        url: String,
        signature_hex: Option<String>,
        pub_key_hex: Option<String>,
    ) -> PyResult<bool> {
        let (tx, rx) = crossbeam_channel::bounded(1);
        self.proxy
            .send_event(UserEvent::ApplyUpdate(url, signature_hex, pub_key_hex, tx))
            .map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Failed to send apply update event",
                )
            })?;
        rx.recv().map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Failed to receive apply update status",
            )
        })
    }
}
