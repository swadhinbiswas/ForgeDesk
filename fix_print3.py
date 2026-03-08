with open("src/lib.rs", "r") as f:
    text = f.read()

import re
text = re.sub(
r'''                        Err\(_\) => \{
                            let _ = tx\.send\(false\);
                    \}
                \}
                Event::UserEvent\(UserEvent::UnregisterAllShortcuts\(tx\)\) => \{''',
'''                        Err(_) => {
                            let _ = tx.send(false);
                        }
                    }
                }
                Event::UserEvent(UserEvent::UnregisterAllShortcuts(tx)) => {''', text)

with open("src/lib.rs", "w") as f:
    f.write(text)
