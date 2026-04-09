import subprocess
import os
from pathlib import Path
import pytest

# Constants
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
CLI_JS_PATH = PROJECT_ROOT / "packages" / "cli" / "bin" / "forge.js"
CREATE_APP_JS_PATH = PROJECT_ROOT / "packages" / "create-forge-app" / "bin" / "create-forge-app.js"

@pytest.fixture
def run_env():
    # Pass along existing environment variables to ensure uv run testing gets python paths
    env = os.environ.copy()
    # Explicitly instruct the wrapper not to attempt auto-installing the framework during dev testing
    env["FORGE_SKIP_AUTO_INSTALL"] = "1"
    return env

def test_npm_cli_wrapper(run_env):
    """Ensure the JS proxy CLI correctly boots the Python backend forge_cli.main."""
    assert CLI_JS_PATH.exists(), "CLI wrapper script does not exist!"
    
    # Run the equivalent of `npx @forge/cli --help`
    result = subprocess.run(
        ["node", str(CLI_JS_PATH), "--help"],
        cwd=PROJECT_ROOT,
        env=run_env,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"CLI wrapper failed: {result.stderr}"
    assert "Usage: forge" in result.stdout or "Usage:" in result.stdout
    assert "build" in result.stdout
    assert "dev" in result.stdout

def test_npm_create_app_wrapper(run_env):
    """Ensure the JS proxy create-forge-app correctly boots the Python scaffolding logic."""
    assert CREATE_APP_JS_PATH.exists(), "create-forge-app wrapper script does not exist!"
    
    # Run the equivalent of `npx create-forge-app --help`
    result = subprocess.run(
        ["node", str(CREATE_APP_JS_PATH), "--help"],
        cwd=PROJECT_ROOT,
        env=run_env,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"create-forge-app wrapper failed: {result.stderr}"
    assert "Usage:" in result.stdout
