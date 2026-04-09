# Forge Security Architecture

Forge implements a "Deny-by-Default" security boundary similar to Tauri, utilizing explicit capability scopes, strict IPC validation, and native OS codesigning standards to prevent remote execution and privilege escalation attacks.

## 1. Granular Security Scopes ($APPDATA / paths)
Paths accessed through modules like the `FileSystemAPI`, `ShellAPI`, or Custom Commands are bound to Strict JSON configuration schema boundaries (`home` / `appData`).
- Forge forbids `../` transversal by fully resolving target paths statically before acting. 
- Boolean configurations (`fs=true`) have been entirely discarded in favor of explicit `ScopeValidator`. If your function attempts to read `C:\Windows\System32\...` but your configuration only allowed `allow: ["$APPDATA/my-app/**"]`, the API automatically returns `Access Denied` via pure Python regex boundary bounds.

## 2. Strict IPC Payload Validation (Pydantic / Type Hints)
When a JavaScript endpoint invokes a Python function over the internal WebSockets/IPC Bridge, the message passes through a rigorous checking sequence:
- **Type Extraction**: The Python 3.14 function signature is extracted using `get_type_hints()`.
- **Dynamic Pydantic Generation**: The IPC broker creates an on-the-fly schema adapter verifying the JSON arguments map identically to the expected parameters structure.
- **Circuit Breaker Penalty**: Any misaligned `kwargs` or spoofed parameters cause validation to throw immediately, logging the malformed payload without ever evaluating the code. Repeated failures trip an internal Circuit breaker suspending the command.

## 3. Code Signing & Gatekeeper CI/CD pipelines
To survive modern Operating System restrictions, Forge embeds enterprise-level Code Signing workflows into `forge build`:
- **macOS (Apple Silicon & Gatekeeper)**: Automates `codesign` with injected `--options=runtime` (Hardened Runtime) and explicit `--entitlements`. It signs the nested app framework dependency chain "inside-out" before running an environment-key injected `xcrun notarytool submit` and `xcrun stapler` sequence to yield offline Gatekeeper approval.
- **Windows (SmartScreen / Defender)**: Unlike tools that purely sign an `NSIS` wrapper setup (triggering SmartScreen warnings on the inner application), Forge recurses through the inner build layout performing Authenticode bulk signing across the interior `.exe`, `.pyd`, and `.dll` binaries before wrapping them into a newly signed `.msi`.

## 4. Cryptographic Auto-Updater
The `src/updater.rs` module ensures updates downloaded mid-session are untampered with.
- Evaluates `Ed25519` cryptographic signatures locally against a statically embedded native public key using Dalek arrays.
- Drops the payload to a verified temp directory safely hot-swapping it over the locked executable using `self_replace`.
