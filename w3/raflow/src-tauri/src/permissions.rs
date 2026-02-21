use serde::Serialize;

use crate::input::DEFAULT_INJECTION_THRESHOLD;
use crate::input::injector::InputInjector;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PermissionReport {
    pub microphone: PermissionState,
    pub accessibility: PermissionState,
    pub guidance: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum PermissionState {
    Granted,
    Denied,
    Unknown,
}

pub fn check_permissions() -> PermissionReport {
    let microphone = check_microphone_permission();
    let accessibility = check_accessibility_permission();

    let mut guidance = Vec::new();
    if matches!(microphone, PermissionState::Denied) {
        guidance
            .push("Microphone is unavailable. Connect or enable a recording device.".to_string());
    }
    if matches!(accessibility, PermissionState::Denied) {
        guidance.push(
            "Accessibility/input simulation appears blocked. Grant automation/accessibility permission."
                .to_string(),
        );
    }
    if guidance.is_empty() {
        guidance.push("Permissions look healthy.".to_string());
    }

    PermissionReport {
        microphone,
        accessibility,
        guidance,
    }
}

fn check_microphone_permission() -> PermissionState {
    #[cfg(desktop)]
    {
        use cpal::traits::HostTrait;
        let host = cpal::default_host();
        match host.input_devices() {
            Ok(_) => {
                if host.default_input_device().is_some() {
                    PermissionState::Granted
                } else {
                    PermissionState::Denied
                }
            }
            Err(_) => PermissionState::Unknown,
        }
    }

    #[cfg(not(desktop))]
    {
        PermissionState::Unknown
    }
}

fn check_accessibility_permission() -> PermissionState {
    #[cfg(desktop)]
    {
        match InputInjector::new(DEFAULT_INJECTION_THRESHOLD) {
            Ok(_) => PermissionState::Granted,
            Err(err) => {
                let message = err.to_string().to_lowercase();
                if message.contains("unsupported") || message.contains("not implemented") {
                    PermissionState::Unknown
                } else {
                    PermissionState::Denied
                }
            }
        }
    }

    #[cfg(not(desktop))]
    {
        PermissionState::Unknown
    }
}
