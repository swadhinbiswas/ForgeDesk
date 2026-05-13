from src.handlers.movies import register_movie_commands

from forge import Forge

app = Forge()

# Register commands
register_movie_commands(app)

if __name__ == "__main__":
    app.run()
