use pyo3::prelude::*;

/// Guard for ensuring only a single instance of the application is running.
#[pyclass]
pub struct SingleInstanceGuard {
    _instance: single_instance::SingleInstance,
    is_single: bool,
}

#[pymethods]
impl SingleInstanceGuard {
    #[new]
    fn new(name: &str) -> PyResult<Self> {
        let instance = single_instance::SingleInstance::new(name).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Single instance error: {:?}",
                e
            ))
        })?;
        let is_single = instance.is_single();
        Ok(SingleInstanceGuard {
            _instance: instance,
            is_single,
        })
    }

    fn is_single(&self) -> bool {
        self.is_single
    }
}
