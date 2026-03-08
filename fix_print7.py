with open("src/lib.rs", "r") as f:
    lines = f.readlines()

new_text = """    fn register_shortcut(&self, accelerator: String) -> PyResult<bool> {
        let (tx, rx) = crossbeam_channel::bounded(1);
        if let Some(proxy) = &self.proxy {
            proxy.send_event(UserEvent::RegisterShortcut(accelerator, tx)).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to send register shortcut event: {}", e))
            })?;
            return Ok(rx.recv().unwrap_or(false));
        }
        Ok(false)
    }

    fn unregister_shortcut(&self, accelerator: String) -> PyResult<bool> {
        let (tx, rx) = crossbeam_channel::bounded(1);
        if let Some(proxy) = &self.proxy {
            proxy.send_event(UserEvent::UnregisterShortcut(accelerator, tx)).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to send unregister shortcut event: {}", e))
            })?;
            return Ok(rx.recv().unwrap_or(false));
        }
        Ok(false)
    }

    fn unregister_all(&self) -> PyResult<bool> {
        let (tx, rx) = crossbeam_channel::bounded(1);
        if let Some(proxy) = &self.proxy {
            proxy.send_event(UserEvent::UnregisterAllShortcuts(tx)).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to send unregister all shortcuts event: {}", e))
            })?;
            return Ok(rx.recv().unwrap_or(false));
        }
        Ok(false)
    }

    fn print(&self, label: String) -> PyResult<()> {
        if let Some(proxy) = &self.proxy {
            proxy.send_event(UserEvent::Print(label)).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to send print event: {}", e))
            })?;
        }
        Ok(())
    }
"""

start_idx = None
end_idx = None

for i in range(len(lines)):
    if "fn register_shortcut(&self, accelerator: String) -> PyResult<bool> {" in lines[i]:
        start_idx = i
        break

for i in range(start_idx, len(lines)):
    if "Event::UserEvent(UserEvent::SetProgressBar(progress)) =>" in lines[i]:
        end_idx = i
        break

lines = lines[:start_idx] + [new_text] + lines[end_idx:]

with open("src/lib.rs", "w") as f:
    f.writelines(lines)
