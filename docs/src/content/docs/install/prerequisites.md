---
title: Prerequisites
description: System dependencies and tooling required before creating a ForgeDesk app.
---

## System Requirements

- Python 3.10+ (3.14+ recommended)
- Rust toolchain (required by native core and build pipeline)
- Node.js 18+ (optional, for React/Vue/Svelte/Astro frontends)

## Linux

Install common native dependencies used by WebKitGTK and desktop integrations:

```bash
sudo apt update
sudo apt install -y \
  libwebkit2gtk-4.1-dev \
  build-essential \
  libssl-dev \
  libayatana-appindicator3-dev \
  librsvg2-dev
```

## macOS

- Install Xcode from the App Store and open it once
- Install command line tools:

```bash
xcode-select --install
```

## Windows

- Install **Microsoft C++ Build Tools** (Desktop development with C++)
- Install or verify **WebView2 Runtime**
- Ensure Python and Rust are available in `PATH`

## Rust

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

Restart your terminal after installing Rust.

## Node.js (Optional)

Only required when using JS frameworks for frontend.

```bash
node -v
npm -v
```

## Continue

Move to [Create Project](./create-project/) once your environment is ready.
