import json
import urllib.request
import urllib.parse
from src.config import TMDB_API_KEY, BASE_URL

MOCK_MOVIES = [
    {
        "id": 458156,
        "title": "John Wick: Chapter 3 - Parabellum",
        "overview": "Super-assassin John Wick returns with a $14 million price tag on his head and an army of bounty-hunting killers on his trail.",
        "poster_path": "/ziEuG1essDuWuC5lpWUaw1uXY2O.jpg",
        "backdrop_path": "/vVpEOvdxVBP2aV166j5Xlvb5Cdc.jpg",
        "release_date": "2019-05-17",
        "genre_ids": [28, 53],
        "genres": [{"id": 28, "name": "Action"}, {"id": 53, "name": "Thriller"}]
    },
    {
        "id": 245891,
        "title": "John Wick",
        "overview": "Ex-hitman John Wick comes out of retirement to track down the gangsters that took everything from him.",
        "poster_path": "/wylXy6Iab3m1rEqD7R0jOin2P1p.jpg",
        "backdrop_path": "/x2IqsMlJjk5rRzYq5Eun4y8YmO3.jpg",
        "release_date": "2014-10-24"
    },
    {
        "id": 1,
        "title": "Inception",
        "overview": "A thief who steals corporate secrets.",
        "poster_path": "/oYuLEt3zVCKq57qu2F8dT7NIa6f.jpg"
    }
]

class TMDBService:
    @staticmethod
    def _request(endpoint: str, params: dict):
        if not TMDB_API_KEY:
            # Return Mock Data simulating the screenshot
            if "popular" in endpoint:
                return {"results": MOCK_MOVIES}
            elif "search" in endpoint:
                query = params.get("query", "").lower()
                return {"results": [m for m in MOCK_MOVIES if query in m.get("title", "").lower()]}
            elif "/movie/" in endpoint:
                return MOCK_MOVIES[0]
            return {"results": MOCK_MOVIES}

        query = urllib.parse.urlencode({"api_key": TMDB_API_KEY, **params})
        url = f"{BASE_URL}{endpoint}?{query}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            return {"error": str(e)}

    @classmethod
    def get_popular(cls, page: int = 1):
        return cls._request("/movie/popular", {"page": page})

    @classmethod
    def search(cls, query: str, page: int = 1):
        return cls._request("/search/movie", {"query": query, "page": page})
        
    @classmethod
    def get_movie(cls, movie_id: int):
        return cls._request(f"/movie/{movie_id}", {})
