//! Forge Core — Rust runtime for Forge Framework.
//!
//! This crate provides the native window management, IPC bridge,
//! and platform integration layer for Forge desktop applications.
//!
//! Architecture:
//!   - `native_window` — NativeWindow #[pyclass], tao event loop
//!   - `window/`       — WindowProxy, WindowDescriptor, WebView builder
//!   - `events`        — UserEvent enum, emit helpers
//!   - `menu/`         — NativeMenuItem, GTK menu builder (Linux)
//!   - `platform/`     — Assets, SingleInstance, AutoLaunch, Keychain, Vibrancy

use pyo3::prelude::*;

pub mod events;
pub mod menu;
pub mod native_window;
pub mod platform;
pub mod updater;
pub mod window;

use native_window::NativeWindow;
use platform::auto_launch::AutoLaunchManager;
use platform::keychain::KeychainManager;
use platform::single_instance::SingleInstanceGuard;
use window::proxy::WindowProxy;

/// Python module definition for `forge_core`.
///
/// Exposes all PyO3 classes to Python:
///   - NativeWindow — main window + event loop
///   - WindowProxy  — thread-safe event loop handle
///   - SingleInstanceGuard — single-instance lock
///   - AutoLaunchManager — OS autostart
///   - KeychainManager — OS credential store
#[pymodule]
fn forge_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<NativeWindow>()?;
    m.add_class::<WindowProxy>()?;
    m.add_class::<SingleInstanceGuard>()?;
    m.add_class::<AutoLaunchManager>()?;
    m.add_class::<KeychainManager>()?;
    Ok(())
}
