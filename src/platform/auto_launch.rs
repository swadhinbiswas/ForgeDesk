use pyo3::prelude::*;

/// Manager for setting the application to start automatically at login.
#[pyclass]
pub struct AutoLaunchManager {
    inner: auto_launch::AutoLaunch,
}

#[pymethods]
impl AutoLaunchManager {
    #[new]
    fn new(app_name: &str) -> PyResult<Self> {
        let app_path = std::env::current_exe().map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to get executable path: {}",
                e
            ))
        })?;
        let path_str = app_path.to_str().ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Invalid executable path")
        })?;
        let auto_launch = auto_launch::AutoLaunchBuilder::new()
            .set_app_name(app_name)
            .set_app_path(path_str)
            .build()
            .map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                    "Failed to build auto_launch: {}",
                    e
                ))
            })?;
        Ok(AutoLaunchManager { inner: auto_launch })
    }

    fn enable(&self) -> PyResult<bool> {
        self.inner.enable().map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to enable autostart: {}",
                e
            ))
        })?;
        Ok(true)
    }

    fn disable(&self) -> PyResult<bool> {
        self.inner.disable().map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to disable autostart: {}",
                e
            ))
        })?;
        Ok(true)
    }

    fn is_enabled(&self) -> PyResult<bool> {
        self.inner.is_enabled().map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to check autostart: {}",
                e
            ))
        })
    }
}
