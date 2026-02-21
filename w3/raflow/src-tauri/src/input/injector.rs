use std::time::Duration;

use enigo::{
    Direction::{Click, Press, Release},
    Enigo, Key, Keyboard, Settings,
};
use tauri::{AppHandle, Runtime};
use tauri_plugin_clipboard_manager::ClipboardExt;
use tracing::warn;

use crate::input::{InputError, validate_transcript};

pub struct InputInjector {
    enigo: Enigo,
    threshold: usize,
}

impl InputInjector {
    pub fn new(threshold: usize) -> Result<Self, InputError> {
        let enigo = Enigo::new(&Settings::default())
            .map_err(|err| InputError::Initialization(err.to_string()))?;

        Ok(Self { enigo, threshold })
    }

    pub fn inject_text<R: Runtime>(
        &mut self,
        text: &str,
        app_handle: &AppHandle<R>,
    ) -> Result<(), InputError> {
        let cleaned = validate_transcript(text)?;
        if cleaned.trim().is_empty() {
            return Ok(());
        }

        let should_try_keyboard = cleaned.is_ascii() && cleaned.chars().count() < self.threshold;
        if should_try_keyboard {
            if let Err(err) = self.inject_via_keyboard(&cleaned) {
                warn!("keyboard injection failed, falling back to clipboard: {err}");
                self.inject_via_clipboard(&cleaned, app_handle)?;
            }
        } else {
            self.inject_via_clipboard(&cleaned, app_handle)?;
        }

        // Keep the latest transcript in clipboard so users can paste manually
        // when there is no editable cursor in the active window.
        if let Err(err) = app_handle.clipboard().write_text(&cleaned) {
            warn!("failed to mirror transcript into clipboard: {err}");
        }

        Ok(())
    }

    fn inject_via_keyboard(&mut self, text: &str) -> Result<(), InputError> {
        for ch in text.chars() {
            self.enigo
                .key(Key::Unicode(ch), Click)
                .map_err(|err| InputError::Keyboard(err.to_string()))?;
            std::thread::sleep(Duration::from_millis(5));
        }

        Ok(())
    }

    fn inject_via_clipboard<R: Runtime>(
        &mut self,
        text: &str,
        app_handle: &AppHandle<R>,
    ) -> Result<(), InputError> {
        app_handle
            .clipboard()
            .write_text(text)
            .map_err(|err| InputError::Clipboard(err.to_string()))?;

        #[cfg(target_os = "macos")]
        {
            self.enigo
                .key(Key::Meta, Press)
                .map_err(|err| InputError::Keyboard(err.to_string()))?;
            self.enigo
                .key(Key::Unicode('v'), Click)
                .map_err(|err| InputError::Keyboard(err.to_string()))?;
            self.enigo
                .key(Key::Meta, Release)
                .map_err(|err| InputError::Keyboard(err.to_string()))?;
        }

        #[cfg(not(target_os = "macos"))]
        {
            self.enigo
                .key(Key::Control, Press)
                .map_err(|err| InputError::Keyboard(err.to_string()))?;
            self.enigo
                .key(Key::Unicode('v'), Click)
                .map_err(|err| InputError::Keyboard(err.to_string()))?;
            self.enigo
                .key(Key::Control, Release)
                .map_err(|err| InputError::Keyboard(err.to_string()))?;
        }

        std::thread::sleep(Duration::from_millis(100));

        Ok(())
    }
}
