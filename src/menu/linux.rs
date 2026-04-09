#![cfg(target_os = "linux")]

use gtk::prelude::*;

use crate::menu::{MenuEmitter, NativeMenuItem};

/// Remove all children from a GTK menu bar.
pub fn clear_linux_menu(menu_bar: &gtk::MenuBar) {
    for child in menu_bar.children() {
        menu_bar.remove(&child);
    }
}

/// Build a single GTK menu widget from a NativeMenuItem descriptor.
pub fn build_linux_menu_widget(item: &NativeMenuItem, emit: MenuEmitter) -> gtk::MenuItem {
    if item.item_type == "separator" {
        return gtk::SeparatorMenuItem::new().upcast::<gtk::MenuItem>();
    }

    if item.checkable {
        let menu_item = match &item.label {
            Some(label) => gtk::CheckMenuItem::with_label(label),
            None => gtk::CheckMenuItem::new(),
        };
        menu_item.set_sensitive(item.enabled);
        menu_item.set_active(item.checked);
        if let Some(item_id) = item.id.clone() {
            let label = item.label.clone();
            let role = item.role.clone();
            let emit_checked = emit.clone();
            menu_item.connect_toggled(move |entry| {
                emit_checked(
                    item_id.clone(),
                    label.clone(),
                    role.clone(),
                    Some(entry.is_active()),
                );
            });
        }
        return menu_item.upcast::<gtk::MenuItem>();
    }

    let menu_item = match &item.label {
        Some(label) => gtk::MenuItem::with_label(label),
        None => gtk::MenuItem::new(),
    };
    menu_item.set_sensitive(item.enabled);

    if !item.submenu.is_empty() {
        let submenu = gtk::Menu::new();
        for child in &item.submenu {
            let child_widget = build_linux_menu_widget(child, emit.clone());
            submenu.append(&child_widget);
        }
        menu_item.set_submenu(Some(&submenu));
    } else if let Some(item_id) = item.id.clone() {
        let label = item.label.clone();
        let role = item.role.clone();
        let emit_click = emit.clone();
        menu_item.connect_activate(move |_| {
            emit_click(item_id.clone(), label.clone(), role.clone(), None);
        });
    }

    menu_item
}

/// Apply a menu model (JSON) to a GTK menu bar.
///
/// Clears the existing menu, parses the JSON, and builds new GTK widgets.
/// Returns the number of top-level items or an error.
pub fn apply_linux_menu(
    menu_bar: &gtk::MenuBar,
    menu_json: &str,
    emit: MenuEmitter,
) -> Result<usize, String> {
    let items: Vec<NativeMenuItem> =
        serde_json::from_str(menu_json).map_err(|e| format!("Invalid menu payload: {}", e))?;

    clear_linux_menu(menu_bar);

    if items.is_empty() {
        menu_bar.hide();
        return Ok(0);
    }

    for item in &items {
        let widget = build_linux_menu_widget(item, emit.clone());
        menu_bar.append(&widget);
    }

    menu_bar.show_all();
    Ok(items.len())
}
