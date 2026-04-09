use anyhow::{Context, Result};
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use reqwest::blocking::Client;
use std::env;
use std::fs;
use std::io::Read;
use std::os::unix::process::CommandExt;
use std::path::PathBuf;
use std::process::Command;

/// Applies an update by downloading the payload, verifying signature (if provided),
/// replacing the current executable, and restarting.
pub fn apply_update(
    url: String,
    signature_hex: Option<String>,
    pub_key_hex: Option<String>,
) -> Result<()> {
    // 1. Download payload to a temp file
    let client = Client::builder()
        .user_agent("forge-framework-updater")
        .build()?;

    let mut response = client.get(&url).send()?.error_for_status()?;
    let mut payload = Vec::new();
    response.read_to_end(&mut payload)?;

    // 2. Verify signature if provided
    if let (Some(sig_hex), Some(pk_hex)) = (signature_hex, pub_key_hex) {
        let sig_bytes = hex::decode(&sig_hex).context("Invalid signature hex")?;
        let pk_bytes = hex::decode(&pk_hex).context("Invalid public key hex")?;

        let public_key =
            VerifyingKey::try_from(pk_bytes.as_slice()).context("Invalid public key format")?;
        let signature = Signature::from_slice(&sig_bytes).context("Invalid signature format")?;

        public_key
            .verify(&payload, &signature)
            .context("Signature verification failed")?;
    }

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

    // 4. Securely replace the current executable
    self_replace::self_replace(&temp_path)?;

    // Ensure cleanup of the temp file
    drop(temp_file);

    // 5. Restart the application
    let current_exe = env::current_exe()?;
    let args: Vec<String> = env::args().collect();

    Command::new(current_exe).args(&args[1..]).exec(); // Will not return if successful

    Ok(())
}
