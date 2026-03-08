"""
Forge Framework v2.0.

Build powerful, cross-platform desktop and web applications using
Python 3.14+ (NoGIL/free-threaded) as the backend and any web
technology (HTML/CSS/JS, React, Vue, Svelte) as the frontend.

Forge the future. Ship with Python.
"""

from __future__ import annotations

from forge.app import ForgeApp, command
from forge.bridge import IPCBridge
from forge.config import ForgeConfig, ServerConfig, DatabaseConfig, RoutesConfig
from forge.events import EventEmitter

__version__ = "2.0.0"
__all__ = [
    "ForgeApp",
    "ForgeConfig",
    "ServerConfig",
    "DatabaseConfig",
    "RoutesConfig",
    "IPCBridge",
    "EventEmitter",
    "command",
]
