const SERVICE_NAME: &str = "com.raflow.app";
const API_KEY_ACCOUNT: &str = "elevenlabs_api_key";

pub fn read_api_key() -> Result<Option<String>, String> {
    let entry =
        keyring::Entry::new(SERVICE_NAME, API_KEY_ACCOUNT).map_err(|err| err.to_string())?;

    match entry.get_password() {
        Ok(value) => Ok(Some(value)),
        Err(err) => {
            if is_not_found_error(&err.to_string()) {
                Ok(None)
            } else {
                Err(format!("failed to read API key from secure storage: {err}"))
            }
        }
    }
}

pub fn write_api_key(api_key: &str) -> Result<(), String> {
    let entry =
        keyring::Entry::new(SERVICE_NAME, API_KEY_ACCOUNT).map_err(|err| err.to_string())?;
    let trimmed = api_key.trim();

    if trimmed.is_empty() {
        return match entry.delete_credential() {
            Ok(()) => Ok(()),
            Err(err) => {
                if is_not_found_error(&err.to_string()) {
                    Ok(())
                } else {
                    Err(format!("failed to clear API key in secure storage: {err}"))
                }
            }
        };
    }

    entry
        .set_password(trimmed)
        .map_err(|err| format!("failed to save API key in secure storage: {err}"))
}

fn is_not_found_error(message: &str) -> bool {
    let normalized = message.to_lowercase();
    normalized.contains("no entry")
        || normalized.contains("not found")
        || normalized.contains("no matching entry")
}
