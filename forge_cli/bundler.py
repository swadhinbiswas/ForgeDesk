"""
Forge Production Bundler.

Encapsulates the multi-stage build pipeline:

1. **Validation**  — Pre-flight checks (entry point, frontend, build tools)
2. **Frontend**    — Bundle frontend assets (copy static, or run npm/vite/trunk build)
3. **Binary**      — Compile Python + Rust into a native binary (maturin or Nuitka)
4. **Package**     — Generate platform-specific descriptors and installers
5. **Sign**        — Execute code signing hooks if configured

This module is the extracted, testable core behind `forge build`.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ─── Configuration ───

@dataclass
class BundleConfig:
    """Resolved bundle configuration for a single build invocation.

    Created from a ForgeConfig + CLI options, with platform detection
    and builder selection applied.
    """

    app_name: str
    entry_point: Path
    frontend_dir: Path
    output_dir: Path
    project_dir: Path
    target: str = "desktop"  # "desktop" | "web"

    # Builder selection
    builder: str = "nuitka"  # "nuitka" | "maturin"
    builder_path: Optional[str] = None

    # Icons
    icon: Optional[Path] = None

    # Platform
    host_platform: str = field(default_factory=platform.system)

    # Packaging formats
    formats: list[str] = field(default_factory=list)

    @classmethod
    def from_forge_config(cls, config: Any, project_dir: Path, output_dir: Optional[Path] = None) -> "BundleConfig":
        """Create a BundleConfig from a loaded ForgeConfig."""
        resolved_output = output_dir or (project_dir / config.build.output_dir)
        icon_path = (project_dir / config.build.icon) if config.build.icon else None

        # Detect builder
        builder_info = detect_build_tool(project_dir)

        return cls(
            app_name=config.app.name,
            entry_point=config.get_entry_path(),
            frontend_dir=config.get_frontend_path(),
            output_dir=resolved_output,
            project_dir=project_dir,
            builder=builder_info["name"],
            builder_path=builder_info.get("path"),
            icon=icon_path,
            formats=list(getattr(config.packaging, "formats", [])),
        )

    @property
    def safe_app_name(self) -> str:
        """Filesystem-safe application name."""
        return self.app_name.replace(" ", "_").lower()


# ─── Build Tool Detection ───

def detect_build_tool(project_dir: Path) -> dict[str, Any]:
    """Detect the best available build tool for the project.

    Priority:
        1. maturin (if Cargo.toml exists and maturin is installed)
        2. Nuitka (Python-only compilation)

    Returns:
        Dict with 'name', 'mode', 'available', and 'path' keys.
    """
    cargo_toml = project_dir / "Cargo.toml"
    maturin_path = shutil.which("maturin")

    if cargo_toml.exists() and maturin_path:
        return {
            "name": "maturin",
            "mode": "hybrid",
            "available": True,
            "path": maturin_path,
        }

    nuitka_available = _module_available("nuitka")
    if nuitka_available:
        return {
            "name": "nuitka",
            "mode": "python",
            "available": True,
            "path": sys.executable,
        }

    return {
        "name": "maturin" if cargo_toml.exists() else "nuitka",
        "mode": "hybrid" if cargo_toml.exists() else "python",
        "available": False,
        "path": maturin_path,
    }


def _module_available(name: str) -> bool:
    """Check if a Python module is importable."""
    import importlib.util
    return importlib.util.find_spec(name) is not None


# ─── Validation ───

@dataclass
class ValidationResult:
    """Result of pre-build validation checks."""
    ok: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.ok = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def validate_bundle(bundle: BundleConfig) -> ValidationResult:
    """Run pre-build validation checks.

    Checks:
        - Target is valid ('desktop' or 'web')
        - Entry point exists (desktop only)
        - Frontend directory exists
        - Build tool is available (desktop only)
        - Icon file exists (if configured)
    """
    result = ValidationResult()

    if bundle.target not in {"desktop", "web"}:
        result.add_error(f"Unsupported build target: {bundle.target}")
        return result

    if bundle.target == "desktop":
        if not bundle.entry_point.exists():
            result.add_error(f"Entry point missing: {bundle.entry_point}")

        build_info = detect_build_tool(bundle.project_dir)
        if not build_info["available"]:
            result.add_error(
                "No supported desktop build tool found. "
                "Install maturin (for Rust+Python hybrid) or Nuitka (pip install nuitka)."
            )

    if not bundle.frontend_dir.exists():
        result.add_error(f"Frontend directory missing: {bundle.frontend_dir}")

    if bundle.icon and not bundle.icon.exists():
        result.add_warning(f"Configured icon not found: {bundle.icon}")

    return result


# ─── Build Pipeline ───

class BundlePipeline:
    """Multi-stage build pipeline.

    Stages:
        1. validate()     — Pre-flight checks
        2. bundle_frontend() — Copy/build frontend assets
        3. build_binary()    — Compile native binary
        4. package()         — Generate platform installers
    """

    def __init__(self, config: BundleConfig) -> None:
        self.config = config
        self.artifacts: list[str] = []

    def validate(self) -> ValidationResult:
        """Run validation and return the result."""
        return validate_bundle(self.config)

    def bundle_frontend(self) -> dict[str, Any]:
        """Copy frontend assets to the output directory.

        If a ``package.json`` exists with a ``build`` script, runs
        ``npm run build`` first to generate production assets.

        Returns:
            Dict with status and list of copied artifacts.
        """
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        frontend_src = self.config.frontend_dir
        dest_name = "static" if self.config.target == "web" else "frontend"
        frontend_dist = self.config.output_dir / dest_name

        if not frontend_src.exists():
            return {"status": "skipped", "reason": "no frontend directory"}

        # Check for package.json → npm run build
        package_json = frontend_src / "package.json"
        if package_json.exists() and shutil.which("npm"):
            try:
                subprocess.run(
                    ["npm", "run", "build"],
                    cwd=str(frontend_src),
                    check=True,
                    capture_output=True,
                    text=True,
                )
                logger.info("Frontend build completed via npm run build")
            except subprocess.CalledProcessError as e:
                logger.warning("npm run build failed: %s", e.stderr[:500] if e.stderr else "")
            except FileNotFoundError:
                pass

        if frontend_dist.exists():
            shutil.rmtree(frontend_dist)
        shutil.copytree(frontend_src, frontend_dist)
        self.artifacts.append(str(frontend_dist))

        return {
            "status": "ok",
            "frontend_dir": str(frontend_dist),
            "artifacts": [str(frontend_dist)],
        }

    def bundle_sidecars(self) -> dict[str, Any]:
        """Copy sidecar binaries to the output directory.

        Returns:
            Dict with status and list of copied sidecar paths.
        """
        bin_src = self.config.project_dir / "bin"
        bin_dist = self.config.output_dir / "bin"

        if not bin_src.exists():
            return {"status": "skipped", "reason": "no bin/ directory"}

        if bin_dist.exists():
            shutil.rmtree(bin_dist)
        shutil.copytree(bin_src, bin_dist)
        self.artifacts.append(str(bin_dist))

        return {"status": "ok", "sidecar_dir": str(bin_dist)}

    def build_binary(self) -> dict[str, Any]:
        """Compile the native binary using the detected build tool.

        Returns:
            Dict with builder name, status, and build arguments used.
        """
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        if self.config.builder == "maturin":
            build_args = [
                "maturin", "build", "--release",
                "--out", str(self.config.output_dir),
            ]
        else:
            build_args = [
                sys.executable, "-m", "nuitka",
                "--standalone",
                f"--output-dir={self.config.output_dir}",
                f"--output-filename={self.config.safe_app_name}",
            ]
            if self.config.icon and self.config.icon.exists():
                build_args.append(f"--linux-icon={self.config.icon}")
            build_args.append(str(self.config.entry_point))

        result = subprocess.run(
            build_args,
            check=True,
            capture_output=True,
            text=True,
        )

        return {
            "status": "ok",
            "builder": self.config.builder,
            "args": build_args,
            "stdout": result.stdout[:500],
        }

    def package(self) -> dict[str, Any]:
        """Generate platform installers for configured formats.
        
        Bubbles up subprocess errors cleanly without hanging.
        """
        results = []
        if not self.config.formats:
            return {"status": "skipped", "reason": "no packaging formats configured"}

        for fmt in self.config.formats:
            try:
                res = self._package_format(fmt)
                results.append(res)
            except subprocess.CalledProcessError as e:
                logger.error(f"Packaging failed for {fmt}: {e.stderr or e.stdout or str(e)}")
                msg = e.stderr or e.stdout or str(e)
                raise RuntimeError(f"Packaging format {fmt} failed: {msg}") from e
            except Exception as e:
                logger.error(f"Packaging failed for {fmt}: {e}")
                raise RuntimeError(f"Packaging format {fmt} failed: {e}") from e

        return {"status": "ok", "results": results}

    def _package_format(self, fmt: str) -> dict[str, Any]:
        """Run the specific packaging tool for a format."""
        output_dir = Path(self.config.output_dir)
        app_name = self.config.app_name
        safe_name = self.config.safe_app_name
        
        dist_dir = output_dir / f"{safe_name}.dist"
        if not dist_dir.exists():
            dist_dir = output_dir

        cmd = []

        if self.config.host_platform == "Darwin" and fmt in ("app", "dmg"):
            app_bundle = output_dir / f"{app_name}.app"
            macos_dir = app_bundle / "Contents" / "MacOS"
            resources_dir = app_bundle / "Contents" / "Resources"
            macos_dir.mkdir(parents=True, exist_ok=True)
            resources_dir.mkdir(parents=True, exist_ok=True)
            
            info_plist = app_bundle / "Contents" / "Info.plist"
            info_plist.write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n'
                                  f'<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                                  f'<plist version="1.0">\n'
                                  f'<dict>\n'
                                  f'    <key>CFBundleExecutable</key>\n'
                                  f'    <string>{safe_name}</string>\n'
                                  f'    <key>CFBundleIdentifier</key>\n'
                                  f'    <string>com.forge.{safe_name}</string>\n'
                                  f'    <key>CFBundleName</key>\n'
                                  f'    <string>{app_name}</string>\n'
                                  f'    <key>CFBundlePackageType</key>\n'
                                  f'    <string>APPL</string>\n'
                                  f'    <key>CFBundleShortVersionString</key>\n'
                                  f'    <string>1.0</string>\n'
                                  f'</dict>\n'
                                  f'</plist>')
            
            if dist_dir != output_dir and dist_dir.exists():
                for item in dist_dir.iterdir():
                    dest = macos_dir / item.name
                    if item.is_dir():
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)
            
            if fmt == "dmg":
                dmg_path = output_dir / f"{safe_name}.dmg"
                cmd = ["hdiutil", "create", "-volname", app_name, "-srcfolder", str(app_bundle), "-ov", "-format", "UDZO", str(dmg_path)]
            else:
                self.artifacts.append(fmt)
                return {"format": fmt, "status": "ok", "tool": "none"}

        elif self.config.host_platform == "Windows" or fmt in ("nsis", "exe"):
            nsi_path = output_dir / "installer.nsi"
            nsi_path.write_text(f'OutFile "{safe_name}_installer.exe"\n'
                                f'InstallDir "$PROGRAMFILES\\{app_name}"\n'
                                f'Section\n'
                                f'  SetOutPath $INSTDIR\n'
                                f'  File /r "{dist_dir.name}\\*"\n'
                                f'  CreateShortcut "$SMPROGRAMS\\{app_name}.lnk" "$INSTDIR\\{safe_name}.exe"\n'
                                f'SectionEnd\n')
            cmd = ["makensis", str(nsi_path)]

        elif self.config.host_platform == "Linux" or fmt in ("appimage", "deb"):
            app_dir = output_dir / "AppDir"
            app_dir.mkdir(exist_ok=True)
            
            app_run = app_dir / "AppRun"
            app_run.write_text(f'#!/bin/sh\ncd "$(dirname "$0")"\nexec ./{safe_name}')
            app_run.chmod(0o755)
            
            desktop_file = app_dir / f"{safe_name}.desktop"
            desktop_file.write_text(f'[Desktop Entry]\n'
                                    f'Name={app_name}\n'
                                    f'Exec={safe_name}\n'
                                    f'Icon={safe_name}\n'
                                    f'Type=Application\n'
                                    f'Categories=Utility;\n')
            
            if dist_dir != output_dir and dist_dir.exists():
                for item in dist_dir.iterdir():
                    dest = app_dir / item.name
                    if item.is_dir():
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)
                    
            if fmt == "appimage":
                cmd = ["appimagetool", str(app_dir)]
            elif fmt == "deb":
                cmd = ["dpkg-deb", "--build", str(app_dir)]

        else:
            return {"format": fmt, "status": "skipped", "reason": f"unsupported format {fmt}"}

        if cmd:
            tool = cmd[0]
            if not shutil.which(tool):
                raise RuntimeError(f"Required packaging tool '{tool}' for format '{fmt}' is not installed.")

            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )

        self.artifacts.append(fmt)
        return {"format": fmt, "status": "ok", "tool": cmd[0] if cmd else "none"}

    def get_summary(self) -> dict[str, Any]:
        """Return a summary of the build pipeline results."""
        return {
            "status": "ok",
            "target": self.config.target,
            "builder": self.config.builder,
            "output_dir": str(self.config.output_dir),
            "artifacts": list(self.artifacts),
            "app_name": self.config.app_name,
            "safe_name": self.config.safe_app_name,
            "host_platform": self.config.host_platform,
        }
