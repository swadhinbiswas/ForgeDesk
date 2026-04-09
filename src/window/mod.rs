pub mod builder;
pub mod proxy;

use serde::Deserialize;

// ─── Default value functions for serde ───

fn default_window_url() -> String {
    "forge://app/index.html".to_string()
}

fn default_window_visible() -> bool {
    true
}

fn default_window_focus() -> bool {
    true
}

fn default_window_min_width() -> f64 {
    320.0
}

fn default_window_min_height() -> f64 {
    240.0
}

fn default_true() -> bool {
    true
}

/// Descriptor for creating a native window, deserialized from JSON.
#[derive(Debug, Clone, Deserialize)]
pub struct WindowDescriptor {
    pub label: String,
    pub title: String,
    #[serde(default)]
    pub parent_label: Option<String>,
    #[serde(default = "default_window_url")]
    pub url: String,
    #[serde(default = "default_window_visible")]
    pub visible: bool,
    #[serde(default = "default_window_focus")]
    pub focus: bool,
    #[serde(default)]
    pub fullscreen: bool,
    #[serde(default = "default_true")]
    pub resizable: bool,
    #[serde(default = "default_true")]
    pub decorations: bool,
    #[serde(default)]
    pub transparent: bool,
    #[serde(default)]
    pub always_on_top: bool,
    #[serde(default = "default_window_min_width")]
    pub min_width: f64,
    #[serde(default = "default_window_min_height")]
    pub min_height: f64,
    pub x: Option<f64>,
    #[serde(default)]
    pub y: Option<f64>,
    pub width: f64,
    pub height: f64,
}

/// A managed native window with its associated WebView.
pub struct RuntimeWindow {
    pub label: String,
    pub parent_label: Option<String>,
    pub url: String,
    pub window: tao::window::Window,
    pub webview: wry::WebView,
    #[cfg(target_os = "linux")]
    pub menu_bar: gtk::MenuBar,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_window_descriptor_defaults() {
        let json = r#"{"label": "test", "title": "Test Window", "width": 800, "height": 600}"#;
        let desc: WindowDescriptor = serde_json::from_str(json).unwrap();
        assert_eq!(desc.label, "test");
        assert_eq!(desc.title, "Test Window");
        assert_eq!(desc.width, 800.0);
        assert_eq!(desc.height, 600.0);
        assert_eq!(desc.url, "forge://app/index.html");
        assert!(desc.visible);
        assert!(desc.focus);
        assert!(!desc.fullscreen);
        assert!(desc.resizable);
        assert!(desc.decorations);
        assert!(!desc.transparent);
        assert!(!desc.always_on_top);
        assert_eq!(desc.min_width, 320.0);
        assert_eq!(desc.min_height, 240.0);
        assert!(desc.x.is_none());
        assert!(desc.y.is_none());
        assert!(desc.parent_label.is_none());
    }

    #[test]
    fn test_window_descriptor_full() {
        let json = r#"{
            "label": "settings",
            "title": "Settings",
            "parent_label": "main",
            "url": "forge://app/settings.html",
            "visible": false,
            "focus": false,
            "fullscreen": true,
            "resizable": false,
            "decorations": false,
            "transparent": true,
            "always_on_top": true,
            "min_width": 400,
            "min_height": 300,
            "x": 100,
            "y": 200,
            "width": 1024,
            "height": 768
        }"#;
        let desc: WindowDescriptor = serde_json::from_str(json).unwrap();
        assert_eq!(desc.label, "settings");
        assert_eq!(desc.parent_label.as_deref(), Some("main"));
        assert_eq!(desc.url, "forge://app/settings.html");
        assert!(!desc.visible);
        assert!(!desc.focus);
        assert!(desc.fullscreen);
        assert!(!desc.resizable);
        assert!(!desc.decorations);
        assert!(desc.transparent);
        assert!(desc.always_on_top);
        assert_eq!(desc.min_width, 400.0);
        assert_eq!(desc.min_height, 300.0);
        assert_eq!(desc.x, Some(100.0));
        assert_eq!(desc.y, Some(200.0));
        assert_eq!(desc.width, 1024.0);
        assert_eq!(desc.height, 768.0);
    }

    #[test]
    fn test_window_descriptor_missing_required_field() {
        // Missing width and height
        let json = r#"{"label": "test", "title": "Test"}"#;
        let result: Result<WindowDescriptor, _> = serde_json::from_str(json);
        assert!(result.is_err());
    }
}
