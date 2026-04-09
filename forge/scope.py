"""
Forge Scope Validator — Path and URL scope enforcement.

Security Model:
    - DENY always overrides ALLOW (deny-first evaluation)
    - Paths are resolved to absolute before matching
    - Glob patterns use fnmatch semantics (*, **, ?)
    - Symlinks are resolved before scope checks
    - Environment variables ($APPDATA, ~) are expanded before matching

This module is used by FileSystemAPI, ShellAPI, and the IPC bridge
to enforce granular access control beyond boolean capabilities.
"""

from __future__ import annotations

import fnmatch
import os
import sys
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse


def expand_scope_path(pattern: str, base_dir: Path | None = None) -> str:
    """Expand environment variables and ~ in a scope path pattern.

    Args:
        pattern: Raw pattern string from forge.toml (e.g. ``$APPDATA/myapp/**``).
        base_dir: Project root for resolving relative patterns.

    Returns:
        Expanded absolute pattern string.
    """
    p = pattern
    # Expand $APPDATA to the platform-appropriate directory
    if "$APPDATA" in p:
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
        elif sys.platform == "darwin":
            appdata = os.path.expanduser("~/Library/Application Support")
        else:
            appdata = os.path.expanduser("~/.config")
        p = p.replace("$APPDATA", appdata)

    p = os.path.expandvars(p)
    p = os.path.expanduser(p)

    # Make relative patterns absolute based on the project root
    if not os.path.isabs(p) and base_dir is not None:
        p = str(base_dir / p)

    return p


class ScopeValidator:
    """Validates file paths and URLs against allow/deny scope rules.

    Deny rules always take priority over allow rules. If a path matches
    both an allow and a deny rule, access is denied.

    Args:
        allow_patterns: Glob patterns for allowed paths/URLs.
        deny_patterns: Glob patterns for denied paths/URLs.
        base_dir: Project root for resolving relative patterns.
    """

    def __init__(
        self,
        allow_patterns: Sequence[str] = (),
        deny_patterns: Sequence[str] = (),
        base_dir: Path | None = None,
    ) -> None:
        self._base_dir = base_dir
        self._allow_expanded = [
            expand_scope_path(p, base_dir) for p in allow_patterns
        ]
        self._deny_expanded = [
            expand_scope_path(p, base_dir) for p in deny_patterns
        ]

    def is_path_allowed(self, path: str | Path) -> bool:
        """Check whether a filesystem path is allowed by the scopes.

        The path is resolved to absolute (following symlinks) before
        being matched against patterns.

        Args:
            path: The path to check.

        Returns:
            True if the path is allowed (matches allow and not deny).
        """
        resolved = str(Path(path).resolve())

        # Step 1: Check deny patterns first — deny always wins
        for deny_pat in self._deny_expanded:
            if self._matches(resolved, deny_pat):
                return False

        # Step 2: If no allow patterns are defined, allow everything
        # (the caller is relying on capability-level permission only)
        if not self._allow_expanded:
            return True

        # Step 3: Check allow patterns
        for allow_pat in self._allow_expanded:
            if self._matches(resolved, allow_pat):
                return True

        # Step 4: Not in allow list → denied
        return False

    def is_url_allowed(self, url: str) -> bool:
        """Check whether a URL is allowed by the scopes.

        URL matching uses fnmatch against the full URL string.
        ``deny_urls`` override ``allow_urls``.

        Args:
            url: The URL to check.

        Returns:
            True if the URL is allowed.
        """
        # Step 1: Check deny patterns
        for deny_pat in self._deny_expanded:
            if fnmatch.fnmatch(url, deny_pat):
                return False

        # Step 2: If no allow patterns, allow everything
        if not self._allow_expanded:
            return True

        # Step 3: Check allow patterns
        for allow_pat in self._allow_expanded:
            if fnmatch.fnmatch(url, allow_pat):
                return True

        return False

    @staticmethod
    def _matches(resolved_path: str, pattern: str) -> bool:
        """Match a resolved path against a scope pattern.

        Supports three matching modes:
        1. Exact directory prefix: ``/home/user/data`` matches anything inside it
        2. Glob with ``**``: ``/home/user/data/**`` matches recursively
        3. Fnmatch glob: ``/home/user/*.txt`` matches specific files
        """
        # Normalize trailing slashes
        pattern_clean = pattern.rstrip("/")

        # Check if the pattern is a directory prefix (no glob characters)
        if not any(c in pattern_clean for c in ("*", "?", "[")):
            # Exact directory prefix match
            resolved_clean = resolved_path.rstrip("/")
            return (
                resolved_clean == pattern_clean
                or resolved_clean.startswith(pattern_clean + "/")
            )

        # Glob matching — use fnmatch with ** support
        # For ** patterns, we need to check each path segment
        if "**" in pattern:
            # Convert ** to a catch-all by splitting and checking segments
            parts = pattern_clean.split("**")
            if len(parts) == 2:
                prefix, suffix = parts
                prefix = prefix.rstrip("/")
                suffix = suffix.lstrip("/")
                if not resolved_path.startswith(prefix):
                    return False
                remainder = resolved_path[len(prefix):].lstrip("/")
                if not suffix:
                    return True
                return fnmatch.fnmatch(remainder, suffix) or fnmatch.fnmatch(
                    os.path.basename(resolved_path), suffix
                )

        # Standard fnmatch
        return fnmatch.fnmatch(resolved_path, pattern_clean)
