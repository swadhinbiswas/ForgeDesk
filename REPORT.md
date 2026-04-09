# Code Signing and Notarization Analysis: `forge_cli/main.py`

## Overview
The current code signing and notarization implementation in `forge_cli/main.py` is naive and fundamentally incomplete for both macOS and Windows platforms. It uses overly simplistic commands that will fail modern OS security checks (like Gatekeeper on macOS or SmartScreen on Windows). 

**Question: Can we publish this?**
**Answer: No.** If published as-is, users will encounter severe warnings or outright blocks. macOS will refuse to run the app due to Gatekeeper blocking un-notarized or improperly signed bundles, and Windows anti-virus/SmartScreen will flag the interior unsigned executables as suspicious. 

---

## macOS Deficiencies (Apple Silicon / Gatekeeper limits)

The current `codesign` block in `_run_default_signing_adapter` is implemented as:
```python
[tool, "--force", "--deep", *timestamp_arg, "--sign", config.signing.identity, target_path]
```

This approach is broken for Several reasons:

1. **Missing Hardened Runtime (`--options runtime`)**: Apple’s Notary service strictly requires the hardened runtime to be enabled for apps targeting macOS 10.14 and later. Without it, the notarization process will reject the submission.
2. **Missing Entitlements**: The command lacks the `--entitlements` flag. Without specifying entitlements (like `com.apple.security.cs.allow-jit` for JS engines or `com.apple.security.network.client`), the app may crash immediately upon launch because the hardened runtime will block essential framework operations.
3. **Flawed `--deep` Signing for `.app` Bundles**: Using `--deep` on a complex `.app` bundle is heavily discouraged by Apple. It blindly signs all nested files, often breaking pre-signed frameworks (like embedded Python or Node libraries) and failing to properly establish the nested bundle dependency chain. A proper implementation must sign inner frameworks, dylibs, and helpers individually (inside-out) before signing the outer `.app` container.

### Notarization Failures
The notarization routine in `_run_notarization` executes:
```python
["xcrun", "notarytool", "submit", submit_target, "--wait"]
```

1. **Missing Authentication credentials**: `notarytool` requires authentication credentials (either `--keychain-profile`, or an explicit `--apple-id`, `--team-id`, and `--password`/key). The current command will fail immediately due to unbound auth requirements.
2. **Missing Stapling**: Even if notarization succeeded, there is no subsequent `xcrun stapler staple <path>` command. Without stapling the notarization ticket to the app, offline Gatekeeper checks will fail, giving users a scary warning if they lack an active internet connection on first run.

## Windows Deficiencies (Authenticode / SmartScreen)

The Windows `signtool` block currently iterates over `target_paths` (the final output artifacts):
```python
sign_command = [tool, "sign", "/fd", "SHA256", "/n", config.signing.identity]
...
sign_command.append(target_path)
```

1. **Only Signing the Outer Installer**: The script only signs the final packaged artifact (e.g., the NSIS installer or target package). It fails to sign the pre-packaged, interior `.exe` application files, companion `.dll`s, and Python native libraries. 
2. **Consequences:** When the installer extracts the application to the user's `AppData` or `Program Files`, the executables themselves will be unsigned. SmartScreen and enterprise AV solutions will frequently quarantine or silently block unsigned internal binaries, even if the installer itself was signed. A proper pipeline should extract/compile the binaries, run `signtool` on the interior executables, and *then* package them into the installer which gets signed again at the end.
