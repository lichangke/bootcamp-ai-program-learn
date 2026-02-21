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
use input::{append_terminal_punctuation, injector::InputInjector};
use network::{NetworkEvent, ScribeEvent};
use state::{AppState, CommittedTranscript, RuntimeState};
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
            emit_string_event(app_handle, EVENT_PARTIAL_TRANSCRIPT, &text);
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

            let committed_text = append_terminal_punctuation(&text);
            if committed_text.trim().is_empty() {
                return;
            }

            let mut dropped = 0_u64;
            {
                let mut queue = runtime.committed_queue.lock().await;
                queue.push_back(CommittedTranscript {
                    text: committed_text.clone(),
                    confidence,
                    created_at_ms,
                });
                if queue.len() > 128 {
                    queue.pop_front();
                    dropped = 1;
                }
            }
            if dropped > 0 {
                let mut metrics = runtime.metrics.lock().await;
                metrics.record_committed_drop(dropped);
            }
            runtime.injection_notify.notify_one();
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
    use super::should_drop_low_confidence_committed;

    #[test]
    fn confidence_zero_is_not_dropped() {
        assert!(!should_drop_low_confidence_committed(0.0));
    }

    #[test]
    fn positive_low_confidence_is_dropped() {
        assert!(should_drop_low_confidence_committed(0.01));
    }
}
