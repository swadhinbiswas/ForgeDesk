use pyo3::prelude::*;
use tray_icon::{TrayIcon, TrayIconBuilder};

#[pyclass(unsendable)]
pub struct TrayManager {
    tray: Option<TrayIcon>,
}

#[pymethods]
impl TrayManager {
    #[new]
    fn new() -> PyResult<Self> {
        Ok(TrayManager { tray: None })
    }

    fn set_tooltip(&mut self, tooltip: &str) -> PyResult<()> {
        if let Some(tray) = &mut self.tray {
            tray.set_tooltip(Some(tooltip)).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                    "Failed to set tooltip: {}",
                    e
                ))
            })?;
        }
        Ok(())
    }

    fn set_visible(&mut self, visible: bool) -> PyResult<()> {
        if let Some(tray) = &mut self.tray {
            tray.set_visible(visible).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                    "Failed to set visible: {}",
                    e
                ))
            })?;
        } else if visible {
            let tray = TrayIconBuilder::new().build().map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                    "Failed to build tray: {}",
                    e
                ))
            })?;
            self.tray = Some(tray);
        }
        Ok(())
    }
}
