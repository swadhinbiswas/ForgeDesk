from forge import Forge
from src.handlers.movies import register_movie_commands

app = Forge()

# Register commands
register_movie_commands(app)

if __name__ == "__main__":
    app.run()
