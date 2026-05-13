use arboard::Clipboard;
use pyo3::prelude::*;

#[pyclass]
pub struct ClipboardManager {
    // arboard::Clipboard manages its own handle, but we could wrap it.
}

#[pymethods]
impl ClipboardManager {
    #[new]
    fn new() -> PyResult<Self> {
        Ok(ClipboardManager {})
    }

    fn write_text(&self, text: &str) -> PyResult<()> {
        let mut ctx = Clipboard::new().map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to open clipboard: {}",
                e
            ))
        })?;
        ctx.set_text(text).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to write text to clipboard: {}",
                e
            ))
        })?;
        Ok(())
    }

    fn read_text(&self) -> PyResult<String> {
        let mut ctx = Clipboard::new().map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to open clipboard: {}",
                e
            ))
        })?;
        let text = ctx.get_text().map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to read text from clipboard: {}",
                e
            ))
        })?;
        Ok(text)
    }
}
