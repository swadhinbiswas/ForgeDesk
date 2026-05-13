from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "require_release_branch.py"
_spec = spec_from_file_location("require_release_branch", SCRIPT_PATH)
assert _spec and _spec.loader
_module = module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)
is_allowed_release_branch = _module.is_allowed_release_branch
check_branch = _module.check_branch


def test_release_branch_patterns() -> None:
    assert is_allowed_release_branch("main") is True
    assert is_allowed_release_branch("master") is True
    assert is_allowed_release_branch("release/2026.03") is True
    assert is_allowed_release_branch("release-hotfix") is True
    assert is_allowed_release_branch("feature/new-ui") is False
    assert is_allowed_release_branch("bugfix") is False


def test_check_branch_prefers_explicit_branch() -> None:
    result = check_branch("release/2.0")
    assert result.branch == "release/2.0"
    assert result.allowed is True
