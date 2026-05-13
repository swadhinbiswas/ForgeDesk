use notify_rust::{Notification, Timeout};
use pyo3::prelude::*;

#[pyclass]
pub struct NotificationManager {}

#[pymethods]
impl NotificationManager {
    #[new]
    fn new() -> PyResult<Self> {
        Ok(NotificationManager {})
    }

    fn show(
        &self,
        summary: &str,
        body: &str,
        app_name: Option<&str>,
        icon: Option<&str>,
        timeout_ms: Option<u32>,
    ) -> PyResult<()> {
        let mut notif = Notification::new();
        notif.summary(summary).body(body);

        if let Some(app) = app_name {
            notif.appname(app);
        }

        if let Some(i) = icon {
            notif.icon(i);
        }

        if let Some(t) = timeout_ms {
            notif.timeout(Timeout::Milliseconds(t));
        }

        notif.show().map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to show notification: {}",
                e
            ))
        })?;

        Ok(())
    }
}
