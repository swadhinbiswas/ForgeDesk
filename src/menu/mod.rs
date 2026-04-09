pub mod linux;

use serde::Deserialize;

fn default_menu_item_type() -> String {
    "item".to_string()
}

fn default_menu_enabled() -> bool {
    true
}

/// A single item in a native application menu.
///
/// Supports normal items, separators, checkable items, and submenus.
/// Deserialized from JSON sent via the IPC bridge.
#[derive(Debug, Clone, Deserialize)]
pub struct NativeMenuItem {
    #[serde(default)]
    pub id: Option<String>,
    #[serde(default)]
    pub label: Option<String>,
    #[serde(default = "default_menu_item_type")]
    #[serde(rename = "type")]
    pub item_type: String,
    #[serde(default = "default_menu_enabled")]
    pub enabled: bool,
    #[serde(default)]
    pub checked: bool,
    #[serde(default)]
    pub checkable: bool,
    #[serde(default)]
    pub role: Option<String>,
    #[serde(default)]
    pub submenu: Vec<NativeMenuItem>,
}

#[cfg(target_os = "linux")]
pub type MenuEmitter = std::rc::Rc<dyn Fn(String, Option<String>, Option<String>, Option<bool>)>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_menu_item_defaults() {
        let json = r#"{"label": "File"}"#;
        let item: NativeMenuItem = serde_json::from_str(json).unwrap();
        assert_eq!(item.label.as_deref(), Some("File"));
        assert_eq!(item.item_type, "item");
        assert!(item.enabled);
        assert!(!item.checked);
        assert!(!item.checkable);
        assert!(item.role.is_none());
        assert!(item.submenu.is_empty());
    }

    #[test]
    fn test_separator_item() {
        let json = r#"{"type": "separator"}"#;
        let item: NativeMenuItem = serde_json::from_str(json).unwrap();
        assert_eq!(item.item_type, "separator");
        assert!(item.label.is_none());
    }

    #[test]
    fn test_checkable_item() {
        let json =
            r#"{"id": "dark-mode", "label": "Dark Mode", "checkable": true, "checked": true}"#;
        let item: NativeMenuItem = serde_json::from_str(json).unwrap();
        assert_eq!(item.id.as_deref(), Some("dark-mode"));
        assert!(item.checkable);
        assert!(item.checked);
    }

    #[test]
    fn test_disabled_item() {
        let json = r#"{"label": "Disabled", "enabled": false}"#;
        let item: NativeMenuItem = serde_json::from_str(json).unwrap();
        assert!(!item.enabled);
    }

    #[test]
    fn test_submenu() {
        let json = r#"{"label": "Edit", "submenu": [{"label": "Copy"}, {"type": "separator"}, {"label": "Paste"}]}"#;
        let item: NativeMenuItem = serde_json::from_str(json).unwrap();
        assert_eq!(item.submenu.len(), 3);
        assert_eq!(item.submenu[0].label.as_deref(), Some("Copy"));
        assert_eq!(item.submenu[1].item_type, "separator");
        assert_eq!(item.submenu[2].label.as_deref(), Some("Paste"));
    }

    #[test]
    fn test_item_with_role() {
        let json = r#"{"label": "Quit", "role": "quit", "id": "quit-btn"}"#;
        let item: NativeMenuItem = serde_json::from_str(json).unwrap();
        assert_eq!(item.role.as_deref(), Some("quit"));
        assert_eq!(item.id.as_deref(), Some("quit-btn"));
    }
}
