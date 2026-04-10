#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import os from "node:os";
import path from "node:path";
import { existsSync } from "node:fs";

function pythonLaunchers() {
  const launchers = [];
  const seen = new Set();

  function addLauncher(command, args = []) {
    const key = `${command}::${args.join(" ")}`;
    if (!seen.has(key)) {
      seen.add(key);
      launchers.push({ command, args });
    }
  }

  const explicit = process.env.FORGE_PYTHON;
  if (explicit) {
    addLauncher(explicit, []);
  }

  const virtualEnv = process.env.VIRTUAL_ENV;
  if (virtualEnv) {
    if (process.platform === "win32") {
      addLauncher(path.join(virtualEnv, "Scripts", "python.exe"), []);
    } else {
      addLauncher(path.join(virtualEnv, "bin", "python"), []);
    }
  }

  const localVenv = process.platform === "win32"
    ? path.join(process.cwd(), ".venv", "Scripts", "python.exe")
    : path.join(process.cwd(), ".venv", "bin", "python");
  addLauncher(localVenv, []);

  if (process.platform === "win32") {
    addLauncher("py", ["-3"]);
    addLauncher("python", []);
    return launchers;
  }

  addLauncher("python3", []);
  addLauncher("python", []);
  return launchers;
}

function run(command, args) {
  const child = spawnSync(command, args, { stdio: "inherit" });
  return child.status ?? 1;
}

function ensurePythonForge() {
  for (const launcher of pythonLaunchers()) {
    const probe = spawnSync(launcher.command, [...launcher.args, "-m", "forge_cli.main", "--help"], {
      stdio: "ignore",
    });
    if (probe.status === 0) {
      return launcher;
    }
  }

  if (process.env.FORGE_SKIP_AUTO_INSTALL === "1") {
    return null;
  }

  function findUvBinary() {
    const candidates = [
      process.env.FORGE_UV,
      "uv",
      path.join(os.homedir(), ".local", "bin", "uv"),
      path.join(os.homedir(), ".cargo", "bin", "uv"),
      path.join(os.homedir(), "AppData", "Local", "uv", "bin", "uv.exe"),
    ].filter(Boolean);

    for (const candidate of candidates) {
      const probe = spawnSync(candidate, ["--version"], { stdio: "ignore" });
      if (probe.status === 0) {
        return candidate;
      }
    }
    return null;
  }

  function ensureUv() {
    const existing = findUvBinary();
    if (existing) {
      return existing;
    }

    const installer = process.platform === "win32"
      ? spawnSync("powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "irm https://astral.sh/uv/install.ps1 | iex"], { stdio: "inherit" })
      : spawnSync("sh", ["-c", "set -e; if command -v curl >/dev/null 2>&1; then curl -LsSf https://astral.sh/uv/install.sh | sh; elif command -v wget >/dev/null 2>&1; then wget -qO- https://astral.sh/uv/install.sh | sh; else exit 1; fi"], { stdio: "inherit" });

    if (installer.status !== 0) {
      return null;
    }

    return findUvBinary();
  }

  const uv = ensureUv();
  if (!uv) {
    return null;
  }

  const uvEnv = {
    ...process.env,
    UV_LINK_MODE: process.env.UV_LINK_MODE || "copy",
  };

  const runtimeRoot = path.join(os.homedir(), ".cache", "forgedesk", "python-runtime");
  const runtimePython = process.platform === "win32"
    ? path.join(runtimeRoot, "Scripts", "python.exe")
    : path.join(runtimeRoot, "bin", "python");

  const createVenv = spawnSync(uv, ["venv", runtimeRoot, "--python", "3.14", "--allow-existing"], {
    stdio: "inherit",
    env: uvEnv,
  });
  if (createVenv.status !== 0) {
    return null;
  }

  const installAttempts = [
    ["pip", "install", "--python", runtimePython, "--index-url", "https://pypi.org/simple", "forge-framework"],
    ["pip", "install", "--python", runtimePython, "forge-framework"],
    [
      "pip",
      "install",
      "--python",
      runtimePython,
      "git+https://github.com/swadhinbiswas/Forge.git",
    ],
  ];

  const scriptDir = path.dirname(process.argv[1] || "");
  const repoCandidate = path.resolve(scriptDir, "..", "..", "..");
  if (existsSync(path.join(repoCandidate, "pyproject.toml")) && existsSync(path.join(repoCandidate, "forge_cli"))) {
    installAttempts.push(["pip", "install", "--python", runtimePython, "-e", repoCandidate]);
  }

  let installed = false;
  for (const args of installAttempts) {
    const attempt = spawnSync(uv, args, { stdio: "inherit", env: uvEnv });
    if (attempt.status !== 0) {
      continue;
    }
    const probe = spawnSync(runtimePython, ["-m", "forge_cli.main", "--help"], { stdio: "ignore" });
    if (probe.status === 0) {
      installed = true;
      break;
    }
  }

  if (!installed) {
    return null;
  }

  const probeRuntime = spawnSync(runtimePython, ["-m", "forge_cli.main", "--help"], { stdio: "ignore" });
  if (probeRuntime.status === 0) {
    return { command: runtimePython, args: [] };
  }

  return null;
}

const argv = process.argv.slice(2);

const launcher = ensurePythonForge();
if (!launcher) {
  console.error("\x1b[1;31m✖\x1b[0m \x1b[1mForge CLI is unavailable.\x1b[0m\n\x1b[33mInstall Python 3.14+ and uv, then run again.\x1b[0m");
  process.exit(1);
}

process.exit(run(launcher.command, [...launcher.args, "-m", "forge_cli.main", ...argv]));
