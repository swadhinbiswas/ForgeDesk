from src.services.tmdb import TMDBService

def register_movie_commands(app):
    @app.command
    def fetch_popular_movies(page: int = 1):
        return TMDBService.get_popular(page)

    @app.command
    def search_movies(query: str, page: int = 1):
        return TMDBService.search(query, page)
        
    @app.command
    def fetch_movie_details(movie_id: int):
        return TMDBService.get_movie(movie_id)
