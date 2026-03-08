import os
import json
from forge import ForgeApp

app = ForgeApp()
app.config.permissions.screen = True
app.config.permissions.filesystem = True

@app.on_ready
def ready(_):
    print("READY!")
    print("MONITORS:", app.screen.get_monitors())
    print("PRIMARY:", app.screen.get_primary_monitor())
    print("CURSOR:", app.screen.get_cursor_screen_point())
    app.window.close()

if __name__ == "__main__":
    app.run()
