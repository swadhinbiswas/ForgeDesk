import contextlib
import logging
import sqlite3
import threading
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
DB_PATH = (BASE_DIR / "app_data.db").resolve()

db_lock = threading.Lock()


def init_db():
    logging.info(f"Initializing DB at {DB_PATH}")
    with db_lock:
        with contextlib.closing(
            sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        ) as conn:
            with conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
                )
                # Watchlist bound to user
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS watchlist (id INTEGER, user_id INTEGER, title TEXT, poster TEXT, rating REAL, PRIMARY KEY (id, user_id))"  # noqa: E501
                )
                # Users and Sessions
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)"  # noqa: E501
                )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER, created_at REAL)"  # noqa: E501
                )
