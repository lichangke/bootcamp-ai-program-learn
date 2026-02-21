use std::time::Duration;

use enigo::{Direction::Click, Enigo, Key, Keyboard, Settings};
use tauri::{AppHandle, Runtime};
use tauri_plugin_clipboard_manager::ClipboardExt;
use tracing::warn;

use crate::input::{InputError, validate_transcript};

pub struct InputInjector {
    enigo: Enigo,
}

impl InputInjector {
    pub fn new() -> Result<Self, InputError> {
        let enigo = Enigo::new(&Settings::default())
            .map_err(|err| InputError::Initialization(err.to_string()))?;

        Ok(Self { enigo })
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

        self.inject_via_keyboard(&cleaned)?;

        // Keep the latest transcript in clipboard so users can paste manually
        // when there is no editable cursor in the active window.
        if let Err(err) = app_handle.clipboard().write_text(&cleaned) {
            warn!("failed to mirror transcript into clipboard: {err}");
        }

        Ok(())
    }

    pub fn write_clipboard_only<R: Runtime>(
        text: &str,
        app_handle: &AppHandle<R>,
    ) -> Result<(), InputError> {
        let cleaned = validate_transcript(text)?;
        if cleaned.trim().is_empty() {
            return Ok(());
        }

        app_handle
            .clipboard()
            .write_text(&cleaned)
            .map_err(|err| InputError::Clipboard(err.to_string()))
    }

    pub fn rewrite_tail<R: Runtime>(
        &mut self,
        backspace_count: usize,
        insert_text: &str,
        app_handle: &AppHandle<R>,
    ) -> Result<(), InputError> {
        for _ in 0..backspace_count {
            self.enigo
                .key(Key::Backspace, Click)
                .map_err(|err| InputError::Keyboard(err.to_string()))?;
            std::thread::sleep(Duration::from_millis(4));
        }

        if insert_text.trim().is_empty() {
            return Ok(());
        }

        self.inject_text(insert_text, app_handle)
    }

    fn inject_via_keyboard(&mut self, text: &str) -> Result<(), InputError> {
        for ch in text.chars() {
            let unit = ch.to_string();
            self.enigo
                .text(&unit)
                .map_err(|err| InputError::Keyboard(err.to_string()))?;
            std::thread::sleep(Duration::from_millis(5));
        }

        Ok(())
    }
}
