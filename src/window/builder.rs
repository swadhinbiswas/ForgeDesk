use pyo3::prelude::*;
use std::borrow::Cow;
use std::env;
use std::fs;
use std::path::PathBuf;
use wry::WebViewBuilder;

use crate::events::{clone_py_callback, emit_window_event};
use crate::platform::assets::mime_from_path;
use crate::window::proxy::WindowProxy;

fn runtime_csp() -> String {
    env::var("FORGE_RUNTIME_CSP").unwrap_or_else(|_| {
        "default-src 'self' forge: forge-asset: forge-memory:; \
         script-src 'self' 'unsafe-inline' forge:; \
         style-src 'self' 'unsafe-inline' forge:; \
         img-src 'self' data: blob: forge: forge-asset: forge-memory:; \
         media-src 'self' data: blob: forge: forge-asset: forge-memory:; \
         connect-src 'self' forge: forge-asset: forge-memory:;"
            .to_string()
    })
}

fn runtime_devtools_enabled() -> bool {
    matches!(
        env::var("FORGE_RUNTIME_DEVTOOLS").ok().as_deref(),
        Some("1") | Some("true") | Some("TRUE") | Some("yes") | Some("on")
    )
}

/// Build a WebView for a given native window.
///
/// Sets up:
/// - Custom `forge://` protocol for serving local assets
/// - IPC handler for Python ↔ JS communication
/// - Navigation handler for URL change events
/// - Content Security Policy headers
pub fn build_webview_for_window(
    window: &tao::window::Window,
    label: &str,
    url: &str,
    root_path: PathBuf,
    ipc_callback: Option<Py<PyAny>>,
    window_event_callback: Option<Py<PyAny>>,
    proxy_for_ipc: Py<WindowProxy>,
) -> Result<wry::WebView, String> {
    let mut webview_builder = WebViewBuilder::new();

    // Register forge-asset:// for raw binary IPC (Data Channel)
    webview_builder = webview_builder.with_asynchronous_custom_protocol(
        "forge-asset".into(),
        move |_webview_id, request, responder| {
            let path_str = request.uri().path().to_string();

            // URL decode the path
            let decoded = urlencoding::decode(&path_str)
                .unwrap_or(std::borrow::Cow::Borrowed(&path_str))
                .to_string();

            #[cfg(target_os = "windows")]
            let file_path = if decoded.starts_with('/') {
                PathBuf::from(&decoded[1..])
            } else {
                PathBuf::from(&decoded)
            };

            #[cfg(not(target_os = "windows"))]
            let file_path = PathBuf::from(&decoded);

            std::thread::spawn(move || {
                let is_allowed: Result<bool, pyo3::PyErr> = Python::attach(|py| {
                    let scope_mod = py.import("forge.scope")?;
                    let allowed = scope_mod
                        .call_method1(
                            "_validate_asset_path",
                            (&file_path.to_string_lossy().to_string(),),
                        )?
                        .extract::<bool>()?;
                    Ok(allowed)
                });

                // Default deny if Python errors out or rejects
                if !is_allowed.unwrap_or(false) {
                    let builder = wry::http::Response::builder()
                        .status(403)
                        .header("Content-Type", "text/plain");
                    return responder.respond(
                        builder
                            .body(
                                format!(
                                    "Access Denied by
 Scope Validator: {}",
                                    decoded
                                )
                                .into_bytes(),
                            )
                            .unwrap(),
                    );
                }

                if let Ok(content) = fs::read(&file_path) {
                    let mime = mime_from_path(&file_path.to_string_lossy());
                    let builder = wry::http::Response::builder().header("Content-Type", mime);

                    let response = builder.body(Cow::Owned(content)).unwrap();
                    responder.respond(response);
                } else {
                    let response = wry::http::Response::builder()
                        .status(404)
                        .body(Cow::Borrowed("File not found".as_bytes()))
                        .unwrap();
                    responder.respond(response);
                }
            });
        },
    );

    // Register forge-memory:// for true zero-copy binary fetches bypassing JSON serialization
    webview_builder = webview_builder.with_asynchronous_custom_protocol(
        "forge-memory".into(),
        move |_webview_id, request, responder| {
            let path_str = request.uri().path().to_string();

            let key = if path_str.starts_with('/') {
                &path_str[1..]
            } else {
                &path_str
            }
            .to_string();

            std::thread::spawn(move || {
                let result: Result<Vec<u8>, PyErr> = Python::attach(|py| {
                    // Fetch from `forge.memory.buffers`
                    let forge_module = py.import("forge.memory")?;
                    let buffers = forge_module.getattr("buffers")?;
                    let memory_dict = buffers.cast::<pyo3::types::PyDict>()?;

                    if let Some(py_bytes) = memory_dict.get_item(&key)? {
                        // Extract into bytes slice directly avoiding any other conversions
                        let extracted = py_bytes.cast::<pyo3::types::PyBytes>()?;
                        let vec_bytes = extracted.as_bytes().to_vec();

                        // Auto-clear memory inside Python so RAM is freed instantly
                        let _ = memory_dict.del_item(&key);

                        Ok(vec_bytes)
                    } else {
                        Err(pyo3::exceptions::PyKeyError::new_err(format!(
                            "Memory {} not found",
                            key
                        )))
                    }
                });

                match result {
                    Ok(content) => {
                        let mime = mime_from_path(&key);
                        let builder = wry::http::Response::builder().header("Content-Type", mime);

                        let response = builder.body(Cow::Owned(content)).unwrap();
                        responder.respond(response);
                    }
                    Err(e) => {
                        eprintln!(
                            "[forge-core] forge-memory:// fetch failed for key {}: {:?}",
                            key, e
                        );
                        let response = wry::http::Response::builder()
                            .status(404)
                            .body(Cow::Borrowed("Memory not found or not bytes".as_bytes()))
                            .unwrap();
                        responder.respond(response);
                    }
                }
            });
        },
    );

    // Register forge:// for internal html assets
    webview_builder = webview_builder.with_asynchronous_custom_protocol(
        "forge".into(),
        move |_webview_id, request, responder| {
            let path = request.uri().path().to_string();
            let mut file_path = root_path.clone();
            let csp = runtime_csp();

            std::thread::spawn(move || {
                let relative_path = if path == "/" {
                    "index.html"
                } else {
                    &path[1..]
                };
                file_path.push(relative_path);

                if let Ok(content) = fs::read(&file_path) {
                    let mime = mime_from_path(&path);
                    let mut builder = wry::http::Response::builder().header("Content-Type", mime);

                    if mime == "text/html" {
                        builder = builder.header("Content-Security-Policy", csp.as_str());
                    }

                    let response = builder.body(Cow::Owned(content)).unwrap();
                    responder.respond(response);
                } else {
                    let response = wry::http::Response::builder()
                        .status(404)
                        .body(Cow::Borrowed("File not found".as_bytes()))
                        .unwrap();
                    responder.respond(response);
                }
            });
        },
    );

    webview_builder = webview_builder.with_url(url);
    webview_builder = webview_builder.with_devtools(runtime_devtools_enabled());

    // Inject the Forge JS runtime BEFORE any page load happens
    // This provides window.__forge__ securely exactly like Tauri
    let forge_js = include_str!("../../forge/js/forge.js");
    webview_builder = webview_builder.with_initialization_script(forge_js);

    if let Some(cb) = clone_py_callback(&window_event_callback) {
        let navigation_label = label.to_string();
        webview_builder = webview_builder.with_navigation_handler(move |target_url| {
            let navigation_callback = Python::attach(|py| Some(cb.clone_ref(py)));
            emit_window_event(
                &navigation_callback,
                "navigated",
                &navigation_label,
                serde_json::json!({ "url": target_url }),
            );
            true
        });
    }

    if let Some(cb) = ipc_callback {
        webview_builder = webview_builder.with_ipc_handler(move |req| {
            let msg = req.into_body();
            Python::attach(|py| {
                if let Err(error) = cb.call1(py, (msg, proxy_for_ipc.clone_ref(py))) {
                    eprintln!("[forge-core] IPC callback error: {}", error);
                }
            });
        });
    }

    #[cfg(target_os = "linux")]
    {
        use tao::platform::unix::WindowExtUnix;
        use wry::WebViewBuilderExtUnix;
        let vbox = window.default_vbox().expect(
            "tao window should have a default vbox; \
             did you disable it with with_default_vbox(false)?",
        );
        webview_builder
            .build_gtk(vbox)
            .map_err(|error| error.to_string())
    }
    #[cfg(not(target_os = "linux"))]
    {
        webview_builder
            .build(window)
            .map_err(|error| error.to_string())
    }
}
