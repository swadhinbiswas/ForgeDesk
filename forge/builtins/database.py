"""SQLite / KV / optional Postgres helpers (built-in extension)."""

from __future__ import annotations

import logging
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CAP = "forge_extensions"


class BuiltinDatabaseAPI:
    __forge_capability__ = _CAP

    def __init__(self, app: Any) -> None:
        self._app = app
        # Map of connection_id -> (sqlite3.Connection, per-connection Lock).
        # We keep the connections in the default ``check_same_thread=True``
        # mode (the safe default for sqlite) and serialise every operation
        # on the per-connection lock. The registry itself is guarded by
        # ``_registry_lock`` only for the open/close cases.
        self._sqlite: dict[str, tuple[sqlite3.Connection, threading.Lock]] = {}
        self._registry_lock = threading.Lock()

    def _resolve_path(self, path: str) -> Path:
        raw = Path(path).expanduser()
        if not raw.is_absolute():
            raw = self._app.config.get_base_dir() / raw
        return raw.resolve()

    def sqlite_open(self, path: str) -> dict[str, Any]:
        """Open a SQLite database under the app project directory (relative paths) or absolute."""
        p = self._resolve_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        cid = str(uuid.uuid4())
        conn = sqlite3.connect(str(p))
        with self._registry_lock:
            self._sqlite[cid] = (conn, threading.Lock())
        return {"connection_id": cid, "path": str(p)}

    def sqlite_execute(
        self,
        connection_id: str,
        sql: str,
        params: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Run SQL (INSERT/UPDATE/DDL). Params are passed as a list for ``?`` placeholders."""
        entry = self._sqlite.get(connection_id)
        if entry is None:
            return {"ok": False, "error": "unknown connection_id"}
        conn, conn_lock = entry
        try:
            with conn_lock:
                cur = conn.cursor()
                if params:
                    cur.execute(sql, params)
                else:
                    cur.execute(sql)
                conn.commit()
                return {"ok": True, "rowcount": cur.rowcount}
        except Exception as exc:
            logger.exception("sqlite_execute")
            try:
                conn.rollback()
            except Exception:
                pass
            return {"ok": False, "error": str(exc)}

    def sqlite_query(
        self,
        connection_id: str,
        sql: str,
        params: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Run a SELECT; returns rows as list of lists (JSON-serializable)."""
        entry = self._sqlite.get(connection_id)
        if entry is None:
            return {"ok": False, "error": "unknown connection_id", "rows": []}
        conn, conn_lock = entry
        try:
            with conn_lock:
                cur = conn.cursor()
                if params:
                    cur.execute(sql, params)
                else:
                    cur.execute(sql)
                rows = cur.fetchall()
                colnames = [d[0] for d in cur.description] if cur.description else []
                return {"ok": True, "columns": colnames, "rows": [list(r) for r in rows]}
        except Exception as exc:
            logger.exception("sqlite_query")
            return {"ok": False, "error": str(exc), "rows": []}

    def sqlite_close(self, connection_id: str) -> bool:
        with self._registry_lock:
            entry = self._sqlite.pop(connection_id, None)
        if entry is None:
            return False
        conn, conn_lock = entry
        with conn_lock:
            try:
                conn.close()
            except Exception:
                pass
        return True

    def kv_open(self, path: str) -> dict[str, Any]:
        """Open a file-backed key-value store (SQLite table ``kv``)."""
        return self.sqlite_open(path)

    def kv_set(self, connection_id: str, key: str, value: str) -> dict[str, Any]:
        self.sqlite_execute(
            connection_id,
            "CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT NOT NULL)",
        )
        return self.sqlite_execute(
            connection_id, "INSERT OR REPLACE INTO kv (k,v) VALUES (?,?)", [key, value]
        )

    def kv_get(self, connection_id: str, key: str) -> dict[str, Any]:
        q = self.sqlite_query(connection_id, "SELECT v FROM kv WHERE k = ?", [key])
        if not q.get("ok"):
            return q
        rows = q.get("rows") or []
        if not rows:
            return {"ok": True, "value": None}
        return {"ok": True, "value": rows[0][0] if rows[0] else None}

    def postgres_ping(self, dsn: str) -> dict[str, Any]:
        """Test PostgreSQL connectivity when ``psycopg`` or ``psycopg2`` is installed."""
        connect: Any
        try:
            import psycopg  # type: ignore[import-not-found]

            connect = psycopg.connect
        except ImportError:
            try:
                import psycopg2  # type: ignore[import-untyped]

                connect = psycopg2.connect
            except ImportError:
                return {"ok": False, "error": "install psycopg or psycopg2 for PostgreSQL support"}
        try:
            conn = connect(dsn)
            conn.close()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinDatabaseAPI(app))
