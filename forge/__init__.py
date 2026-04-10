"""
Forge Framework v3.0.

Build powerful, cross-platform desktop and web applications using
Python 3.14+ (NoGIL/free-threaded) as the backend and any web
technology (HTML/CSS/JS, React, Vue, Svelte) as the frontend.

Forge the future. Ship with Python.
"""

from __future__ import annotations

import os
import sys

from forge.app import ForgeApp
from forge.bridge import IPCBridge
from forge.config import ForgeConfig, ServerConfig, DatabaseConfig, RoutesConfig
from forge.events import EventEmitter
from forge.recovery import CircuitBreaker, CrashReporter, ErrorCode
from forge.router import Router
from forge.scope import ScopeValidator
from forge.state import AppState

if sys.platform.startswith("linux") and os.environ.get("XDG_SESSION_TYPE") == "wayland":
    # Prevent WebKitGTK (WPE) crashing persistently via Protocol Error 71 on Wayland
    os.environ.setdefault("WEBKIT_DISABLE_COMPOSITING_MODE", "1")

__version__ = "2.0.2"
__all__ = [
    "ForgeApp",
    "ForgeConfig",
    "ServerConfig",
    "DatabaseConfig",
    "RoutesConfig",
    "IPCBridge",
    "EventEmitter",
    "Router",
    "AppState",
    "CircuitBreaker",
    "CrashReporter",
    "ErrorCode",
    "ScopeValidator",
]
