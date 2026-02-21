pub mod audio;
mod commands;
mod error;
pub mod input;
mod metrics;
pub mod network;
mod permissions;
mod secure_storage;
mod state;

use std::error::Error;
use std::sync::Arc;
use std::sync::atomic::Ordering;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use error::AppError;
use input::{
    append_terminal_punctuation, injector::InputInjector, normalize_transcript_text,
    resolve_committed_punctuation_delta,
};
use network::{NetworkEvent, ScribeEvent};
use state::{AppState, CommittedTranscript, RuntimeState, TranscriptInjectionMode};
use tauri::Emitter;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{Manager, RunEvent, WindowEvent};
use tokio::sync::broadcast;
use tracing::{error, info, warn};

const MAIN_WINDOW_LABEL: &str = "main";
const MENU_ID_OPEN_SETTINGS: &str = "open_settings";
const MENU_ID_TOGGLE_OVERLAY: &str = "toggle_overlay";
const MENU_ID_QUIT: &str = "quit";
const EVENT_PARTIAL_TRANSCRIPT: &str = "partial_transcript";
const EVENT_COMMITTED_TRANSCRIPT: &str = "committed_transcript";
const EVENT_SESSION_STARTED: &str = "session_started";
const EVENT_RECORDING_ERROR: &str = "recording_error";
const EVENT_RECORDING_STATE: &str = "recording_state";
const EVENT_OVERLAY_VISIBILITY_CHANGED: &str = "overlay_visibility_changed";
const FALLBACK_HOTKEY: &str = "Ctrl+N";
const MIN_COMMITTED_CONFIDENCE: f32 = 0.10;
const MAX_COMMIT_INACTIVE_MS: u64 = 6_000;
const MAX_PARTIAL_INACTIVE_MS: u64 = 2_000;

type SetupResult<T> = Result<T, Box<dyn Error>>;

fn init_logging() -> Result<(), AppError> {
    tracing_subscriber::fmt()
        .with_target(false)
        .with_thread_ids(true)
        .with_file(true)
        .with_line_number(true)
        .with_env_filter("info")
        .try_init()
        .map_err(|err| AppError::LoggingInit(err.to_string()))
}

fn init_rustls_crypto_provider() {
    if rustls::crypto::CryptoProvider::get_default().is_some() {
        return;
    }

    if rustls::crypto::ring::default_provider()
        .install_default()
        .is_err()
    {
        warn!("rustls CryptoProvider was already installed");
    } else {
        info!("rustls CryptoProvider initialized with ring");
    }
}

fn setup_tray(app: &mut tauri::App) -> SetupResult<()> {
    let settings_item =
        MenuItem::with_id(app, MENU_ID_OPEN_SETTINGS, "Settings", true, None::<&str>)?;
    let toggle_overlay_item = MenuItem::with_id(
        app,
        MENU_ID_TOGGLE_OVERLAY,
        "Show/Hide Overlay",
        true,
        None::<&str>,
    )?;
    let quit_item = MenuItem::with_id(app, MENU_ID_QUIT, "Quit", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&settings_item, &toggle_overlay_item, &quit_item])?;

    TrayIconBuilder::new()
        .icon(tauri::include_image!("./icons/icon.png"))
        .menu(&menu)
        .show_menu_on_left_click(true)
        .on_menu_event(|app_handle, event| match event.id().as_ref() {
            MENU_ID_OPEN_SETTINGS => {
                if let Some(window) = app_handle.get_webview_window(MAIN_WINDOW_LABEL) {
                    if let Err(show_err) = window.show() {
                        warn!("failed to show main window from tray menu: {show_err}");
                    }
                    if let Err(focus_err) = window.set_focus() {
                        warn!("failed to focus main window from tray menu: {focus_err}");
                    }
                } else {
                    warn!("main window not found when opening settings from tray");
                }
            }
            MENU_ID_TOGGLE_OVERLAY => {
                let app_handle = app_handle.clone();
                tauri::async_runtime::spawn(async move {
                    toggle_overlay_visibility(&app_handle).await;
                });
            }
            MENU_ID_QUIT => {
                app_handle.exit(0);
            }
            _ => {}
        })
        .build(app)?;

    Ok(())
}

#[cfg(desktop)]
fn setup_global_shortcut(app: &mut tauri::App) -> SetupResult<()> {
    use tauri_plugin_global_shortcut::{
        Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState,
    };

    let configured_hotkey = {
        let state = app.state::<AppState>();
        let runtime = state.runtime();
        tauri::async_runtime::block_on(async {
            let hotkey = runtime.current_hotkey.lock().await;
            hotkey.clone()
        })
    };

    let shortcut = match configured_hotkey.parse::<Shortcut>() {
        Ok(value) => value,
        Err(err) => {
            warn!("invalid configured hotkey `{configured_hotkey}`: {err}; fallback to Ctrl+N");
            let fallback = Shortcut::new(Some(Modifiers::CONTROL), Code::KeyN);
            let state = app.state::<AppState>();
            let runtime = state.runtime();
            tauri::async_runtime::block_on(async {
                let mut hotkey = runtime.current_hotkey.lock().await;
                *hotkey = FALLBACK_HOTKEY.to_string();
            });
            fallback
        }
    };

    app.handle().plugin(
        tauri_plugin_global_shortcut::Builder::new()
            .with_handler(|app_handle, _, event| {
                let app_handle = app_handle.clone();
                match event.state {
                    ShortcutState::Pressed => {
                        tauri::async_runtime::spawn(async move {
                            commands::handle_shortcut_pressed(app_handle).await;
                        });
                    }
                    ShortcutState::Released => {
                        tauri::async_runtime::spawn(async move {
                            commands::handle_shortcut_released(app_handle).await;
                        });
                    }
                }
            })
            .build(),
    )?;

    app.global_shortcut().register(shortcut)?;
    Ok(())
}

#[cfg(not(desktop))]
fn setup_global_shortcut(_app: &mut tauri::App) -> SetupResult<()> {
    Ok(())
}

fn setup_app(app: &mut tauri::App) -> SetupResult<()> {
    let app_state = AppState::new();
    let runtime = app_state.runtime();
    match commands::load_settings(app.handle()) {
        Ok(settings) => {
            tauri::async_runtime::block_on(async {
                let mut hotkey = runtime.current_hotkey.lock().await;
                *hotkey = settings.hotkey;
                let mut threshold = runtime.injection_threshold.lock().await;
                *threshold = settings.injection_threshold;
                let mut rewrite_enabled = runtime.partial_rewrite_enabled.lock().await;
                *rewrite_enabled = settings.partial_rewrite_enabled;
                let mut rewrite_max_backspace = runtime.partial_rewrite_max_backspace.lock().await;
                *rewrite_max_backspace = settings.partial_rewrite_max_backspace;
                let mut rewrite_window_ms = runtime.partial_rewrite_window_ms.lock().await;
                *rewrite_window_ms = settings.partial_rewrite_window_ms;
            });
        }
        Err(err) => {
            warn!("failed to load persisted settings during startup: {err}");
        }
    }

    spawn_network_dispatcher(app.handle().clone(), Arc::clone(&runtime));
    spawn_injection_dispatcher(app.handle().clone(), Arc::clone(&runtime));
    app.manage(app_state);

    if let Some(window) = app.get_webview_window(MAIN_WINDOW_LABEL) {
        if let Err(err) = window.set_icon(tauri::include_image!("./icons/icon.png")) {
            warn!("failed to set main window icon: {err}");
        }
    }

    setup_tray(app)?;
    setup_global_shortcut(app)?;
    Ok(())
}

fn handle_run_event(app_handle: &tauri::AppHandle, event: RunEvent) {
    match event {
        RunEvent::WindowEvent {
            label,
            event: WindowEvent::CloseRequested { api, .. },
            ..
        } => {
            if label == MAIN_WINDOW_LABEL {
                api.prevent_close();
                if let Some(window) = app_handle.get_webview_window(MAIN_WINDOW_LABEL) {
                    if let Err(hide_err) = window.hide() {
                        warn!("failed to hide main window on close request: {hide_err}");
                    } else {
                        info!("main window hidden to tray");
                    }
                } else {
                    warn!("main window not found while handling close request");
                }
            }
        }
        RunEvent::ExitRequested { code, api, .. } => {
            if code.is_none() {
                api.prevent_exit();
                info!("prevented system-triggered app exit; app remains in tray");
            }
        }
        _ => {}
    }
}

fn spawn_network_dispatcher(app_handle: tauri::AppHandle, runtime: Arc<RuntimeState>) {
    let mut network_rx = runtime.network_events.subscribe();

    tauri::async_runtime::spawn(async move {
        loop {
            match network_rx.recv().await {
                Ok(NetworkEvent::Scribe(event)) => {
                    handle_scribe_event(&app_handle, &runtime, event).await;
                }
                Ok(NetworkEvent::TransportError(message)) => {
                    warn!("network transport error: {message}");
                    emit_string_event(&app_handle, EVENT_RECORDING_STATE, "Error");
                    emit_string_event(&app_handle, EVENT_RECORDING_ERROR, &message);
                }
                Err(broadcast::error::RecvError::Lagged(skipped)) => {
                    warn!("network dispatcher lagged, skipped {skipped} events");
                }
                Err(broadcast::error::RecvError::Closed) => {
                    warn!("network event channel closed");
                    break;
                }
            }
        }
    });
}

async fn handle_scribe_event(
    app_handle: &tauri::AppHandle,
    runtime: &Arc<RuntimeState>,
    event: ScribeEvent,
) {
    match event {
        ScribeEvent::SessionStarted { session_id, .. } => {
            info!(session_id = session_id.as_str(), "scribe session started");
            emit_string_event(app_handle, EVENT_RECORDING_STATE, "Listening");
            emit_string_event(app_handle, EVENT_SESSION_STARTED, &session_id);
        }
        ScribeEvent::PartialTranscript { text, .. } => {
            let language_code = current_language_code(runtime).await;
            let normalized_text = normalize_transcript_text(&text, &language_code);
            emit_string_event(app_handle, EVENT_PARTIAL_TRANSCRIPT, &normalized_text);

            if !is_text_cursor_available() {
                let mut tracker = runtime.live_partial_tracker.lock().await;
                tracker.mode = TranscriptInjectionMode::ClipboardOnly;
                return;
            }

            inject_partial_transcript_delta(app_handle, runtime, &normalized_text).await;
        }
        ScribeEvent::CommittedTranscript {
            text,
            confidence,
            created_at_ms,
        } => {
            let now_ms = now_epoch_ms();
            let last_voice_activity_ms = runtime.last_voice_activity_ms.load(Ordering::Relaxed);
            if last_voice_activity_ms == 0
                || now_ms.saturating_sub(last_voice_activity_ms) > MAX_COMMIT_INACTIVE_MS
            {
                info!(
                    last_voice_activity_ms,
                    now_ms,
                    max_inactive_ms = MAX_COMMIT_INACTIVE_MS,
                    "dropped committed transcript because no recent local voice activity was detected"
                );
                return;
            }

            if !confidence.is_finite() {
                warn!("dropped committed transcript due to non-finite confidence value");
                return;
            }
            if should_drop_low_confidence_committed(confidence) {
                info!(
                    confidence,
                    min_confidence = MIN_COMMITTED_CONFIDENCE,
                    "dropped low-confidence committed transcript"
                );
                return;
            }

            let language_code = current_language_code(runtime).await;
            let normalized_text = normalize_transcript_text(&text, &language_code);
            let committed_text = append_terminal_punctuation(&normalized_text);
            if committed_text.trim().is_empty() {
                return;
            }

            let (text_for_injection, pending_clipboard_text) = {
                let mut tracker = runtime.live_partial_tracker.lock().await;
                if !tracker.injected_text.trim().is_empty() {
                    let punctuation_only = resolve_committed_punctuation_delta(
                        &committed_text,
                        &tracker.injected_text,
                    );
                    tracker.reset_after_commit();
                    (punctuation_only, None)
                } else {
                    let pending_clipboard_text = append_to_pending_clipboard(
                        &mut tracker.pending_clipboard_text,
                        &committed_text,
                    );
                    tracker.reset_after_commit();
                    (String::new(), Some(pending_clipboard_text))
                }
            };

            if let Some(pending_text) = pending_clipboard_text {
                if let Err(err) = InputInjector::write_clipboard_only(&pending_text, app_handle) {
                    warn!("failed to update clipboard-only transcript buffer: {err}");
                    emit_string_event(app_handle, EVENT_RECORDING_STATE, "Error");
                    emit_string_event(app_handle, EVENT_RECORDING_ERROR, &err.to_string());
                } else {
                    info!("committed transcript appended to clipboard-only buffer");
                }
            }

            let mut dropped = 0_u64;
            let mut queued_for_injection = false;
            if !text_for_injection.trim().is_empty() {
                let mut queue = runtime.committed_queue.lock().await;
                queue.push_back(CommittedTranscript {
                    text: text_for_injection,
                    confidence,
                    created_at_ms,
                });
                queued_for_injection = true;
                if queue.len() > 128 {
                    queue.pop_front();
                    dropped = 1;
                }
            }
            if dropped > 0 {
                let mut metrics = runtime.metrics.lock().await;
                metrics.record_committed_drop(dropped);
            }
            if queued_for_injection {
                runtime.injection_notify.notify_one();
            }
            emit_string_event(app_handle, EVENT_COMMITTED_TRANSCRIPT, &committed_text);
        }
        ScribeEvent::InputError { error_message } => {
            warn!("scribe input_error: {error_message}");
            emit_string_event(app_handle, EVENT_RECORDING_STATE, "Error");
            emit_string_event(app_handle, EVENT_RECORDING_ERROR, &error_message);
        }
        ScribeEvent::Error {
            error_message,
            error,
        } => {
            let combined = if !error_message.trim().is_empty() {
                error_message
            } else if !error.trim().is_empty() {
                error
            } else {
                "unknown scribe error".to_string()
            };
            warn!("scribe error: {combined}");
            emit_string_event(app_handle, EVENT_RECORDING_STATE, "Error");
            emit_string_event(app_handle, EVENT_RECORDING_ERROR, &combined);
        }
        ScribeEvent::AuthError {
            error_message,
            error,
        } => {
            let combined = if !error_message.trim().is_empty() {
                error_message
            } else if !error.trim().is_empty() {
                error
            } else {
                "authentication failed".to_string()
            };
            warn!("scribe auth_error: {combined}");
            emit_string_event(app_handle, EVENT_RECORDING_STATE, "Error");
            emit_string_event(app_handle, EVENT_RECORDING_ERROR, &combined);
        }
        ScribeEvent::Unknown => {
            info!("ignored unknown scribe event");
        }
    }
}

fn spawn_injection_dispatcher(app_handle: tauri::AppHandle, runtime: Arc<RuntimeState>) {
    tauri::async_runtime::spawn(async move {
        loop {
            runtime.injection_notify.notified().await;

            loop {
                let pending = {
                    let mut queue = runtime.committed_queue.lock().await;
                    queue.pop_front()
                };

                let Some(transcript) = pending else {
                    break;
                };

                emit_string_event(&app_handle, EVENT_RECORDING_STATE, "Injecting");

                let threshold = {
                    let threshold = runtime.injection_threshold.lock().await;
                    *threshold
                };
                let inject_started = Instant::now();
                let inject_result = {
                    let app_handle = app_handle.clone();
                    tauri::async_runtime::spawn_blocking(move || {
                        let mut injector = InputInjector::new(threshold)?;
                        injector.inject_text(&transcript.text, &app_handle)
                    })
                    .await
                };

                match inject_result {
                    Ok(Ok(())) => {
                        let injection_ms = inject_started.elapsed().as_millis() as u64;
                        let mut metrics = runtime.metrics.lock().await;
                        metrics.record_injection(injection_ms);
                        if transcript.created_at_ms > 1_000_000_000_000 {
                            let now_ms = now_epoch_ms();
                            if now_ms > transcript.created_at_ms {
                                metrics.record_end_to_end(now_ms - transcript.created_at_ms);
                            }
                        }
                        info!("transcript injected successfully");
                        emit_string_event(&app_handle, EVENT_RECORDING_STATE, "Idle");
                    }
                    Ok(Err(err)) => {
                        let injection_ms = inject_started.elapsed().as_millis() as u64;
                        let mut metrics = runtime.metrics.lock().await;
                        metrics.record_injection(injection_ms);
                        warn!("failed to inject transcript: {err}");
                        emit_string_event(&app_handle, EVENT_RECORDING_STATE, "Error");
                        emit_string_event(&app_handle, EVENT_RECORDING_ERROR, &err.to_string());
                    }
                    Err(err) => {
                        let injection_ms = inject_started.elapsed().as_millis() as u64;
                        let mut metrics = runtime.metrics.lock().await;
                        metrics.record_injection(injection_ms);
                        warn!("failed to run injector task: {err}");
                        emit_string_event(&app_handle, EVENT_RECORDING_STATE, "Error");
                        emit_string_event(
                            &app_handle,
                            EVENT_RECORDING_ERROR,
                            "injection task failed",
                        );
                    }
                }
            }
        }
    });
}

async fn toggle_overlay_visibility(app_handle: &tauri::AppHandle) {
    let runtime = {
        let state = app_handle.state::<AppState>();
        state.runtime()
    };

    let next_visible = {
        let mut visible = runtime.overlay_visible.lock().await;
        *visible = !*visible;
        *visible
    };

    emit_bool_event(app_handle, EVENT_OVERLAY_VISIBILITY_CHANGED, next_visible);

    if let Some(window) = app_handle.get_webview_window("overlay") {
        let result = if next_visible {
            window.show()
        } else {
            window.hide()
        };
        if let Err(err) = result {
            warn!("failed to toggle overlay window visibility: {err}");
        }
    }
}

fn emit_string_event(app_handle: &tauri::AppHandle, event_name: &str, value: &str) {
    if let Err(err) = app_handle.emit(event_name, value.to_string()) {
        warn!(event_name = event_name, "failed to emit event: {err}");
    }
}

fn emit_bool_event(app_handle: &tauri::AppHandle, event_name: &str, value: bool) {
    if let Err(err) = app_handle.emit(event_name, value) {
        warn!(event_name = event_name, "failed to emit bool event: {err}");
    }
}

async fn current_language_code(runtime: &Arc<RuntimeState>) -> String {
    let binding = runtime.client_binding.lock().await;
    binding
        .as_ref()
        .map(|client| client.language_code.clone())
        .unwrap_or_else(|| "eng".to_string())
}

fn append_to_pending_clipboard(pending: &mut String, new_text: &str) -> String {
    let segment = new_text.trim();
    if segment.is_empty() {
        return pending.clone();
    }

    if !pending.is_empty() {
        let previous = pending.chars().rev().find(|ch| !ch.is_whitespace());
        let upcoming = segment.chars().find(|ch| !ch.is_whitespace());
        if let (Some(previous), Some(upcoming)) = (previous, upcoming) {
            let needs_separator = !is_join_boundary_punctuation(previous)
                && !is_join_boundary_punctuation(upcoming)
                && !is_cjk(previous)
                && !is_cjk(upcoming);
            if needs_separator {
                pending.push(' ');
            }
        }
    }

    pending.push_str(segment);
    pending.clone()
}

fn is_join_boundary_punctuation(ch: char) -> bool {
    matches!(
        ch,
        '.' | ',' | '!' | '?' | ';' | ':' | '，' | '。' | '！' | '？' | '；' | '：' | '、'
    )
}

fn is_cjk(ch: char) -> bool {
    matches!(
        ch as u32,
        0x3400..=0x4DBF
            | 0x4E00..=0x9FFF
            | 0xF900..=0xFAFF
            | 0x20000..=0x2A6DF
            | 0x2A700..=0x2B73F
            | 0x2B740..=0x2B81F
            | 0x2B820..=0x2CEAF
            | 0x2CEB0..=0x2EBEF
            | 0x3000..=0x303F
    )
}

#[cfg(target_os = "windows")]
fn is_text_cursor_available() -> bool {
    use std::mem::{size_of, zeroed};
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        GUITHREADINFO, GetForegroundWindow, GetGUIThreadInfo, GetWindowThreadProcessId,
    };

    unsafe {
        let foreground_window = GetForegroundWindow();
        if foreground_window.is_null() {
            return false;
        }

        let thread_id = GetWindowThreadProcessId(foreground_window, std::ptr::null_mut());
        if thread_id == 0 {
            return false;
        }

        let mut info: GUITHREADINFO = zeroed();
        info.cbSize = size_of::<GUITHREADINFO>() as u32;

        if GetGUIThreadInfo(thread_id, &mut info) == 0 {
            return false;
        }

        !info.hwndCaret.is_null()
    }
}

#[cfg(not(target_os = "windows"))]
fn is_text_cursor_available() -> bool {
    true
}

#[derive(Clone)]
enum PartialInjectionPlan {
    Append {
        delta: String,
        next_injected_text: String,
    },
    Rewrite {
        backspace_count: usize,
        insert_text: String,
        next_injected_text: String,
    },
}

async fn current_partial_rewrite_config(runtime: &Arc<RuntimeState>) -> (bool, usize, u64) {
    let enabled = {
        let value = runtime.partial_rewrite_enabled.lock().await;
        *value
    };
    let max_backspace = {
        let value = runtime.partial_rewrite_max_backspace.lock().await;
        *value
    };
    let window_ms = {
        let value = runtime.partial_rewrite_window_ms.lock().await;
        *value
    };

    (enabled, max_backspace, window_ms)
}

async fn inject_partial_transcript_delta(
    app_handle: &tauri::AppHandle,
    runtime: &Arc<RuntimeState>,
    partial_text: &str,
) {
    let normalized = partial_text.trim();
    if normalized.is_empty() {
        return;
    }

    let now_ms = now_epoch_ms();
    let last_voice_activity_ms = runtime.last_voice_activity_ms.load(Ordering::Relaxed);
    if last_voice_activity_ms == 0
        || now_ms.saturating_sub(last_voice_activity_ms) > MAX_PARTIAL_INACTIVE_MS
    {
        return;
    }

    let (rewrite_enabled, rewrite_max_backspace, rewrite_window_ms) =
        current_partial_rewrite_config(runtime).await;

    let injection_plan = {
        let mut tracker = runtime.live_partial_tracker.lock().await;
        if matches!(tracker.mode, TranscriptInjectionMode::ClipboardOnly) {
            None
        } else if tracker.disabled_until_commit {
            None
        } else if tracker.injected_text.is_empty() {
            Some(PartialInjectionPlan::Append {
                delta: normalized.to_string(),
                next_injected_text: normalized.to_string(),
            })
        } else if let Some(delta) = normalized.strip_prefix(tracker.injected_text.as_str()) {
            if delta.is_empty() {
                None
            } else {
                Some(PartialInjectionPlan::Append {
                    delta: delta.to_string(),
                    next_injected_text: normalized.to_string(),
                })
            }
        } else if !rewrite_enabled {
            tracker.disabled_until_commit = true;
            info!("disabled live partial injection due to transcript revision");
            None
        } else {
            let common_prefix_chars =
                common_prefix_char_count(tracker.injected_text.as_str(), normalized);
            let previous_chars = tracker.injected_text.chars().count();
            let backspace_count = previous_chars.saturating_sub(common_prefix_chars);

            if backspace_count == 0 {
                None
            } else if backspace_count > rewrite_max_backspace {
                tracker.disabled_until_commit = true;
                info!(
                    backspace_count,
                    rewrite_max_backspace,
                    "disabled live partial injection due to rewrite backspace limit"
                );
                None
            } else if rewrite_window_ms > 0
                && tracker.last_rewrite_at_ms > 0
                && now_ms.saturating_sub(tracker.last_rewrite_at_ms) < rewrite_window_ms
            {
                None
            } else {
                tracker.last_rewrite_at_ms = now_ms;
                let insert_text = suffix_from_char_index(normalized, common_prefix_chars);
                Some(PartialInjectionPlan::Rewrite {
                    backspace_count,
                    insert_text,
                    next_injected_text: normalized.to_string(),
                })
            }
        }
    };

    let Some(plan) = injection_plan else {
        return;
    };

    let threshold = {
        let threshold = runtime.injection_threshold.lock().await;
        *threshold
    };
    let inject_started = Instant::now();
    let inject_result = {
        let plan_for_exec = plan.clone();
        let app_handle = app_handle.clone();
        tauri::async_runtime::spawn_blocking(move || {
            let mut injector = InputInjector::new(threshold)?;
            match plan_for_exec {
                PartialInjectionPlan::Append { delta, .. } => {
                    injector.inject_text(&delta, &app_handle)
                }
                PartialInjectionPlan::Rewrite {
                    backspace_count,
                    insert_text,
                    ..
                } => injector.rewrite_tail(backspace_count, &insert_text, &app_handle),
            }
        })
        .await
    };

    let injection_ms = inject_started.elapsed().as_millis() as u64;
    {
        let mut metrics = runtime.metrics.lock().await;
        metrics.record_injection(injection_ms);
    }

    match inject_result {
        Ok(Ok(())) => {
            let mut tracker = runtime.live_partial_tracker.lock().await;
            if !tracker.disabled_until_commit {
                tracker.injected_text = match plan {
                    PartialInjectionPlan::Append {
                        next_injected_text, ..
                    } => next_injected_text,
                    PartialInjectionPlan::Rewrite {
                        next_injected_text, ..
                    } => next_injected_text,
                };
                tracker.mode = TranscriptInjectionMode::RealtimeCursor;
            }
        }
        Ok(Err(err)) => {
            warn!("failed to inject partial transcript delta: {err}");
            let mut tracker = runtime.live_partial_tracker.lock().await;
            tracker.disabled_until_commit = true;
            if matches!(tracker.mode, TranscriptInjectionMode::Undetermined) {
                tracker.mode = TranscriptInjectionMode::ClipboardOnly;
            }
        }
        Err(err) => {
            warn!("failed to run partial injection task: {err}");
            let mut tracker = runtime.live_partial_tracker.lock().await;
            tracker.disabled_until_commit = true;
            if matches!(tracker.mode, TranscriptInjectionMode::Undetermined) {
                tracker.mode = TranscriptInjectionMode::ClipboardOnly;
            }
        }
    }
}

fn common_prefix_char_count(left: &str, right: &str) -> usize {
    left.chars()
        .zip(right.chars())
        .take_while(|(l, r)| l == r)
        .count()
}

fn suffix_from_char_index(text: &str, char_index: usize) -> String {
    let mut split_at = text.len();
    let mut seen = 0_usize;
    for (byte_index, _) in text.char_indices() {
        if seen == char_index {
            split_at = byte_index;
            break;
        }
        seen += 1;
    }

    if char_index >= text.chars().count() {
        String::new()
    } else {
        text[split_at..].to_string()
    }
}

fn now_epoch_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or(0)
}

fn should_drop_low_confidence_committed(confidence: f32) -> bool {
    // ElevenLabs can emit committed_transcript with confidence=0.0 as "unknown".
    // Treat 0.0 as not-provided rather than low quality, otherwise valid commits
    // are mistakenly dropped and never injected.
    if confidence <= 0.0 {
        return false;
    }

    confidence < MIN_COMMITTED_CONFIDENCE
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    if let Err(init_err) = init_logging() {
        eprintln!("logging bootstrap failed: {init_err}");
    }
    init_rustls_crypto_provider();

    info!("starting raflow phase 5 runtime");

    let builder = tauri::Builder::default()
        .setup(setup_app)
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![
            commands::ping,
            commands::app_status,
            commands::check_permissions,
            commands::get_performance_report,
            commands::start_recording,
            commands::stop_recording,
            commands::get_settings,
            commands::save_settings,
            commands::save_api_key,
            commands::get_api_key,
            commands::dequeue_committed_transcript,
            commands::committed_queue_len
        ]);

    let app = match builder.build(tauri::generate_context!()) {
        Ok(app) => app,
        Err(build_err) => {
            error!("failed to build tauri app: {build_err}");
            return;
        }
    };

    app.run(handle_run_event);
}

#[cfg(test)]
mod tests {
    use super::{
        append_to_pending_clipboard, common_prefix_char_count,
        should_drop_low_confidence_committed, suffix_from_char_index,
    };

    #[test]
    fn confidence_zero_is_not_dropped() {
        assert!(!should_drop_low_confidence_committed(0.0));
    }

    #[test]
    fn positive_low_confidence_is_dropped() {
        assert!(should_drop_low_confidence_committed(0.01));
    }

    #[test]
    fn clipboard_pending_buffer_appends_without_overwrite() {
        let mut pending = String::new();
        assert_eq!(
            append_to_pending_clipboard(&mut pending, "hello world"),
            "hello world"
        );
        assert_eq!(
            append_to_pending_clipboard(&mut pending, "new chunk"),
            "hello world new chunk"
        );
    }

    #[test]
    fn clipboard_pending_buffer_keeps_chinese_contiguous() {
        let mut pending = "你好".to_string();
        assert_eq!(
            append_to_pending_clipboard(&mut pending, "世界"),
            "你好世界"
        );
    }

    #[test]
    fn clipboard_pending_buffer_ignores_empty_segment() {
        let mut pending = "existing".to_string();
        assert_eq!(append_to_pending_clipboard(&mut pending, "   "), "existing");
    }

    #[test]
    fn partial_rewrite_helpers_compute_expected_suffix() {
        let before = "modern test";
        let after = "model test";
        let prefix = common_prefix_char_count(before, after);
        assert_eq!(prefix, 4);
        assert_eq!(suffix_from_char_index(after, prefix), "l test");
    }
}
