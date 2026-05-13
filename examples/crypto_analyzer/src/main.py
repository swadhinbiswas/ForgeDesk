# Import components
import api
import background
import db

import forge


def create_app():
    # Initialize DB
    db.init_db()

    # Create the forge app
    app = forge.ForgeApp()

    # Mount APIs
    api.register_routes(app)

    # Start background task for real-time updates
    background.start_worker(app)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
