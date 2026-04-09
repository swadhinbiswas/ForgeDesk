use pyo3::prelude::*;

/// Manager for OS keychain (credential store) operations.
#[pyclass]
pub struct KeychainManager {
    service: String,
}

#[pymethods]
impl KeychainManager {
    #[new]
    fn new(service: &str) -> PyResult<Self> {
        Ok(KeychainManager {
            service: service.to_string(),
        })
    }

    fn set_password(&self, user: &str, password: &str) -> PyResult<()> {
        let entry = keyring::Entry::new(&self.service, user).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to get keyring entry: {}",
                e
            ))
        })?;
        entry.set_password(password).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to set password: {}",
                e
            ))
        })?;
        Ok(())
    }

    fn get_password(&self, user: &str) -> PyResult<String> {
        let entry = keyring::Entry::new(&self.service, user).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to get keyring entry: {}",
                e
            ))
        })?;
        let password = entry.get_password().map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to get password: {}",
                e
            ))
        })?;
        Ok(password)
    }

    fn delete_password(&self, user: &str) -> PyResult<()> {
        let entry = keyring::Entry::new(&self.service, user).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to get keyring entry: {}",
                e
            ))
        })?;
        entry.delete_credential().map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to delete password: {}",
                e
            ))
        })?;
        Ok(())
    }
}
