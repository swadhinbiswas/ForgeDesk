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
                    let body =
                        format!("Access Denied by Scope Validator: {}", decoded).into_bytes();
                    let response = wry::http::Response::builder()
                        .status(403)
                        .header("Content-Type", "text/plain")
                        .body(Cow::Owned(body))
                        .unwrap_or_else(|_| wry::http::Response::new(Cow::Borrowed(&[][..])));
                    return responder.respond(response);
                }

                if let Ok(content) = fs::read(&file_path) {
                    let mime = mime_from_path(&file_path.to_string_lossy());
                    let builder = wry::http::Response::builder().header("Content-Type", mime);

                    match builder.body(Cow::Owned(content)) {
                        Ok(response) => responder.respond(response),
                        Err(_) => {
                            let _ = responder.respond(
                                wry::http::Response::builder()
                                    .status(500)
                                    .body(Cow::Borrowed("Response build error".as_bytes()))
                                    .unwrap_or_else(|_| {
                                        wry::http::Response::new(Cow::Borrowed(&[][..]))
                                    }),
                            );
                        }
                    }
                } else {
                    let _ = responder.respond(
                        wry::http::Response::builder()
                            .status(404)
                            .body(Cow::Borrowed("File not found".as_bytes()))
                            .unwrap_or_else(|_| wry::http::Response::new(Cow::Borrowed(&[][..]))),
                    );
                }
            });
        },
    );

    // Register forge-memory:// for true zero-copy binary fetches bypassing JSON serialization
    webview_builder = webview_builder.with_asynchronous_custom_protocol(
        "forge-memory".into(),
        move |_webview_id, request, responder| {
            let path_str = request.uri().path().to_string();

            let key = path_str.strip_prefix('/').unwrap_or(&path_str).to_string();

            std::thread::spawn(move || {
                let result: Result<Vec<u8>, PyErr> = Python::attach(|py| {
                    // Fetch and remove the entry in a single locked call so we
                    // never race with the Python writer path on NoGIL.
                    let forge_module = py.import("forge.memory")?;
                    let take_fn = forge_module.getattr("take")?;
                    let value = take_fn.call1((&key,))?;

                    if value.is_none() {
                        return Err(pyo3::exceptions::PyKeyError::new_err(format!(
                            "Memory {} not found",
                            key
                        )));
                    }

                    let py_bytes = value.cast::<pyo3::types::PyBytes>()?;
                    Ok(py_bytes.as_bytes().to_vec())
                });

                match result {
                    Ok(content) => {
                        let mime = mime_from_path(&key);
                        let builder = wry::http::Response::builder().header("Content-Type", mime);

                        match builder.body(Cow::Owned(content)) {
                            Ok(response) => responder.respond(response),
                            Err(_) => {
                                let _ = responder.respond(
                                    wry::http::Response::builder()
                                        .status(500)
                                        .body(Cow::Borrowed("Response build error".as_bytes()))
                                        .unwrap_or_else(|_| {
                                            wry::http::Response::new(Cow::Borrowed(&[][..]))
                                        }),
                                );
                            }
                        }
                    }
                    Err(e) => {
                        eprintln!(
                            "[forge-core] forge-memory:// fetch failed for key {}: {:?}",
                            key, e
                        );
                        let _ = responder.respond(
                            wry::http::Response::builder()
                                .status(404)
                                .body(Cow::Borrowed("Memory not found or not bytes".as_bytes()))
                                .unwrap_or_else(|_| wry::http::Response::new(Cow::Borrowed(&[][..]))),
                        );
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
            let root_clone = root_path.clone();
            let csp = runtime_csp();

            std::thread::spawn(move || {
                let decoded_path = urlencoding::decode(&path)
                    .map(|c| c.into_owned())
                    .unwrap_or_else(|_| path.clone());
                let relative_path = if decoded_path == "/" {
                    "index.html".to_string()
                } else {
                    decoded_path.trim_start_matches('/').to_string()
                };

                let candidate = root_clone.join(&relative_path);

                // Canonicalize both root and target, then verify containment.
                // Reject any path that escapes the project root.
                let root_canonical = match std::fs::canonicalize(&root_clone) {
                    Ok(p) => p,
                    Err(_) => {
                        let _ = responder.respond(
                            wry::http::Response::builder()
                                .status(500)
                                .body(Cow::Borrowed("Root not accessible".as_bytes()))
                                .unwrap_or_else(|_| wry::http::Response::new(Cow::Borrowed(&[][..]))),
                        );
                        return;
                    }
                };
                let resolved = match std::fs::canonicalize(&candidate) {
                    Ok(p) => p,
                    Err(_) => {
                        let _ = responder.respond(
                            wry::http::Response::builder()
                                .status(404)
                                .body(Cow::Borrowed("File not found".as_bytes()))
                                .unwrap_or_else(|_| wry::http::Response::new(Cow::Borrowed(&[][..]))),
                        );
                        return;
                    }
                };
                if !resolved.starts_with(&root_canonical) {
                    let _ = responder.respond(
                        wry::http::Response::builder()
                            .status(403)
                            .body(Cow::Borrowed("Path traversal blocked".as_bytes()))
                            .unwrap_or_else(|_| wry::http::Response::new(Cow::Borrowed(&[][..]))),
                    );
                    return;
                }

                if let Ok(content) = fs::read(&resolved) {
                    let mime = mime_from_path(&decoded_path);
                    let mut builder = wry::http::Response::builder().header("Content-Type", mime);

                    if mime == "text/html" {
                        builder = builder.header("Content-Security-Policy", csp.as_str());
                    }

                    match builder.body(Cow::Owned(content)) {
                        Ok(response) => responder.respond(response),
                        Err(_) => {
                            let _ = responder.respond(
                                wry::http::Response::builder()
                                    .status(500)
                                    .body(Cow::Borrowed("Response build error".as_bytes()))
                                    .unwrap_or_else(|_| {
                                        wry::http::Response::new(Cow::Borrowed(&[][..]))
                                    }),
                            );
                        }
                    }
                } else {
                    let _ = responder.respond(
                        wry::http::Response::builder()
                            .status(404)
                            .body(Cow::Borrowed("File not found".as_bytes()))
                            .unwrap_or_else(|_| wry::http::Response::new(Cow::Borrowed(&[][..]))),
                    );
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
        let vbox = window.default_vbox().ok_or_else(|| {
            "tao window has no default vbox; did you disable it with with_default_vbox(false)?"
                .to_string()
        })?;
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
