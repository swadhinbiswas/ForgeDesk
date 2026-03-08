import sys
import time
from forge import ForgeApp

app = ForgeApp()
app.config.permissions.lifecycle = True
app.config.permissions.filesystem = True

@app.on_ready
def ready(_):
    print("Checking single instance lock...")
    is_primary = app.lifecycle.request_single_instance_lock("my-test-app")
    if not is_primary:
        print("I AM A SECONDARY INSTANCE! EXITING!")
        sys.exit(0)
        
    print("I AM THE PRIMARY INSTANCE. HOLDING LOCK FOR 10 SECONDS...")
    time.sleep(10)
    print("SHUTTING DOWN")
    app.window.close()

if __name__ == "__main__":
    app.run()
