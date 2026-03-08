from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


IGNORE_NAMES = {
    "dist",
    "target",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".forge-data",
}


def _copy_project(source: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)

    def _ignore(directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in IGNORE_NAMES}

    shutil.copytree(source, dest, ignore=_ignore)


def _append_config(
    config_path: Path,
    *,
    formats: list[str],
    app_id: str,
    product_name: str,
    signing_mode: str,
    repo_root: Path,
) -> None:
    python_exe = Path(sys.executable).as_posix()
    lines = [
        "",
        "[packaging]",
        f'app_id = "{app_id}"',
        f'product_name = "{product_name}"',
        'category = "Utility"',
        "formats = [" + ", ".join(f'\"{fmt}\"' for fmt in formats) + "]",
    ]

    if signing_mode == "linux-gpg":
        lines.extend(
            [
                "",
                "[signing]",
                "enabled = true",
                'adapter = "gpg"',
                'identity = "Forge CI"',
            ]
        )
    elif signing_mode == "macos-ci":
        sign_script = (repo_root / "scripts" / "ci" / "sign_macos.py").as_posix()
        verify_script = (repo_root / "scripts" / "ci" / "verify_macos.py").as_posix()
        notarize_script = (repo_root / "scripts" / "ci" / "notarize_macos.py").as_posix()
        lines.extend(
            [
                "",
                "[signing]",
                "enabled = true",
                f'sign_command = "{python_exe} {sign_script}"',
                f'verify_command = "{python_exe} {verify_script}"',
                "notarize = true",
                f'notarize_command = "{python_exe} {notarize_script}"',
            ]
        )
    elif signing_mode == "windows-ci":
        sign_script = (repo_root / "scripts" / "ci" / "sign_windows.py").as_posix()
        verify_script = (repo_root / "scripts" / "ci" / "verify_windows.py").as_posix()
        lines.extend(
            [
                "",
                "[signing]",
                "enabled = true",
                f'sign_command = "{python_exe} {sign_script}"',
                f'verify_command = "{python_exe} {verify_script}"',
            ]
        )

    with config_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a Forge release fixture project")
    parser.add_argument("--source", required=True)
    parser.add_argument("--dest", required=True)
    parser.add_argument("--formats", required=True, help="Comma-separated packaging formats")
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--product-name", required=True)
    parser.add_argument(
        "--signing-mode",
        choices=["none", "linux-gpg", "macos-ci", "windows-ci"],
        default="none",
    )
    args = parser.parse_args()

    source = Path(args.source).resolve()
    dest = Path(args.dest).resolve()
    repo_root = Path(__file__).resolve().parents[2]

    _copy_project(source, dest)
    _append_config(
        dest / "forge.toml",
        formats=[item.strip() for item in args.formats.split(",") if item.strip()],
        app_id=args.app_id,
        product_name=args.product_name,
        signing_mode=args.signing_mode,
        repo_root=repo_root,
    )


if __name__ == "__main__":
    main()
