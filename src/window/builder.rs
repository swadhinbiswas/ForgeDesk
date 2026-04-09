use pyo3::prelude::*;
use std::borrow::Cow;
use std::fs;
use std::path::PathBuf;
use wry::WebViewBuilder;

use crate::events::{clone_py_callback, emit_window_event};
use crate::platform::assets::mime_from_path;
use crate::window::proxy::WindowProxy;

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
    webview_builder = webview_builder.with_asynchronous_custom_protocol("forge".into(), move |_webview_id, request, responder| {
        let path = request.uri().path().to_string();
        let mut file_path = root_path.clone();

        std::thread::spawn(move || {
            let relative_path = if path == "/" { "index.html" } else { &path[1..] };
            file_path.push(relative_path);

            if let Ok(content) = fs::read(&file_path) {
                let mime = mime_from_path(&path);
                let mut builder = wry::http::Response::builder()
                    .header("Content-Type", mime)
                    .header("Access-Control-Allow-Origin", "*");

                if mime == "text/html" {
                    builder = builder.header(
                        "Content-Security-Policy",
                        "default-src 'self' forge: http://localhost:*; \
                         script-src 'self' 'unsafe-inline' 'unsafe-eval' forge: http://localhost:*; \
                         style-src 'self' 'unsafe-inline' forge: http://localhost:*; \
                         img-src 'self' data: forge: http://localhost:*; \
                         connect-src 'self' ws://localhost:* http://localhost:* forge:;"
                    );
                }

                let response = builder.body(Cow::Owned(content)).unwrap();
                responder.respond(response);
            } else {
                let response = wry::http::Response::builder()
                    .status(404)
                    .header("Access-Control-Allow-Origin", "*")
                    .body(Cow::Borrowed("File not found".as_bytes()))
                    .unwrap();
                responder.respond(response);
            }
        });
    });

    webview_builder = webview_builder.with_url(url);
    webview_builder = webview_builder.with_devtools(true);

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
