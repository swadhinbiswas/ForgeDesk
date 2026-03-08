with open("src/lib.rs", "r") as f:
    text = f.read()

text = text.replace("""        if let Some(proxy) = &self.proxy {
            proxy.send_event(UserEvent::RegisterShortcut(accelerator, tx)).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to send register shortcut event: {}", e))
            })?;
            return Ok(rx.recv().unwrap_or(false));
        }
        Ok(false)""", """        self.proxy.send_event(UserEvent::RegisterShortcut(accelerator, tx)).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to send register shortcut event: {}", e))
        })?;
        Ok(rx.recv().unwrap_or(false))""")

text = text.replace("""        if let Some(proxy) = &self.proxy {
            proxy.send_event(UserEvent::UnregisterShortcut(accelerator, tx)).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to send unregister shortcut event: {}", e))
            })?;
            return Ok(rx.recv().unwrap_or(false));
        }
        Ok(false)""", """        self.proxy.send_event(UserEvent::UnregisterShortcut(accelerator, tx)).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to send unregister shortcut event: {}", e))
        })?;
        Ok(rx.recv().unwrap_or(false))""")

text = text.replace("""        if let Some(proxy) = &self.proxy {
            proxy.send_event(UserEvent::UnregisterAllShortcuts(tx)).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to send unregister all shortcuts event: {}", e))
            })?;
            return Ok(rx.recv().unwrap_or(false));
        }
        Ok(false)""", """        self.proxy.send_event(UserEvent::UnregisterAllShortcuts(tx)).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to send unregister all shortcuts event: {}", e))
        })?;
        Ok(rx.recv().unwrap_or(false))""")

text = text.replace("""        if let Some(proxy) = &self.proxy {
            proxy.send_event(UserEvent::Print(label)).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to send print event: {}", e))
            })?;
        }
        Ok(())""", """        self.proxy.send_event(UserEvent::Print(label)).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to send print event: {}", e))
        })?;
        Ok(())""")

with open("src/lib.rs", "w") as f:
    f.write(text)
