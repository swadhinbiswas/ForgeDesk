use pyo3::prelude::*;
use rfd::{FileDialog, MessageDialog};

#[pyclass]
pub struct DialogManager {}

#[pymethods]
impl DialogManager {
    #[new]
    fn new() -> PyResult<Self> {
        Ok(DialogManager {})
    }

    fn open_file(
        &self,
        title: Option<&str>,
        directory: Option<&str>,
        filters_json: Option<&str>,
        multiple: Option<bool>,
    ) -> PyResult<Option<Vec<String>>> {
        let mut dialog = FileDialog::new();
        if let Some(t) = title {
            dialog = dialog.set_title(t);
        }
        if let Some(d) = directory {
            dialog = dialog.set_directory(d);
        }

        if let Some(fj) = filters_json {
            if let Ok(filters) = serde_json::from_str::<Vec<serde_json::Value>>(fj) {
                for filter in filters {
                    if let (Some(name), Some(exts)) = (
                        filter.get("name").and_then(|n| n.as_str()),
                        filter.get("extensions").and_then(|e| e.as_array()),
                    ) {
                        let e_str: Vec<&str> = exts.iter().filter_map(|e| e.as_str()).collect();
                        dialog = dialog.add_filter(name, &e_str);
                    }
                }
            }
        }

        if multiple.unwrap_or(false) {
            match dialog.pick_files() {
                Some(paths) => Ok(Some(
                    paths
                        .into_iter()
                        .map(|p| p.to_string_lossy().to_string())
                        .collect(),
                )),
                None => Ok(None),
            }
        } else {
            match dialog.pick_file() {
                Some(path) => Ok(Some(vec![path.to_string_lossy().to_string()])),
                None => Ok(None),
            }
        }
    }

    fn show_message(&self, title: &str, message: &str, level: &str) -> PyResult<()> {
        let mut dialog = MessageDialog::new()
            .set_title(title)
            .set_description(message);

        match level {
            "error" => dialog = dialog.set_level(rfd::MessageLevel::Error),
            "warning" => dialog = dialog.set_level(rfd::MessageLevel::Warning),
            _ => dialog = dialog.set_level(rfd::MessageLevel::Info),
        }

        dialog.show();
        Ok(())
    }

    fn confirm(&self, title: &str, message: &str, level: &str) -> PyResult<bool> {
        let mut dialog = MessageDialog::new()
            .set_title(title)
            .set_description(message)
            .set_buttons(rfd::MessageButtons::YesNo);

        match level {
            "error" => dialog = dialog.set_level(rfd::MessageLevel::Error),
            "warning" => dialog = dialog.set_level(rfd::MessageLevel::Warning),
            _ => dialog = dialog.set_level(rfd::MessageLevel::Info),
        }

        Ok(dialog.show() == rfd::MessageDialogResult::Yes)
    }

    fn save_file(
        &self,
        title: Option<&str>,
        directory: Option<&str>,
        file_name: Option<&str>,
        filters_json: Option<&str>,
    ) -> PyResult<Option<String>> {
        let mut dialog = FileDialog::new();
        if let Some(t) = title {
            dialog = dialog.set_title(t);
        }
        if let Some(d) = directory {
            dialog = dialog.set_directory(d);
        }
        if let Some(f) = file_name {
            dialog = dialog.set_file_name(f);
        }

        if let Some(fj) = filters_json {
            if let Ok(filters) = serde_json::from_str::<Vec<serde_json::Value>>(fj) {
                for filter in filters {
                    if let (Some(name), Some(exts)) = (
                        filter.get("name").and_then(|n| n.as_str()),
                        filter.get("extensions").and_then(|e| e.as_array()),
                    ) {
                        let e_str: Vec<&str> = exts.iter().filter_map(|e| e.as_str()).collect();
                        dialog = dialog.add_filter(name, &e_str);
                    }
                }
            }
        }

        match dialog.save_file() {
            Some(path) => Ok(Some(path.to_string_lossy().to_string())),
            None => Ok(None),
        }
    }

    fn select_folder(
        &self,
        title: Option<&str>,
        directory: Option<&str>,
    ) -> PyResult<Option<String>> {
        let mut dialog = FileDialog::new();
        if let Some(t) = title {
            dialog = dialog.set_title(t);
        }
        if let Some(d) = directory {
            dialog = dialog.set_directory(d);
        }

        match dialog.pick_folder() {
            Some(path) => Ok(Some(path.to_string_lossy().to_string())),
            None => Ok(None),
        }
    }
}
