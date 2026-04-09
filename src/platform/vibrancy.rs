/// Apply vibrancy/blur effects to a native window.
///
/// Platform-specific: macOS uses NSVisualEffectMaterial, Windows uses Mica/Acrylic/Blur.
/// Linux has no vibrancy support (no-op).

/// Apply vibrancy effect to a window on macOS.
#[cfg(target_os = "macos")]
pub fn apply_vibrancy_to_window(window: &tao::window::Window, effect: &str) {
    use window_vibrancy::{apply_vibrancy, NSVisualEffectMaterial};
    let material = match effect {
        "appearance_based" => Some(NSVisualEffectMaterial::AppearanceBased),
        "light" => Some(NSVisualEffectMaterial::Light),
        "dark" => Some(NSVisualEffectMaterial::Dark),
        "titlebar" => Some(NSVisualEffectMaterial::Titlebar),
        "selection" => Some(NSVisualEffectMaterial::Selection),
        "menu" => Some(NSVisualEffectMaterial::Menu),
        "popover" => Some(NSVisualEffectMaterial::Popover),
        "sidebar" => Some(NSVisualEffectMaterial::Sidebar),
        "header_view" => Some(NSVisualEffectMaterial::HeaderView),
        "sheet" => Some(NSVisualEffectMaterial::Sheet),
        "window_background" => Some(NSVisualEffectMaterial::WindowBackground),
        "hud_window" => Some(NSVisualEffectMaterial::HudWindow),
        "full_screen_ui" => Some(NSVisualEffectMaterial::FullScreenUI),
        "tooltip" => Some(NSVisualEffectMaterial::Tooltip),
        "content_background" => Some(NSVisualEffectMaterial::ContentBackground),
        "under_window_background" => Some(NSVisualEffectMaterial::UnderWindowBackground),
        "under_page_background" => Some(NSVisualEffectMaterial::UnderPageBackground),
        _ => None,
    };
    if let Some(mat) = material {
        let _ = apply_vibrancy(window, mat, None, None);
    }
}

/// Apply vibrancy effect to a window on Windows.
#[cfg(target_os = "windows")]
pub fn apply_vibrancy_to_window(window: &tao::window::Window, effect: &str) {
    use window_vibrancy::{apply_acrylic, apply_blur, apply_mica};
    match effect {
        "mica" => {
            let _ = apply_mica(window, None);
        }
        "acrylic" => {
            let _ = apply_acrylic(window, None);
        }
        "blur" => {
            let _ = apply_blur(window, None);
        }
        _ => {}
    }
}

/// No-op vibrancy on Linux.
#[cfg(target_os = "linux")]
pub fn apply_vibrancy_to_window(_window: &tao::window::Window, _effect: &str) {
    // Vibrancy is not supported on Linux
}
