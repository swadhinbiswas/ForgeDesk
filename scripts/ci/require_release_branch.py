from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass

ALLOWED_PATTERNS = (
    re.compile(r"^main$"),
    re.compile(r"^master$"),
    re.compile(r"^release/[A-Za-z0-9._-]+$"),
    re.compile(r"^release-[A-Za-z0-9._-]+$"),
)


@dataclass(frozen=True)
class BranchCheck:
    branch: str
    allowed: bool


def is_allowed_release_branch(branch: str) -> bool:
    return any(pattern.match(branch) for pattern in ALLOWED_PATTERNS)


def resolve_branch(explicit_branch: str | None = None) -> str:
    if explicit_branch:
        return explicit_branch

    for env_name in ("GITHUB_REF_NAME", "GITHUB_HEAD_REF", "BRANCH_NAME"):
        value = os.environ.get(env_name)
        if value:
            return value

    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/heads/"):
        return ref.removeprefix("refs/heads/")
    if ref.startswith("refs/tags/"):
        return ref.removeprefix("refs/tags/")
    return ref or "unknown"


def check_branch(explicit_branch: str | None = None) -> BranchCheck:
    branch = resolve_branch(explicit_branch)
    return BranchCheck(branch=branch, allowed=is_allowed_release_branch(branch))


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate release-heavy CI jobs to release branches")
    parser.add_argument("--branch", help="Branch name to validate instead of the CI environment")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    args = parser.parse_args()

    result = check_branch(args.branch)
    if args.json:
        pass
    elif result.allowed:
        pass
    else:
        pass

    raise SystemExit(0 if result.allowed else 1)


if __name__ == "__main__":
    main()
