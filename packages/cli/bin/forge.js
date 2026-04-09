#!/usr/bin/env node
import { spawnSync } from "node:child_process";

function pythonLaunchers() {
  if (process.platform === "win32") {
    return [
      { command: "py", args: ["-3"] },
      { command: "python", args: [] },
    ];
  }
  return [
    { command: process.env.FORGE_PYTHON || "python3", args: [] },
    { command: "python", args: [] },
  ];
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

  for (const launcher of pythonLaunchers()) {
    const install = spawnSync(
      launcher.command,
      [...launcher.args, "-m", "pip", "install", "forge-framework"],
      { stdio: "inherit" },
    );
    if (install.status === 0) {
      return launcher;
    }
  }
  return null;
}

const argv = process.argv.slice(2);

const launcher = ensurePythonForge();
if (!launcher) {
  console.error("\x1b[1;31m✖\x1b[0m \x1b[1mForge CLI is unavailable.\x1b[0m\n\x1b[33mInstall Python 3.14+ and run:\x1b[0m \x1b[36mpython -m pip install forge-framework\x1b[0m");
  process.exit(1);
}

process.exit(run(launcher.command, [...launcher.args, "-m", "forge_cli.main", ...argv]));
