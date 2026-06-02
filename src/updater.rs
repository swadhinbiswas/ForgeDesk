use anyhow::{Context, Result};
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use reqwest::blocking::Client;
use reqwest::redirect::Policy;
use std::env;
use std::fs;
use std::io::{Cursor, Read};
use std::process::Command;

/// Build an HTTPS-only reqwest client with redirects following only same-scheme HTTPS hops.
fn build_client() -> Result<Client> {
    let policy = Policy::custom(|attempt| {
        if attempt.url().scheme() == "https" && attempt.previous().len() < 5 {
            attempt.follow()
        } else {
            attempt.stop()
        }
    });
    Client::builder()
        .user_agent("forge-framework-updater")
        .https_only(true)
        .redirect(policy)
        .build()
        .context("Failed to build HTTPS client")
}

/// Validate that the URL is HTTPS (no http://, ftp://, file://, etc).
fn require_https(url: &str) -> Result<()> {
    if !url.starts_with("https://") {
        anyhow::bail!(
            "Updater rejected non-HTTPS URL: {}. Only https:// is permitted.",
            url
        );
    }
    Ok(())
}

/// Applies a full update by downloading the payload, verifying the signature,
/// replacing the current executable, and restarting.
///
/// Signature verification is mandatory; both `signature_hex` and `pub_key_hex`
/// must be provided. The URL must use https://.
pub fn apply_update(
    url: String,
    signature_hex: Option<String>,
    pub_key_hex: Option<String>,
) -> Result<()> {
    require_https(&url)?;

    let sig_hex = signature_hex
        .ok_or_else(|| anyhow::anyhow!("Updater requires signature_hex; refusing unsigned update"))?;
    let pk_hex = pub_key_hex
        .ok_or_else(|| anyhow::anyhow!("Updater requires pub_key_hex; refusing unsigned update"))?;

    // 1. Download payload
    let client = build_client()?;
    let mut response = client.get(&url).send()?.error_for_status()?;
    let mut payload = Vec::new();
    response.read_to_end(&mut payload)?;

    // 2. Verify signature (mandatory)
    verify_signature(&payload, &sig_hex, &pk_hex)?;

    // 3. Save payload to temporary executable file
    let temp_file = tempfile::NamedTempFile::new()?;
    let temp_path = temp_file.path().to_path_buf();
    fs::write(&temp_path, &payload)?;

    // Set executable permissions (Unix)
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = fs::metadata(&temp_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&temp_path, perms)?;
    }

    // 4. Drop the NamedTempFile guard so the file isn't unlinked while
    //    self_replace is operating on it (Windows-safe).
    drop(temp_file);

    // 5. Replace the current executable
    self_replace::self_replace(&temp_path)?;

    // 6. Best-effort cleanup of the staged file
    let _ = fs::remove_file(&temp_path);

    // 7. Restart the application (this terminates the current process)
    restart_application()
}

/// Applies a delta update by downloading the binary diff patch, verifying signature,
/// applying the patch to the current executable, and restarting.
///
/// The patch payload layout is:
///   [0..8]   u64 little-endian — size of the new (patched) file in bytes
///   [8..]    raw bsdiff patch data
///
/// Signature verification is mandatory; both `signature_hex` and `pub_key_hex`
/// must be provided. The URL must use https://.
pub fn apply_delta_update(
    patch_url: String,
    expected_old_hash: Option<String>,
    expected_new_hash: Option<String>,
    signature_hex: Option<String>,
    pub_key_hex: Option<String>,
) -> Result<()> {
    require_https(&patch_url)?;

    let sig_hex = signature_hex.ok_or_else(|| {
        anyhow::anyhow!("Delta updater requires signature_hex; refusing unsigned update")
    })?;
    let pk_hex = pub_key_hex.ok_or_else(|| {
        anyhow::anyhow!("Delta updater requires pub_key_hex; refusing unsigned update")
    })?;

    // 1. Download the delta patch
    let client = build_client()?;
    let mut response = client.get(&patch_url).send()?.error_for_status()?;
    let mut patch_data = Vec::new();
    response.read_to_end(&mut patch_data)?;

    // 2. Verify signature (mandatory)
    verify_signature(&patch_data, &sig_hex, &pk_hex)?;

    // 3. Parse the new-file size header
    if patch_data.len() < 8 {
        anyhow::bail!("Delta patch is too short to contain new-size header");
    }
    let mut size_bytes = [0u8; 8];
    size_bytes.copy_from_slice(&patch_data[..8]);
    let new_size = u64::from_le_bytes(size_bytes) as usize;

    // Reject implausibly large allocations (1 GiB hard cap).
    const MAX_NEW_SIZE: usize = 1024 * 1024 * 1024;
    if new_size == 0 || new_size > MAX_NEW_SIZE {
        anyhow::bail!(
            "Delta patch declared invalid new size: {} bytes (max {})",
            new_size,
            MAX_NEW_SIZE
        );
    }

    // 4. Read the current executable
    let current_exe = env::current_exe()?;
    let old_data = fs::read(&current_exe)?;

    // 5. Verify old hash if provided
    if let Some(ref hash) = expected_old_hash {
        let actual_hash = sha256_hex(&old_data);
        if &actual_hash != hash {
            anyhow::bail!(
                "Current executable hash mismatch. Expected: {}, Got: {}",
                hash,
                actual_hash
            );
        }
    }

    // 6. Apply the bsdiff patch with the correctly-sized buffer
    let mut patch_reader = Cursor::new(&patch_data[8..]);
    let mut new_data = vec![0u8; new_size];
    bsdiff::patch::patch(&old_data, &mut patch_reader, &mut new_data)
        .context("Failed to apply binary patch. The patch may be for a different version.")?;

    // 7. Verify new hash if provided
    if let Some(ref hash) = expected_new_hash {
        let actual_hash = sha256_hex(&new_data);
        if &actual_hash != hash {
            anyhow::bail!(
                "Patched executable hash mismatch. Expected: {}, Got: {}",
                hash,
                actual_hash
            );
        }
    }

    // 8. Save patched executable to temp file
    let temp_file = tempfile::NamedTempFile::new()?;
    let temp_path = temp_file.path().to_path_buf();
    fs::write(&temp_path, &new_data)?;

    // Set executable permissions (Unix)
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = fs::metadata(&temp_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&temp_path, perms)?;
    }

    // 9. Drop the NamedTempFile guard before self_replace (Windows-safe).
    drop(temp_file);

    // 10. Securely replace the current executable
    self_replace::self_replace(&temp_path)?;
    let _ = fs::remove_file(&temp_path);

    // 11. Restart the application (this terminates the current process)
    restart_application()
}

/// Verify an Ed25519 signature against the payload.
fn verify_signature(payload: &[u8], sig_hex: &str, pk_hex: &str) -> Result<()> {
    let sig_bytes = hex::decode(sig_hex).context("Invalid signature hex")?;
    let pk_bytes = hex::decode(pk_hex).context("Invalid public key hex")?;

    let public_key =
        VerifyingKey::try_from(pk_bytes.as_slice()).context("Invalid public key format")?;
    let signature = Signature::from_slice(&sig_bytes).context("Invalid signature format")?;

    public_key
        .verify(payload, &signature)
        .context("Signature verification failed")?;

    Ok(())
}

/// Compute SHA-256 hash of data as hex string.
fn sha256_hex(data: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(data);
    hex::encode(hasher.finalize())
}

/// Spawn the freshly-replaced executable, then terminate the current process.
///
/// Returns `Ok(())` only on the (unreachable) path where exit fails; on
/// success the calling process never returns from this function.
fn restart_application() -> Result<()> {
    let current_exe = env::current_exe()?;
    let args: Vec<String> = env::args().collect();
    Command::new(current_exe).args(&args[1..]).spawn()?;
    // Give the spawned process a moment to detach before we exit.
    std::thread::sleep(std::time::Duration::from_millis(150));
    std::process::exit(0);
}
