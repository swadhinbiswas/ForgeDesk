# Production Branch Rules & Engineering Strategy

To maintain enterprise-grade stability for ForgeDesk v3.0.0 and beyond, the following GitHub branch protections and engineering practices **MUST** be enforced strictly.

## 1. Branch Protection (`main`)

### Rules
- **Require Pull Request reviews before merging**: 
  - Minimum number of approvals: **1** (or **2** for core backend modifications).
  - Dismiss stale pull request approvals when new commits are pushed: **Enabled**.
  - Require review from Code Owners: **Enabled** (Define in `.github/CODEOWNERS`).
- **Require status checks to pass before merging**:
  - `Rust (clippy & cargo fmt)`
  - `Rust Tests (cargo test)`
  - `Python Linting (ruff & mypy)`
  - `Python Tests (pytest - Linux, macOS, Windows)`
  - `Node Tests (packages/* suite)`
  - Require branches to be up to date before merging: **Enabled**.
- **Do not allow bypassing the above settings**: Enforce strictly on administrators.
- **Restrict who can push to matching branches**: Nobody. All code must go through a PR and be squash-merged.

## 2. Release Branches (`release/vX.Y`)
- Created from `main` roughly 1 week before a major/minor launch.
- Accepts non-breaking bug fixes.
- Hard freeze on new features.

## 3. Commit Message Standards
- We strictly enforce **Conventional Commits**:
  - `feat: ✨ interactive CLI scaffolding via questionary`
  - `fix: 🐛 scope.py URL resolver fails when no allow list exists`
  - `docs: 📝 updated README.md to reflect v3.0 architecture`
  - `chore: 🔧 bumping Vite dependencies`

## 4. Submitting a PR
1. Always base branches on `main`. Prefix with `feat/`, `fix/`, `docs/`, or `chore/`.
2. Do not bump versions in your PR. Version bumping is done globally via a release script.
3. Every bug fix must include a regression test ensuring `pytest` captures the fault.
4. Pass `forge doctor` locally.

## 5. Security & Hotfixing Protocols
1. Security vulnerabilities must NEVER be submitted as public PRs. Reach out via email defined in `SECURITY.md`.
2. A hotfix directly targets `main` and is cherry-picked back to active support branches (`v2.X`, `v3.X`).
