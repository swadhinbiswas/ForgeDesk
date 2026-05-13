"""
Allow running Forge via `python -m forge`.

Provides a convenient alternative to the `forge` CLI entry point:

    python -m forge dev
    python -m forge build
    python -m forge doctor
    python -m forge info

This module simply delegates to the CLI entry point.
"""

from __future__ import annotations


def main() -> None:
    """Entry point for `python -m forge`."""
    try:
        from forge_cli.main import app

        app()
    except ImportError:
        import sys

        sys.exit(1)


if __name__ == "__main__":
    main()
