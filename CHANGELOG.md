# Changelog

All notable changes to Forge Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-01

### Added

#### Core Framework
- `ForgeApp` class with `@app.command` decorator for exposing Python to JavaScript
- IPC Bridge for bidirectional Python-JavaScript communication
- Event system with `app.emit()` and `window.__forge__.on()`
- Window manager with full API for controlling window properties
- Configuration loader for `forge.toml` with validation

#### Built-in APIs
- **File System API** (`forge.fs`): read, write, exists, list, delete, mkdir
- **Dialog API** (`forge.dialog`): open_file, save_file, message dialogs
- **Clipboard API** (`forge.clipboard`): read, write clipboard content
- **System API** (`forge.app`): version, platform, info, exit
- **Tray API** (`forge.tray`): system tray icon and menu (optional)

#### CLI
- `forge create` - Scaffold new projects with templates (plain, react, vue, svelte)
- `forge dev` - Development mode with hot reload
- `forge build` - Build production binaries with PyInstaller
- `forge info` - Display system and project information

#### Security Features
- Command name validation (whitelist pattern)
- Path traversal prevention in file system API
- Input validation and sanitization
- Error message sanitization to prevent information leakage
- XSS prevention in event data
- Request size limits to prevent DoS

#### Templates
- Plain HTML/CSS/JS template
- React template with Vite
- Vue 3 template with Vite
- Svelte template with Vite

#### Examples
- **Hello Forge** - Minimal demo validating IPC functionality
- **Forge Notes** - Note-taking app demonstrating file system API

### Changed

- All API methods now have proper type hints
- Improved error messages with sanitization
- Enhanced documentation with security best practices

### Fixed

- Path traversal vulnerability in FileSystemAPI
- XSS vulnerability in event data emission
- Race condition in async command execution
- CLI template file copying for binary files
- Missing API command registrations

### Security

- Added SECURITY.md with vulnerability reporting process
- Added comprehensive security tests
- Implemented defense-in-depth for file operations
- Added null byte injection prevention
- Implemented symlink resolution and validation

## [Unreleased]

### Planned
- Plugin system for extending Forge
- Auto-update mechanism
- Enhanced tray icon support across platforms
- WebSocket support for real-time communication
- Database API with SQLite integration
- Notification API for system notifications
