use pyo3::prelude::*;
use std::collections::HashMap;
use std::path::PathBuf;
use tao::{
    event::{Event, WindowEvent},
    event_loop::{ControlFlow, EventLoopBuilder},
    window::{Fullscreen, WindowBuilder, WindowId},
};

#[cfg(target_os = "linux")]
use gtk::prelude::*;
#[cfg(target_os = "linux")]
use std::rc::Rc;
#[cfg(target_os = "linux")]
use tao::platform::unix::WindowExtUnix;

use crate::events::{clone_py_callback, emit_window_event, UserEvent};
use crate::platform::vibrancy::apply_vibrancy_to_window;
use crate::window::builder::build_webview_for_window;
use crate::window::proxy::WindowProxy;
use crate::window::RuntimeWindow;

/// NativeWindow - The Rust-backed window for Forge Framework.
///
/// In Python 3.14+ free-threaded mode, the IPC callback can be invoked
/// without acquiring the GIL, enabling true parallel command execution.
#[pyclass]
pub struct NativeWindow {
    title: String,
    base_path: PathBuf,
    width: f64,
    height: f64,
    fullscreen: bool,
    resizable: bool,
    decorations: bool,
    transparent: bool,
    always_on_top: bool,
    min_width: f64,
    min_height: f64,
    x: Option<f64>,
    y: Option<f64>,
    vibrancy: Option<String>,
    ipc_callback: Option<Py<PyAny>>,
    ready_callback: Option<Py<PyAny>>,
    window_event_callback: Option<Py<PyAny>>,
}

#[pymethods]
impl NativeWindow {
    #[new]
    #[pyo3(signature = (
        title,
        base_path,
        width = 800.0,
        height = 600.0,
        fullscreen = false,
        resizable = true,
        decorations = true,
        transparent = false,
        always_on_top = false,
        min_width = 400.0,
        min_height = 300.0,
        x = None,
        y = None,
        vibrancy = None,
    ))]
    fn new(
        title: String,
        base_path: String,
        width: f64,
        height: f64,
        fullscreen: bool,
        resizable: bool,
        decorations: bool,
        transparent: bool,
        always_on_top: bool,
        min_width: f64,
        min_height: f64,
        x: Option<f64>,
        y: Option<f64>,
        vibrancy: Option<String>,
    ) -> Self {
        NativeWindow {
            title,
            base_path: PathBuf::from(base_path),
            width,
            height,
            fullscreen,
            resizable,
            decorations,
            transparent,
            always_on_top,
            min_width,
            min_height,
            x,
            y,
            vibrancy,
            ipc_callback: None,
            ready_callback: None,
            window_event_callback: None,
        }
    }

    /// Register the Python IPC callback.
    ///
    /// The callback receives two arguments: (message: str, proxy: WindowProxy).
    /// The proxy can be used to send JS back to the WebView without touching
    /// NativeWindow (avoiding the PyO3 borrow conflict).
    fn set_ipc_callback(&mut self, callback: Py<PyAny>) {
        self.ipc_callback = Some(callback);
    }

    /// Register a callback that fires once the window is ready.
    ///
    /// The callback receives one argument: (proxy: WindowProxy).
    /// This allows Python code to store the proxy for later use (e.g. emitting
    /// events to JS from background threads).
    fn set_ready_callback(&mut self, callback: Py<PyAny>) {
        self.ready_callback = Some(callback);
    }

    /// Register a callback for native window lifecycle/state events.
    ///
    /// The callback receives two arguments: (event_name: str, payload_json: str).
    fn set_window_event_callback(&mut self, callback: Py<PyAny>) {
        self.window_event_callback = Some(callback);
    }

    /// Launch the native window and block until closed.
    ///
    /// The IPC handler uses Python::attach which, under free-threaded Python 3.14+,
    /// does NOT serialize execution -- multiple IPC calls run truly in parallel.
    ///
    /// On launch, a WindowProxy is created and passed to:
    ///   1. The IPC callback (as the second argument on each call)
    ///   2. The ready callback (once, immediately after window creation)
    fn run(slf: PyRefMut<'_, Self>) -> PyResult<()> {
        let event_loop = EventLoopBuilder::<UserEvent>::with_user_event().build();
        let proxy = event_loop.create_proxy();

        let mut builder = WindowBuilder::new()
            .with_title(&slf.title)
            .with_inner_size(tao::dpi::LogicalSize::new(slf.width, slf.height))
            .with_min_inner_size(tao::dpi::LogicalSize::new(slf.min_width, slf.min_height))
            .with_fullscreen(if slf.fullscreen {
                Some(Fullscreen::Borderless(None))
            } else {
                None
            })
            .with_resizable(slf.resizable)
            .with_decorations(slf.decorations)
            .with_transparent(slf.transparent)
            .with_always_on_top(slf.always_on_top);

        if let (Some(x), Some(y)) = (slf.x, slf.y) {
            builder = builder.with_position(tao::dpi::LogicalPosition::new(x, y));
        }

        let main_window = builder.build(&event_loop).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to build window: {}",
                e
            ))
        })?;

        // Apply initial vibrancy
        #[cfg(target_os = "linux")]
        {
            let _ = &slf.vibrancy;
        }

        #[cfg(not(target_os = "linux"))]
        {
            if let Some(v) = &slf.vibrancy {
                apply_vibrancy_to_window(&main_window, v);
            }
        }

        // ─── LINUX: Add GtkHeaderBar for proper window decorations ───
        #[cfg(target_os = "linux")]
        if slf.decorations {
            let gtk_window = main_window.gtk_window();
            let header_bar = gtk::HeaderBar::new();
            header_bar.set_show_close_button(true);
            header_bar.set_title(Some(&slf.title));
            gtk_window.set_titlebar(Some(&header_bar));
            header_bar.show_all();
        }

        #[cfg(target_os = "linux")]
        let menu_bar = {
            let vbox = main_window.default_vbox().expect(
                "tao window should have a default vbox; \
                 did you disable it with with_default_vbox(false)?",
            );
            let menu_bar = gtk::MenuBar::new();
            menu_bar.hide();
            vbox.pack_start(&menu_bar, false, false, 0);
            vbox.reorder_child(&menu_bar, 0);
            menu_bar
        };

        // Create the Python-visible WindowProxy (holds only the EventLoopProxy)
        let py = slf.py();
        let window_proxy = WindowProxy {
            proxy: proxy.clone(),
        };
        let window_proxy_py = Py::new(py, window_proxy.clone())?;

        // Clone callbacks out before dropping the PyRefMut borrow
        let ipc_cb = slf.ipc_callback.as_ref().map(|cb| cb.clone_ref(py));
        let ready_cb = slf.ready_callback.as_ref().map(|cb| cb.clone_ref(py));
        let window_event_cb = slf
            .window_event_callback
            .as_ref()
            .map(|cb| cb.clone_ref(py));
        let root_path = slf.base_path.clone();
        let main_title = slf.title.clone();
        let main_width = slf.width;
        let main_height = slf.height;
        let main_fullscreen = slf.fullscreen;
        let main_resizable = slf.resizable;
        let main_decorations = slf.decorations;
        let main_always_on_top = slf.always_on_top;
        let main_min_width = slf.min_width;
        let main_min_height = slf.min_height;

        // Drop the mutable borrow on NativeWindow before entering the event loop.
        // From here on, all communication goes through WindowProxy / EventLoopProxy.
        drop(slf);

        let main_webview = build_webview_for_window(
            &main_window,
            "main",
            "forge://app/index.html",
            root_path.clone(),
            clone_py_callback(&ipc_cb),
            clone_py_callback(&window_event_cb),
            window_proxy_py.clone_ref(py),
        )
        .map_err(|error| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to build WebView: {}",
                error
            ))
        })?;

        let main_window_id = main_window.id();
        let mut windows_by_id: HashMap<WindowId, RuntimeWindow> = HashMap::new();
        let mut labels_to_id: HashMap<String, WindowId> = HashMap::new();
        windows_by_id.insert(
            main_window_id,
            RuntimeWindow {
                label: "main".to_string(),
                parent_label: None,
                url: "forge://app/index.html".to_string(),
                window: main_window,
                webview: main_webview,
                #[cfg(target_os = "linux")]
                menu_bar,
            },
        );
        labels_to_id.insert("main".to_string(), main_window_id);

        if let Some(cb) = ready_cb {
            Python::attach(|py| {
                if let Err(error) = cb.call1(py, (window_proxy_py.clone_ref(py),)) {
                    eprintln!("[forge-core] ready callback error: {}", error);
                }
            });
        }

        emit_window_event(
            &window_event_cb,
            "ready",
            "main",
            serde_json::json!({
                "title": main_title,
                "url": "forge://app/index.html",
                "width": main_width,
                "height": main_height,
                "fullscreen": main_fullscreen,
                "resizable": main_resizable,
                "decorations": main_decorations,
                "always_on_top": main_always_on_top,
                "visible": true,
                "min_width": main_min_width,
                "min_height": main_min_height,
            }),
        );

        #[cfg(target_os = "linux")]
        let emit_menu_selection: crate::menu::MenuEmitter = {
            let cb = clone_py_callback(&window_event_cb);
            Rc::new(
                move |item_id: String,
                      label: Option<String>,
                      role: Option<String>,
                      checked: Option<bool>| {
                    emit_window_event(
                        &cb,
                        "menu_selected",
                        "main",
                        serde_json::json!({
                            "id": item_id,
                            "label": label,
                            "role": role,
                            "checked": checked,
                        }),
                    );
                },
            )
        };

        // ─── GLOBAL HOTKEYS ───
        let hotkey_manager =
            global_hotkey::GlobalHotKeyManager::new().expect("Failed to initialize hotkey manager");
        let hotkey_channel = global_hotkey::GlobalHotKeyEvent::receiver();
        let mut registered_hotkeys: std::collections::HashMap<
            String,
            global_hotkey::hotkey::HotKey,
        > = std::collections::HashMap::new();
        let mut hotkey_id_to_string: std::collections::HashMap<u32, String> =
            std::collections::HashMap::new();

        // ─── EVENT LOOP ───
        event_loop.run(move |event, target, control_flow| {
            *control_flow = ControlFlow::Wait;

            // Check global hotkeys
            if let Ok(hotkey_event) = hotkey_channel.try_recv() {
                if hotkey_event.state == global_hotkey::HotKeyState::Released {
                    if let Some(accelerator) = hotkey_id_to_string.get(&hotkey_event.id) {
                        emit_window_event(
                            &window_event_cb,
                            "global_shortcut",
                            "main",
                            serde_json::json!({
                                "accelerator": accelerator
                            }),
                        );
                    }
                }
            }

            match event {
                Event::UserEvent(UserEvent::Eval(label, script)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(target_id) {
                            let _ = runtime_window.webview.evaluate_script(&script);
                        }
                    }
                }
                Event::UserEvent(UserEvent::LoadUrl(label, url)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get_mut(target_id) {
                            runtime_window.url = url.clone();
                            let _ = runtime_window.webview.load_url(&url);
                        }
                    }
                }
                Event::UserEvent(UserEvent::Reload(label)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(target_id) {
                            let _ = runtime_window.webview.reload();
                        }
                    }
                    emit_window_event(
                        &window_event_cb,
                        "reloaded",
                        &label,
                        serde_json::Value::Null,
                    );
                }
                Event::UserEvent(UserEvent::GoBack(label)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(target_id) {
                            let _ = runtime_window
                                .webview
                                .evaluate_script("window.history.back();");
                        }
                    }
                    emit_window_event(
                        &window_event_cb,
                        "history_back",
                        &label,
                        serde_json::Value::Null,
                    );
                }
                Event::UserEvent(UserEvent::GoForward(label)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(target_id) {
                            let _ = runtime_window
                                .webview
                                .evaluate_script("window.history.forward();");
                        }
                    }
                    emit_window_event(
                        &window_event_cb,
                        "history_forward",
                        &label,
                        serde_json::Value::Null,
                    );
                }
                Event::UserEvent(UserEvent::OpenDevtools(label)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(target_id) {
                            runtime_window.webview.open_devtools();
                        }
                    }
                    emit_window_event(
                        &window_event_cb,
                        "devtools",
                        &label,
                        serde_json::json!({ "open": true }),
                    );
                }
                Event::UserEvent(UserEvent::CloseDevtools(label)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(target_id) {
                            runtime_window.webview.close_devtools();
                        }
                    }
                    emit_window_event(
                        &window_event_cb,
                        "devtools",
                        &label,
                        serde_json::json!({ "open": false }),
                    );
                }
                Event::UserEvent(UserEvent::SetTitle(label, title)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(target_id) {
                            runtime_window.window.set_title(&title);
                        }
                    }
                }
                Event::UserEvent(UserEvent::Resize(label, w, h)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(target_id) {
                            runtime_window
                                .window
                                .set_inner_size(tao::dpi::LogicalSize::new(w, h));
                        }
                    }
                }
                Event::UserEvent(UserEvent::SetPosition(label, x, y)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(target_id) {
                            runtime_window
                                .window
                                .set_outer_position(tao::dpi::LogicalPosition::new(x, y));
                        }
                    }
                }
                Event::UserEvent(UserEvent::SetVibrancy(label, vibrancy)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(target_id) {
                            if let Some(v) = &vibrancy {
                                apply_vibrancy_to_window(&runtime_window.window, v);
                            }
                        }
                    }
                }
                Event::UserEvent(UserEvent::SetFullscreen(label, enabled)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(target_id) {
                            runtime_window.window.set_fullscreen(if enabled {
                                Some(Fullscreen::Borderless(None))
                            } else {
                                None
                            });
                        }
                    }
                }
                Event::UserEvent(UserEvent::SetVisible(label, visible)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(target_id) {
                            runtime_window.window.set_visible(visible);
                        }
                    }
                }
                Event::UserEvent(UserEvent::SetMinimized(label, minimized)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(target_id) {
                            runtime_window.window.set_minimized(minimized);
                        }
                    }
                }
                Event::UserEvent(UserEvent::SetMaximized(label, maximized)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(target_id) {
                            runtime_window.window.set_maximized(maximized);
                        }
                    }
                }
                Event::UserEvent(UserEvent::SetAlwaysOnTop(label, always_on_top)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(target_id) {
                            runtime_window.window.set_always_on_top(always_on_top);
                        }
                    }
                }
                Event::UserEvent(UserEvent::SetMenu(menu_json)) => {
                    #[cfg(target_os = "linux")]
                    {
                        if let Some(main_id) = labels_to_id.get("main") {
                            if let Some(runtime_window) = windows_by_id.get(main_id) {
                                if let Err(error) = crate::menu::linux::apply_linux_menu(
                                    &runtime_window.menu_bar,
                                    &menu_json,
                                    emit_menu_selection.clone(),
                                ) {
                                    emit_window_event(
                                        &window_event_cb,
                                        "menu_error",
                                        "main",
                                        serde_json::json!({ "error": error }),
                                    );
                                }
                            }
                        }
                    }
                    #[cfg(not(target_os = "linux"))]
                    {
                        emit_window_event(
                            &window_event_cb,
                            "menu_unsupported",
                            "main",
                            serde_json::json!({ "platform": std::env::consts::OS }),
                        );
                    }
                }
                Event::UserEvent(UserEvent::Focus(label)) => {
                    if let Some(target_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(target_id) {
                            runtime_window.window.set_focus();
                        }
                    }
                }
                Event::UserEvent(UserEvent::CreateWindow(descriptor)) => {
                    let label = descriptor.label.trim().to_lowercase();
                    if label.is_empty() {
                        emit_window_event(
                            &window_event_cb,
                            "window_error",
                            "main",
                            serde_json::json!({ "error": "Window label is required" }),
                        );
                    } else if labels_to_id.contains_key(&label) {
                        emit_window_event(
                            &window_event_cb,
                            "window_error",
                            &label,
                            serde_json::json!({ "error": "Window already exists" }),
                        );
                    } else {
                        #[allow(unused_mut)]
                        let mut child_builder = WindowBuilder::new()
                            .with_title(&descriptor.title)
                            .with_inner_size(tao::dpi::LogicalSize::new(
                                descriptor.width,
                                descriptor.height,
                            ))
                            .with_min_inner_size(tao::dpi::LogicalSize::new(
                                descriptor.min_width,
                                descriptor.min_height,
                            ))
                            .with_fullscreen(if descriptor.fullscreen {
                                Some(Fullscreen::Borderless(None))
                            } else {
                                None
                            })
                            .with_resizable(descriptor.resizable)
                            .with_decorations(descriptor.decorations)
                            .with_transparent(descriptor.transparent)
                            .with_always_on_top(descriptor.always_on_top);

                        #[cfg(target_os = "windows")]
                        if let Some(parent_label) = &descriptor.parent_label {
                            if let Some(parent_id) = labels_to_id.get(parent_label) {
                                if let Some(parent_rt) = windows_by_id.get(parent_id) {
                                    use tao::platform::windows::{WindowBuilderExtWindows, WindowExtWindows};
                                    child_builder =
                                        child_builder.with_owner_window(parent_rt.window.hwnd());
                                }
                            }
                        }

                        #[cfg(target_os = "macos")]
                        if let Some(parent_label) = &descriptor.parent_label {
                            if let Some(parent_id) = labels_to_id.get(parent_label) {
                                if let Some(_parent_rt) = windows_by_id.get(parent_id) {
                                    use tao::platform::macos::WindowExtMacOS;
                                }
                            }
                        }

                        if let Ok(child_window) = child_builder.build(target) {
                            #[cfg(target_os = "linux")]
                            if descriptor.decorations {
                                let gtk_window = child_window.gtk_window();
                                let header_bar = gtk::HeaderBar::new();
                                header_bar.set_show_close_button(true);
                                header_bar.set_title(Some(&descriptor.title));
                                gtk_window.set_titlebar(Some(&header_bar));
                                header_bar.show_all();
                            }

                            #[cfg(target_os = "linux")]
                            let child_menu_bar = {
                                let vbox = child_window.default_vbox().expect(
                                    "tao window should have a default vbox; \
                                 did you disable it with with_default_vbox(false)?",
                                );
                                let menu_bar = gtk::MenuBar::new();
                                menu_bar.hide();
                                vbox.pack_start(&menu_bar, false, false, 0);
                                vbox.reorder_child(&menu_bar, 0);
                                menu_bar
                            };

                            if let Ok(child_webview) = build_webview_for_window(
                                &child_window,
                                &label,
                                &descriptor.url,
                                root_path.clone(),
                                clone_py_callback(&ipc_cb),
                                clone_py_callback(&window_event_cb),
                                Python::attach(|py| window_proxy_py.clone_ref(py)),
                            ) {
                                if !descriptor.visible {
                                    child_window.set_visible(false);
                                }
                                if descriptor.focus {
                                    child_window.set_focus();
                                }

                                let child_window_id = child_window.id();
                                windows_by_id.insert(
                                    child_window_id,
                                    RuntimeWindow {
                                        label: label.clone(),
                                        parent_label: descriptor.parent_label.clone(),
                                        url: descriptor.url.clone(),
                                        window: child_window,
                                        webview: child_webview,
                                        #[cfg(target_os = "linux")]
                                        menu_bar: child_menu_bar,
                                    },
                                );
                                labels_to_id.insert(label.clone(), child_window_id);
                                emit_window_event(
                                    &window_event_cb,
                                    "created",
                                    &label,
                                    serde_json::json!({
                                        "title": descriptor.title,
                                        "url": descriptor.url,
                                        "width": descriptor.width,
                                        "height": descriptor.height,
                                        "fullscreen": descriptor.fullscreen,
                                        "resizable": descriptor.resizable,
                                        "decorations": descriptor.decorations,
                                        "transparent": descriptor.transparent,
                                        "always_on_top": descriptor.always_on_top,
                                        "visible": descriptor.visible,
                                        "focused": descriptor.focus,
                                    }),
                                );
                            } else {
                                emit_window_event(
                                    &window_event_cb,
                                    "window_error",
                                    &label,
                                    serde_json::json!({ "error": "Failed to build WebView" }),
                                );
                            }
                        } else {
                            emit_window_event(
                                &window_event_cb,
                                "window_error",
                                &label,
                                serde_json::json!({ "error": "Failed to build window" }),
                            );
                        }
                    }
                }
                Event::UserEvent(UserEvent::CloseLabel(label)) => {
                    let normalized = label.trim().to_lowercase();
                    if normalized == "main" {
                        emit_window_event(
                            &window_event_cb,
                            "close_requested",
                            "main",
                            serde_json::Value::Null,
                        );
                        *control_flow = ControlFlow::Exit;
                    } else if let Some(window_id) = labels_to_id.remove(&normalized) {
                        windows_by_id.remove(&window_id);
                        emit_window_event(
                            &window_event_cb,
                            "destroyed",
                            &normalized,
                            serde_json::Value::Null,
                        );
                    }
                }
                Event::UserEvent(UserEvent::Close) => {
                    emit_window_event(
                        &window_event_cb,
                        "close_requested",
                        "main",
                        serde_json::Value::Null,
                    );
                    *control_flow = ControlFlow::Exit;
                }
                Event::UserEvent(UserEvent::GetMonitors(tx)) => {
                    if let Some(main_id) = labels_to_id.get("main") {
                        if let Some(runtime_window) = windows_by_id.get(main_id) {
                            let mut monitors = Vec::new();
                            for m in runtime_window.window.available_monitors() {
                                let start = m.position();
                                let size = m.size();
                                let is_primary = runtime_window
                                    .window
                                    .primary_monitor()
                                    .map_or(false, |pm| pm.name() == m.name());
                                let mon_json = serde_json::json!({
                                    "name": m.name(),
                                    "position": { "x": start.x, "y": start.y },
                                    "size": { "width": size.width, "height": size.height },
                                    "scale_factor": m.scale_factor(),
                                    "is_primary": is_primary
                                });
                                monitors.push(mon_json);
                            }
                            let _ = tx.send(
                                serde_json::to_string(&monitors)
                                    .unwrap_or_else(|_| "[]".to_string()),
                            );
                        } else {
                            let _ = tx.send("[]".into());
                        }
                    } else {
                        let _ = tx.send("[]".into());
                    }
                }
                Event::UserEvent(UserEvent::GetPrimaryMonitor(tx)) => {
                    if let Some(main_id) = labels_to_id.get("main") {
                        if let Some(runtime_window) = windows_by_id.get(main_id) {
                            if let Some(m) = runtime_window.window.primary_monitor() {
                                let start = m.position();
                                let size = m.size();
                                let mon_json = serde_json::json!({
                                    "name": m.name(),
                                    "position": { "x": start.x, "y": start.y },
                                    "size": { "width": size.width, "height": size.height },
                                    "scale_factor": m.scale_factor(),
                                    "is_primary": true
                                });
                                let _ = tx.send(
                                    serde_json::to_string(&mon_json)
                                        .unwrap_or_else(|_| "null".into()),
                                );
                            } else {
                                let _ = tx.send("null".into());
                            }
                        } else {
                            let _ = tx.send("null".into());
                        }
                    } else {
                        let _ = tx.send("null".into());
                    }
                }
                Event::UserEvent(UserEvent::GetCursorPosition(tx)) => {
                    if let Some(main_id) = labels_to_id.get("main") {
                        if let Some(runtime_window) = windows_by_id.get(main_id) {
                            if let Ok(pos) = runtime_window.window.cursor_position() {
                                let pos_json = serde_json::json!({
                                    "x": pos.x as i32,
                                    "y": pos.y as i32
                                });
                                let _ = tx.send(
                                    serde_json::to_string(&pos_json)
                                        .unwrap_or_else(|_| "{\"x\":0,\"y\":0}".into()),
                                );
                            } else {
                                let _ = tx.send("{\"x\":0,\"y\":0}".into());
                            }
                        } else {
                            let _ = tx.send("{\"x\":0,\"y\":0}".into());
                        }
                    } else {
                        let _ = tx.send("{\"x\":0,\"y\":0}".into());
                    }
                }
                Event::UserEvent(UserEvent::RegisterShortcut(accelerator, tx)) => {
                    use std::str::FromStr;
                    match global_hotkey::hotkey::HotKey::from_str(&accelerator) {
                        Ok(hotkey) => {
                            if hotkey_manager.register(hotkey).is_ok() {
                                registered_hotkeys.insert(accelerator.clone(), hotkey);
                                hotkey_id_to_string.insert(hotkey.id(), accelerator.clone());
                                let _ = tx.send(true);
                            } else {
                                let _ = tx.send(false);
                            }
                        }
                        Err(_) => {
                            let _ = tx.send(false);
                        }
                    }
                }
                Event::UserEvent(UserEvent::UnregisterShortcut(accelerator, tx)) => {
                    if let Some(hotkey) = registered_hotkeys.remove(&accelerator) {
                        hotkey_id_to_string.remove(&hotkey.id());
                        let _ = hotkey_manager.unregister(hotkey);
                        let _ = tx.send(true);
                    } else {
                        let _ = tx.send(false);
                    }
                }
                Event::UserEvent(UserEvent::UnregisterAllShortcuts(tx)) => {
                    for (_, hotkey) in registered_hotkeys.drain() {
                        let _ = hotkey_manager.unregister(hotkey);
                    }
                    hotkey_id_to_string.clear();
                    let _ = tx.send(true);
                }
                Event::UserEvent(UserEvent::Print(label)) => {
                    if let Some(window_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(window_id) {
                            let _ = runtime_window.webview.print();
                        }
                    }
                }
                Event::UserEvent(UserEvent::SetProgressBar(progress)) => {
                    if let Some(main_id) = labels_to_id.get("main") {
                        if let Some(runtime_window) = windows_by_id.get(main_id) {
                            let state = if progress < 0.0 {
                                tao::window::ProgressBarState {
                                    progress: None,
                                    state: None,
                                    desktop_filename: None,
                                }
                            } else {
                                tao::window::ProgressBarState {
                                    progress: Some((progress * 100.0) as u64),
                                    state: Some(tao::window::ProgressState::Normal),
                                    desktop_filename: None,
                                }
                            };
                            runtime_window.window.set_progress_bar(state);
                        }
                    }
                }
                Event::UserEvent(UserEvent::RequestUserAttention(attention_type)) => {
                    if let Some(main_id) = labels_to_id.get("main") {
                        if let Some(runtime_window) = windows_by_id.get(main_id) {
                            runtime_window.window.request_user_attention(attention_type);
                        }
                    }
                }
                Event::UserEvent(UserEvent::PowerGetBatteryInfo(tx)) => {
                    let mut battery_info = "{}".to_string();
                    if let Ok(manager) = starship_battery::Manager::new() {
                        if let Ok(mut batteries) = manager.batteries() {
                            if let Some(Ok(battery)) = batteries.next() {
                                let state = match battery.state() {
                                    starship_battery::State::Charging => "charging",
                                    starship_battery::State::Discharging => "discharging",
                                    starship_battery::State::Empty => "empty",
                                    starship_battery::State::Full => "full",
                                    _ => "unknown",
                                };
                                let charge = battery.state_of_charge().value;
                                battery_info =
                                    format!(r#"{{"state": "{}", "charge": {}}}"#, state, charge);
                            }
                        }
                    }
                    let _ = tx.send(battery_info);
                }
                Event::UserEvent(UserEvent::ApplyUpdate(url, sig, pubkey, tx)) => {
                    std::thread::spawn(move || {
                        if let Err(e) = crate::updater::apply_update(url, sig, pubkey) {
                            eprintln!("[forge-core] ApplyUpdate failed: {}", e);
                            let _ = tx.send(false);
                        } else {
                            let _ = tx.send(true);
                        }
                    });
                }
                Event::WindowEvent {
                    event, window_id, ..
                } => {
                    if let Some(runtime_window) = windows_by_id.get(&window_id) {
                        let label = runtime_window.label.clone();

                        match event {
                            WindowEvent::Resized(size) => {
                                emit_window_event(
                                    &window_event_cb,
                                    "resized",
                                    &label,
                                    serde_json::json!({
                                        "width": size.width,
                                        "height": size.height,
                                    }),
                                );
                            }
                            WindowEvent::Moved(position) => {
                                emit_window_event(
                                    &window_event_cb,
                                    "moved",
                                    &label,
                                    serde_json::json!({
                                        "x": position.x,
                                        "y": position.y,
                                    }),
                                );
                            }
                            WindowEvent::Focused(focused) => {
                                emit_window_event(
                                    &window_event_cb,
                                    "focused",
                                    &label,
                                    serde_json::json!({ "focused": focused }),
                                );
                            }
                            WindowEvent::CloseRequested => {
                                emit_window_event(
                                    &window_event_cb,
                                    "close_requested",
                                    &label,
                                    serde_json::Value::Null,
                                );
                                if label == "main" {
                                    *control_flow = ControlFlow::Exit;
                                } else {
                                    labels_to_id.remove(&label);
                                    windows_by_id.remove(&window_id);
                                    emit_window_event(
                                        &window_event_cb,
                                        "destroyed",
                                        &label,
                                        serde_json::Value::Null,
                                    );
                                }
                            }
                            WindowEvent::Destroyed => {
                                labels_to_id.remove(&label);
                                windows_by_id.remove(&window_id);
                                emit_window_event(
                                    &window_event_cb,
                                    "destroyed",
                                    &label,
                                    serde_json::Value::Null,
                                );
                                if windows_by_id.is_empty() {
                                    *control_flow = ControlFlow::Exit;
                                }
                            }
                            _ => {}
                        }
                    }
                }
                Event::Suspended => {
                    emit_window_event(
                        &window_event_cb,
                        "power:suspended",
                        "main",
                        serde_json::Value::Null,
                    );
                }
                Event::Resumed => {
                    emit_window_event(
                        &window_event_cb,
                        "power:resumed",
                        "main",
                        serde_json::Value::Null,
                    );
                }
                _ => (),
            }
        });
    }
}
