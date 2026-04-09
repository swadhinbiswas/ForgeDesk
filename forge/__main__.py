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
        print(
            "Error: forge-cli is not installed.\n"
            "Install it with: pip install forge-framework[cli]",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
