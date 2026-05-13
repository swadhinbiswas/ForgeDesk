import contextlib
import json
import logging
import sqlite3
import time
import urllib.request
import uuid
from pathlib import Path

from forge import ForgeApp

from .api import fetch_tmdb
from .db import DB_PATH, db_lock, init_db

BASE_DIR = Path(__file__).parent.parent.parent
LOG_PATH = (BASE_DIR / "app.log").resolve()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)

app = ForgeApp()
app._logger = logging.getLogger("forge")

init_db()


@app.command
def get_setting(key: str) -> str:
    try:
        with db_lock:
            with contextlib.closing(
                sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
            ) as conn:
                cursor = conn.execute("SELECT value FROM settings WHERE key=?", (key,))
                row = cursor.fetchone()
                return row[0] if row else ""
    except Exception as e:
        logging.error(f"Failed to get setting '{key}': {e}")
        return ""


@app.command
def save_setting(key: str, value: str) -> bool:
    try:
        with db_lock:
            with contextlib.closing(
                sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
            ) as conn:
                with conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
                    )
        return True
    except Exception as e:
        logging.error(f"Failed to save setting '{key}': {e}")
        return False


@app.command
def check_api_key(key: str) -> bool:
    try:
        url = f"https://api.themoviedb.org/3/authentication?api_key={key}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            return data.get("success", False)
    except Exception:
        return False


@app.command
def login(username, password):
    with db_lock:
        with contextlib.closing(
            sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        ) as conn:
            cursor = conn.execute(
                "SELECT id FROM users WHERE username=? AND password=?", (username, password)
            )
            row = cursor.fetchone()
            if not row:
                # auto register if user doesn't exist (for simplicity)
                cursor = conn.execute("SELECT id FROM users WHERE username=?", (username,))
                if cursor.fetchone():
                    return {"error": "Invalid password"}
                with conn:
                    cursor = conn.execute(
                        "INSERT INTO users (username, password) VALUES (?, ?)", (username, password)
                    )
                    user_id = cursor.lastrowid
            else:
                user_id = row[0]

            token = str(uuid.uuid4())
            with conn:
                conn.execute(
                    "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
                    (token, user_id, time.time()),
                )
            return {"token": token, "username": username}


@app.command
def get_dashboard_data() -> dict:
    try:
        key = get_setting("tmdb_key")
        if not key:
            return {"error": "API Key is not configured"}
        popular = fetch_tmdb("movie/popular", key).get("results", [])
        top_rated = fetch_tmdb("movie/top_rated", key).get("results", [])
        upcoming = fetch_tmdb("movie/upcoming", key).get("results", [])
        return {
            "hero": popular[0] if popular else None,
            "parties": upcoming[:4],
            "continue_watching": top_rated[:5],
            "popular": popular,
        }
    except Exception as e:
        return {"error": str(e)}


@app.command
def get_movie_details(movie_id: int) -> dict:
    try:
        key = get_setting("tmdb_key")
        if not key:
            return {"error": "API Key missing"}
        movie = fetch_tmdb(f"movie/{movie_id}", key, params={"append_to_response": "credits"})
        return movie
    except Exception as e:
        return {"error": str(e)}


def _get_user_id(token: str, conn):
    cursor = conn.execute("SELECT user_id FROM sessions WHERE token=?", (token,))
    row = cursor.fetchone()
    return row[0] if row else None


@app.command
def toggle_watchlist(token: str, movie: dict) -> bool:
    try:
        with db_lock:
            with contextlib.closing(
                sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
            ) as conn:
                user_id = _get_user_id(token, conn)
                if not user_id:
                    return False

                movie_id = movie.get("id")
                cursor = conn.execute(
                    "SELECT id FROM watchlist WHERE id=? AND user_id=?", (movie_id, user_id)
                )
                if cursor.fetchone():
                    with conn:
                        conn.execute(
                            "DELETE FROM watchlist WHERE id=? AND user_id=?", (movie_id, user_id)
                        )
                    return False
                else:
                    with conn:
                        conn.execute(
                            "INSERT INTO watchlist (id, user_id, title, poster, rating) VALUES (?, ?, ?, ?, ?)",  # noqa: E501
                            (
                                movie_id,
                                user_id,
                                movie.get("title"),
                                movie.get("poster_path"),
                                movie.get("vote_average"),
                            ),
                        )
                    return True
    except Exception:
        return False


@app.command
def get_watchlist(token: str) -> list:
    try:
        with db_lock:
            with contextlib.closing(
                sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
            ) as conn:
                user_id = _get_user_id(token, conn)
                if not user_id:
                    return []
                cursor = conn.execute(
                    "SELECT id, title, poster, rating FROM watchlist WHERE user_id=?", (user_id,)
                )
                return [
                    {"id": r[0], "title": r[1], "poster_path": r[2], "vote_average": r[3]}
                    for r in cursor.fetchall()
                ]
    except Exception:
        return []
