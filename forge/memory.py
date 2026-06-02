"""Process-local binary buffer registry used by the bridge for `__forge_blob`
auto-routing and by the ``forge-memory://`` custom protocol handler.

The dict is mutated from:
  * the Python ``Bridge._success_response`` writer path (can be called from
    background tasks on Python 3.14+ free-threaded mode), and
  * the Rust protocol handler thread which acquires the GIL just to look up
    / delete an entry.

Under NoGIL a plain ``dict`` would race between these writers. A coarse
``threading.Lock`` is sufficient because the access pattern is "write once,
read once, delete once" and the entries are large byte payloads that
dominate the cost of acquiring the lock.
"""

from __future__ import annotations

import threading
from typing import Any

buffers: dict[str, Any] = {}
_buffers_lock = threading.Lock()


def put(key: str, value: Any) -> None:
    with _buffers_lock:
        buffers[key] = value


def take(key: str) -> Any:
    with _buffers_lock:
        return buffers.pop(key, None)


def get(key: str) -> Any:
    with _buffers_lock:
        return buffers.get(key)
