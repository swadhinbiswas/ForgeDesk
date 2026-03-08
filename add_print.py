with open("src/lib.rs", "r") as f:
    text = f.read()

text = text.replace("    UnregisterAllShortcuts(crossbeam_channel::Sender<bool>),", "    UnregisterAllShortcuts(crossbeam_channel::Sender<bool>),\n    Print(String),")

to_replace = """    fn unregister_all_shortcuts(&self) -> PyResult<bool> {
        let (tx, rx) = crossbeam_channel::bounded(1);
        self.proxy.send_event(UserEvent::UnregisterAllShortcuts(tx)).map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send unregister all shortcuts event")
        })?;
        rx.recv().map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to receive shortcut unregistration status")
        })
    }"""

new_text = to_replace + """

    fn print(&self, label: String) -> PyResult<()> {
        self.proxy.send_event(UserEvent::Print(label)).map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Failed to send print event")
        })?;
        Ok(())
    }"""

text = text.replace(to_replace, new_text)

event_match_to_replace = """                Event::UserEvent(UserEvent::UnregisterAllShortcuts(tx)) => {
                    for (_, hotkey) in registered_hotkeys.drain() {
                        let _ = hotkey_manager.unregister(hotkey);
                    }
                    hotkey_id_to_string.clear();
                    let _ = tx.send(true);
                }"""

event_match_new = event_match_to_replace + """
                Event::UserEvent(UserEvent::Print(label)) => {
                    if let Some(window_id) = labels_to_id.get(&label) {
                        if let Some(runtime_window) = windows_by_id.get(window_id) {
                            let _ = runtime_window.webview.print();
                        }
                    }
                }"""
text = text.replace(event_match_to_replace, event_match_new)

with open("src/lib.rs", "w") as f:
    f.write(text)
