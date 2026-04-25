use muda::{CheckMenuItem, Menu, MenuId, MenuItem, PredefinedMenuItem, Submenu};
use pyo3::prelude::*;
use std::collections::HashMap;
use std::sync::Mutex;

use crate::menu::NativeMenuItem;

/// Managed application menu backed by muda.
///
/// Parses a JSON menu descriptor tree and builds
/// native platform menus (macOS menu bar, Windows menu, etc.).
#[pyclass(unsendable)]
pub struct MenuManager {
    menu: Menu,
    serialized_menu: Mutex<String>,
    /// Maps user-provided `id` → muda `MenuId` for event dispatch lookup.
    id_map: Mutex<HashMap<String, MenuId>>,
    /// Reverse map: muda MenuId → user-provided id string.
    reverse_map: Mutex<HashMap<MenuId, String>>,
}

#[pymethods]
impl MenuManager {
    #[new]
    fn new() -> PyResult<Self> {
        let menu = Menu::new();
        Ok(MenuManager {
            menu,
            serialized_menu: Mutex::new("[]".to_string()),
            id_map: Mutex::new(HashMap::new()),
            reverse_map: Mutex::new(HashMap::new()),
        })
    }

    /// Build the native platform menu from a JSON descriptor array.
    ///
    /// Each element is a top-level submenu (e.g. File, Edit, View).
    /// This replaces any previous menu items.
    fn set_items(&self, json_string: &str) -> PyResult<()> {
        let items: Vec<NativeMenuItem> = serde_json::from_str(json_string).map_err(|error| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Invalid menu JSON payload: {}",
                error
            ))
        })?;

        // Clear existing menu items by removing from position 0 repeatedly
        while self.menu.remove_at(0).is_some() {}

        // Clear ID mappings
        {
            let mut id_map = self.id_map.lock().unwrap();
            let mut rev_map = self.reverse_map.lock().unwrap();
            id_map.clear();
            rev_map.clear();
        }

        // Build native items from the descriptor tree
        for item in &items {
            if !item.submenu.is_empty() || item.item_type == "submenu" {
                // Top-level entry is a submenu (File, Edit, etc.)
                let label = item.label.as_deref().unwrap_or("Menu");
                let submenu = Submenu::new(label, item.enabled);
                self.build_submenu_children(&submenu, &item.submenu)?;

                // Register the submenu's own ID if user provided one
                if let Some(user_id) = &item.id {
                    let mut id_map = self.id_map.lock().unwrap();
                    let mut rev_map = self.reverse_map.lock().unwrap();
                    id_map.insert(user_id.clone(), submenu.id().clone());
                    rev_map.insert(submenu.id().clone(), user_id.clone());
                }

                self.menu.append(&submenu).map_err(|e| {
                    PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                        "Failed to append submenu '{}': {}",
                        label, e
                    ))
                })?;
            } else {
                // Top-level standalone item (unusual but supported)
                let native_item = self.build_normal_item(item)?;
                self.menu.append(&native_item).map_err(|e| {
                    PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                        "Failed to append top-level item: {}",
                        e
                    ))
                })?;
            }
        }

        // Cache the serialized form
        let mut guard = self.serialized_menu.lock().map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Failed to update native menu payload cache",
            )
        })?;
        *guard = json_string.to_string();
        Ok(())
    }

    fn get_items(&self) -> PyResult<String> {
        let guard = self.serialized_menu.lock().map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Failed to read native menu payload cache",
            )
        })?;
        Ok(guard.clone())
    }

    /// Look up the user-provided ID string for a muda MenuId.
    /// Used by the event loop to map menu click events back to user IDs.
    fn resolve_id(&self, muda_id_str: &str) -> PyResult<Option<String>> {
        let rev_map = self.reverse_map.lock().map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to read menu id map")
        })?;
        let menu_id = MenuId::new(muda_id_str);
        Ok(rev_map.get(&menu_id).cloned())
    }
}

impl MenuManager {
    /// Recursively populate a `Submenu` with child items.
    fn build_submenu_children(
        &self,
        submenu: &Submenu,
        children: &[NativeMenuItem],
    ) -> PyResult<()> {
        for child in children {
            if child.item_type == "separator" {
                submenu
                    .append(&PredefinedMenuItem::separator())
                    .map_err(|e| {
                        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                            "Failed to append separator: {}",
                            e
                        ))
                    })?;
            } else if !child.submenu.is_empty() || child.item_type == "submenu" {
                // Nested submenu
                let label = child.label.as_deref().unwrap_or("Submenu");
                let nested = Submenu::new(label, child.enabled);
                self.build_submenu_children(&nested, &child.submenu)?;
                if let Some(user_id) = &child.id {
                    let mut id_map = self.id_map.lock().unwrap();
                    let mut rev_map = self.reverse_map.lock().unwrap();
                    id_map.insert(user_id.clone(), nested.id().clone());
                    rev_map.insert(nested.id().clone(), user_id.clone());
                }
                submenu.append(&nested).map_err(|e| {
                    PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                        "Failed to append nested submenu: {}",
                        e
                    ))
                })?;
            } else if child.checkable {
                // Checkbox item
                let label = child.label.as_deref().unwrap_or("");
                let check_item = CheckMenuItem::new(
                    label,
                    child.enabled,
                    child.checked,
                    None::<muda::accelerator::Accelerator>,
                );
                if let Some(user_id) = &child.id {
                    let mut id_map = self.id_map.lock().unwrap();
                    let mut rev_map = self.reverse_map.lock().unwrap();
                    id_map.insert(user_id.clone(), check_item.id().clone());
                    rev_map.insert(check_item.id().clone(), user_id.clone());
                }
                submenu.append(&check_item).map_err(|e| {
                    PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                        "Failed to append check item: {}",
                        e
                    ))
                })?;
            } else if let Some(role) = &child.role {
                // Predefined role item (copy, paste, quit, etc.)
                if let Some(predefined) = predefined_from_role(role) {
                    submenu.append(&predefined).map_err(|e| {
                        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                            "Failed to append predefined item: {}",
                            e
                        ))
                    })?;
                } else {
                    // Unknown role, fall back to a normal item
                    let item = self.build_normal_item(child)?;
                    submenu.append(&item).map_err(|e| {
                        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                            "Failed to append item: {}",
                            e
                        ))
                    })?;
                }
            } else {
                // Normal clickable item
                let item = self.build_normal_item(child)?;
                submenu.append(&item).map_err(|e| {
                    PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                        "Failed to append item: {}",
                        e
                    ))
                })?;
            }
        }
        Ok(())
    }

    /// Build a normal `MenuItem` from a descriptor, registering its ID.
    fn build_normal_item(&self, item: &NativeMenuItem) -> PyResult<MenuItem> {
        let label = item.label.as_deref().unwrap_or("");
        let menu_item = MenuItem::new(label, item.enabled, None::<muda::accelerator::Accelerator>);
        if let Some(user_id) = &item.id {
            let mut id_map = self.id_map.lock().unwrap();
            let mut rev_map = self.reverse_map.lock().unwrap();
            id_map.insert(user_id.clone(), menu_item.id().clone());
            rev_map.insert(menu_item.id().clone(), user_id.clone());
        }
        Ok(menu_item)
    }

    /// Get a reference to the inner muda Menu for init_for_window.
    pub fn inner_menu(&self) -> &Menu {
        &self.menu
    }
}

/// Map a role string to a predefined OS menu item.
fn predefined_from_role(role: &str) -> Option<PredefinedMenuItem> {
    match role.to_lowercase().as_str() {
        "separator" => Some(PredefinedMenuItem::separator()),
        "copy" => Some(PredefinedMenuItem::copy(None)),
        "cut" => Some(PredefinedMenuItem::cut(None)),
        "paste" => Some(PredefinedMenuItem::paste(None)),
        "selectall" | "select_all" => Some(PredefinedMenuItem::select_all(None)),
        "undo" => Some(PredefinedMenuItem::undo(None)),
        "redo" => Some(PredefinedMenuItem::redo(None)),
        "minimize" => Some(PredefinedMenuItem::minimize(None)),
        "maximize" => Some(PredefinedMenuItem::maximize(None)),
        "hide" => Some(PredefinedMenuItem::hide(None)),
        "hideothers" | "hide_others" => Some(PredefinedMenuItem::hide_others(None)),
        "showall" | "show_all" => Some(PredefinedMenuItem::show_all(None)),
        "fullscreen" => Some(PredefinedMenuItem::fullscreen(None)),
        "quit" => Some(PredefinedMenuItem::quit(None)),
        "about" => Some(PredefinedMenuItem::about(None, Default::default())),
        "closewindow" | "close_window" => Some(PredefinedMenuItem::close_window(None)),
        "services" => Some(PredefinedMenuItem::services(None)),
        _ => None,
    }
}
