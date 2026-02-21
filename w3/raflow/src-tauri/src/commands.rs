use std::fs;
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Manager, State};
use tokio::sync::mpsc;
use tracing::{error, info, warn};

use crate::audio::{AudioCapturer, AudioConfig, ProcessedAudioChunk, audio_processing_task};
use crate::error::AppError;
use crate::input::{
    DEFAULT_PARTIAL_REWRITE_ENABLED, DEFAULT_PARTIAL_REWRITE_MAX_BACKSPACE,
    DEFAULT_PARTIAL_REWRITE_WINDOW_MS, MAX_PARTIAL_REWRITE_MAX_BACKSPACE,
    MAX_PARTIAL_REWRITE_WINDOW_MS, MIN_PARTIAL_REWRITE_MAX_BACKSPACE,
    MIN_PARTIAL_REWRITE_WINDOW_MS,
};
use crate::metrics::PerformanceReport;
use crate::network::ScribeClient;
use crate::permissions::PermissionReport;
use crate::secure_storage;
use crate::state::{AppState, ClientBinding, CommittedTranscript, RecordingSession, RuntimeState};

const RECORDING_ERROR_EVENT: &str = "recording_error";
const RECORDING_STATE_EVENT: &str = "recording_state";
const DEFAULT_HOTKEY: &str = "Ctrl+N";
const AUDIO_CHANNEL_CAPACITY: usize = 16;
const MAX_AUDIO_BATCH_CHUNKS: usize = 3;
const MAX_AUDIO_BATCH_DELAY_MS: u64 = 180;
const SLOW_NETWORK_SEND_MS: u64 = 250;
const ENABLE_SILENCE_SUPPRESSION: bool = false;
const SILENCE_RMS_THRESHOLD: f32 = 0.0015;
const SILENCE_PEAK_THRESHOLD_I16: i16 = 120;
const SILENCE_CHUNK_GRACE: usize = 12;
const SILENCE_SUPPRESS_LOG_EVERY: u64 = 50;
const VOICE_ACTIVITY_RMS_THRESHOLD: f32 = 0.0008;
const VOICE_ACTIVITY_PEAK_THRESHOLD_I16: i16 = 80;

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AppStatus {
    pub service: &'static str,
    pub version: &'static str,
    pub ready: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppSettings {
    #[serde(default)]
    pub api_key: String,
    #[serde(default = "default_language_code")]
    pub language_code: String,
    #[serde(default = "default_hotkey")]
    pub hotkey: String,
    #[serde(default = "default_partial_rewrite_enabled")]
    pub partial_rewrite_enabled: bool,
    #[serde(default = "default_partial_rewrite_max_backspace")]
    pub partial_rewrite_max_backspace: usize,
    #[serde(default = "default_partial_rewrite_window_ms")]
    pub partial_rewrite_window_ms: u64,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            api_key: String::new(),
            language_code: default_language_code(),
            hotkey: default_hotkey(),
            partial_rewrite_enabled: default_partial_rewrite_enabled(),
            partial_rewrite_max_backspace: default_partial_rewrite_max_backspace(),
            partial_rewrite_window_ms: default_partial_rewrite_window_ms(),
        }
    }
}

fn default_language_code() -> String {
    "eng".to_string()
}

fn default_hotkey() -> String {
    DEFAULT_HOTKEY.to_string()
}

fn default_partial_rewrite_enabled() -> bool {
    DEFAULT_PARTIAL_REWRITE_ENABLED
}

fn default_partial_rewrite_max_backspace() -> usize {
    DEFAULT_PARTIAL_REWRITE_MAX_BACKSPACE
}

fn default_partial_rewrite_window_ms() -> u64 {
    DEFAULT_PARTIAL_REWRITE_WINDOW_MS
}

fn read_api_key_from_environment() -> Option<String> {
    for key_name in ["ELEVENLABS_KEY", "ELEVENLABS_API_KEY"] {
        if let Ok(value) = std::env::var(key_name) {
            let trimmed = value.trim();
            if !trimmed.is_empty() {
                return Some(trimmed.to_string());
            }
        }
    }

    None
}

#[tauri::command]
pub fn ping() -> String {
    info!("received ping command");
    "pong".to_string()
}

fn status_snapshot() -> Result<AppStatus, AppError> {
    Ok(AppStatus {
        service: "raflow-core",
        version: env!("CARGO_PKG_VERSION"),
        ready: true,
    })
}

#[tauri::command]
pub fn app_status() -> Result<AppStatus, String> {
    status_snapshot().map_err(|err| err.to_string())
}

#[tauri::command]
pub fn check_permissions() -> PermissionReport {
    crate::permissions::check_permissions()
}

#[tauri::command]
pub async fn get_performance_report(
    state: State<'_, AppState>,
) -> Result<PerformanceReport, String> {
    let runtime = state.runtime();
    let metrics = runtime.metrics.lock().await;
    Ok(metrics.report())
}

#[tauri::command]
pub async fn start_recording(
    app_handle: AppHandle,
    state: State<'_, AppState>,
) -> Result<(), String> {
    let app_state = state.inner().clone();
    start_recording_impl(&app_handle, &app_state)
        .await
        .map_err(|err| err.to_string())
}

#[tauri::command]
pub async fn stop_recording(
    app_handle: AppHandle,
    state: State<'_, AppState>,
) -> Result<(), String> {
    let app_state = state.inner().clone();
    stop_recording_impl(&app_handle, &app_state)
        .await
        .map_err(|err| err.to_string())
}

#[tauri::command]
pub async fn save_api_key(
    app_handle: AppHandle,
    state: State<'_, AppState>,
    api_key: String,
) -> Result<(), String> {
    let mut settings = load_settings(&app_handle)?;
    settings.api_key = api_key;
    let runtime = state.runtime();
    save_settings_impl(&app_handle, &runtime, settings)
        .await
        .map(|_| ())
}

#[tauri::command]
pub fn get_settings(app_handle: AppHandle) -> Result<AppSettings, String> {
    load_settings(&app_handle)
}

#[tauri::command]
pub async fn save_settings(
    app_handle: AppHandle,
    state: State<'_, AppState>,
    settings: AppSettings,
) -> Result<AppSettings, String> {
    let runtime = state.runtime();
    save_settings_impl(&app_handle, &runtime, settings).await
}

#[tauri::command]
pub fn get_api_key(app_handle: AppHandle) -> Result<String, String> {
    load_settings(&app_handle).map(|settings| settings.api_key)
}

#[tauri::command]
pub async fn dequeue_committed_transcript(
    state: State<'_, AppState>,
) -> Result<Option<CommittedTranscript>, String> {
    let runtime = state.runtime();
    let mut queue = runtime.committed_queue.lock().await;
    Ok(queue.pop_front())
}

#[tauri::command]
pub async fn committed_queue_len(state: State<'_, AppState>) -> Result<usize, String> {
    let runtime = state.runtime();
    let queue = runtime.committed_queue.lock().await;
    Ok(queue.len())
}

pub async fn handle_shortcut_pressed(app_handle: AppHandle) {
    let app_state = {
        let state = app_handle.state::<AppState>();
        state.inner().clone()
    };

    if let Err(err) = start_recording_impl(&app_handle, &app_state).await {
        emit_error(&app_handle, &err.to_string());
    }
}

pub async fn handle_shortcut_released(app_handle: AppHandle) {
    let app_state = {
        let state = app_handle.state::<AppState>();
        state.inner().clone()
    };

    if let Err(err) = stop_recording_impl(&app_handle, &app_state).await {
        emit_error(&app_handle, &err.to_string());
    }
}

pub fn load_settings(app_handle: &AppHandle) -> Result<AppSettings, String> {
    let mut settings = normalize_loaded_settings(read_config(app_handle)?);

    match secure_storage::read_api_key() {
        Ok(Some(api_key)) => {
            settings.api_key = api_key;
        }
        Ok(None) => {
            if !settings.api_key.is_empty() {
                // Backward-compatible migration for users who still have legacy plaintext config.
                if let Err(err) = secure_storage::write_api_key(&settings.api_key) {
                    warn!("failed to migrate API key into secure storage: {err}");
                } else {
                    let mut sanitized = settings.clone();
                    sanitized.api_key.clear();
                    if let Err(err) = write_config(app_handle, &sanitized) {
                        warn!("failed to rewrite sanitized config after secure migration: {err}");
                    }
                }
            }
        }
        Err(err) => {
            warn!("failed to read API key from secure storage; using config fallback: {err}");
        }
    }

    if settings.api_key.trim().is_empty() {
        if let Some(env_api_key) = read_api_key_from_environment() {
            settings.api_key = env_api_key;
        }
    }

    Ok(settings)
}

async fn save_settings_impl(
    app_handle: &AppHandle,
    runtime: &Arc<RuntimeState>,
    settings: AppSettings,
) -> Result<AppSettings, String> {
    let previous = load_settings(app_handle)?;
    let validated = validate_settings(settings)?;
    let previous_hotkey = {
        let hotkey = runtime.current_hotkey.lock().await;
        hotkey.clone()
    };

    if previous_hotkey != validated.hotkey {
        apply_hotkey_change(app_handle, &previous_hotkey, &validated.hotkey)?;
    }

    let secure_storage_available = match secure_storage::write_api_key(&validated.api_key) {
        Ok(()) => {
            if validated.api_key.trim().is_empty() {
                true
            } else {
                match secure_storage::read_api_key() {
                    Ok(Some(saved_key)) if saved_key.trim() == validated.api_key.trim() => true,
                    Ok(_) => {
                        warn!(
                            "secure storage write could not be verified, fallback to config persistence"
                        );
                        false
                    }
                    Err(err) => {
                        warn!(
                            "failed to verify API key from secure storage, fallback to config persistence: {err}"
                        );
                        false
                    }
                }
            }
        }
        Err(err) => {
            warn!(
                "failed to write API key into secure storage, fallback to config persistence: {err}"
            );
            false
        }
    };

    let mut persisted = validated.clone();
    if secure_storage_available {
        persisted.api_key.clear();
    }
    write_config(app_handle, &persisted)?;

    {
        let mut hotkey = runtime.current_hotkey.lock().await;
        *hotkey = validated.hotkey.clone();
    }
    {
        let mut enabled = runtime.partial_rewrite_enabled.lock().await;
        *enabled = validated.partial_rewrite_enabled;
    }
    {
        let mut max_backspace = runtime.partial_rewrite_max_backspace.lock().await;
        *max_backspace = validated.partial_rewrite_max_backspace;
    }
    {
        let mut window_ms = runtime.partial_rewrite_window_ms.lock().await;
        *window_ms = validated.partial_rewrite_window_ms;
    }

    if previous.api_key != validated.api_key || previous.language_code != validated.language_code {
        disconnect_cached_client(runtime).await;
    }

    Ok(validated)
}

async fn start_recording_impl(app_handle: &AppHandle, state: &AppState) -> Result<(), AppError> {
    let runtime = state.runtime();
    {
        let mut tracker = runtime.live_partial_tracker.lock().await;
        tracker.reset_for_session();
    }
    runtime.last_voice_activity_ms.store(0, Ordering::Relaxed);

    {
        let is_recording = runtime.is_recording.lock().await;
        if *is_recording {
            return Ok(());
        }
    }

    emit_state(app_handle, "Connecting");

    let config = load_settings(app_handle).map_err(AppError::Runtime)?;
    if config.api_key.trim().is_empty() {
        return Err(AppError::Runtime(
            "API key is missing. Save a valid ElevenLabs API key first.".to_string(),
        ));
    }

    let client = get_or_create_client(
        runtime.as_ref(),
        config.api_key.clone(),
        config.language_code.clone(),
    )
    .await;
    client
        .ensure_connected()
        .await
        .map_err(|err| AppError::Runtime(err.to_string()))?;

    let audio_config = AudioConfig::default();
    let (stop_tx, stop_rx) = std::sync::mpsc::channel::<()>();
    let (ready_tx, ready_rx) = std::sync::mpsc::sync_channel::<Result<(), String>>(1);
    let worker_client = Arc::clone(&client);
    let worker_runtime = Arc::clone(&runtime);
    let worker_handle = thread::spawn(move || {
        run_recording_worker(
            worker_client,
            worker_runtime,
            audio_config,
            stop_rx,
            ready_tx,
        );
    });

    match ready_rx.recv_timeout(Duration::from_secs(5)) {
        Ok(Ok(())) => {}
        Ok(Err(err)) => {
            let _ = stop_tx.send(());
            let _ = worker_handle.join();
            return Err(AppError::Runtime(err));
        }
        Err(err) => {
            let _ = stop_tx.send(());
            let _ = worker_handle.join();
            return Err(AppError::Runtime(format!(
                "recording worker did not become ready: {err}"
            )));
        }
    }

    {
        let mut session = runtime.session.lock().await;
        *session = Some(RecordingSession {
            stop_tx,
            worker_handle,
        });
    }

    {
        let mut is_recording = runtime.is_recording.lock().await;
        *is_recording = true;
    }

    emit_state(app_handle, "Recording");
    info!("recording pipeline started");

    Ok(())
}

async fn stop_recording_impl(app_handle: &AppHandle, state: &AppState) -> Result<(), AppError> {
    let runtime = state.runtime();

    {
        let mut is_recording = runtime.is_recording.lock().await;
        if !*is_recording {
            return Ok(());
        }
        *is_recording = false;
    }

    emit_state(app_handle, "Processing");

    let session = {
        let mut session_guard = runtime.session.lock().await;
        session_guard.take()
    };

    if let Some(session) = session {
        let _ = session.stop_tx.send(());

        match tauri::async_runtime::spawn_blocking(move || session.worker_handle.join()).await {
            Ok(Ok(())) => {}
            Ok(Err(_)) => {
                warn!("recording worker thread panicked");
            }
            Err(err) => {
                warn!("failed to join recording worker thread: {err}");
            }
        }
    }

    // Keep live partial tracker and recent voice activity until late committed
    // events are handled; they will be reset at the next recording start.

    emit_state(app_handle, "Idle");
    info!("recording pipeline stopped");
    Ok(())
}

fn run_recording_worker(
    client: Arc<ScribeClient>,
    runtime_state: Arc<RuntimeState>,
    audio_config: AudioConfig,
    stop_rx: std::sync::mpsc::Receiver<()>,
    ready_tx: std::sync::mpsc::SyncSender<Result<(), String>>,
) {
    let runtime = match tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
    {
        Ok(runtime) => runtime,
        Err(err) => {
            let _ = ready_tx.send(Err(format!("failed to create runtime: {err}")));
            return;
        }
    };

    runtime.block_on(async move {
        let mut capturer = match AudioCapturer::new(audio_config.clone()) {
            Ok(value) => value,
            Err(err) => {
                let _ = ready_tx.send(Err(err.to_string()));
                return;
            }
        };

        let consumer = match capturer.take_consumer() {
            Ok(value) => value,
            Err(err) => {
                let _ = ready_tx.send(Err(err.to_string()));
                return;
            }
        };

        if let Err(err) = capturer.start() {
            let _ = ready_tx.send(Err(err.to_string()));
            return;
        }

        if ready_tx.send(Ok(())).is_err() {
            let _ = capturer.stop();
            return;
        }

        let dropped_audio_counter = Arc::new(AtomicU64::new(0));
        let processing_drop_counter = Arc::clone(&dropped_audio_counter);
        let (audio_tx, mut audio_rx) = mpsc::channel::<ProcessedAudioChunk>(AUDIO_CHANNEL_CAPACITY);
        let processing_task = tokio::spawn(async move {
            if let Err(err) =
                audio_processing_task(consumer, audio_tx, audio_config, processing_drop_counter).await
            {
                warn!("audio processing task finished with error: {err}");
            }
        });

        let sender_client = Arc::clone(&client);
        let sender_runtime = Arc::clone(&runtime_state);
        let sender_task = tokio::spawn(async move {
            let mut batch_samples = Vec::<i16>::new();
            let mut batch_chunks = 0_usize;
            let mut silent_streak = 0_usize;
            let mut suppressed_silence_chunks = 0_u64;
            let mut ticker = tokio::time::interval(Duration::from_millis(MAX_AUDIO_BATCH_DELAY_MS));

            loop {
                tokio::select! {
                    _ = ticker.tick() => {
                        if batch_chunks > 0 {
                            flush_audio_batch(&sender_client, &sender_runtime, &mut batch_samples, &mut batch_chunks).await;
                        }
                    }
                    next_chunk = audio_rx.recv() => {
                        let Some(chunk) = next_chunk else {
                            break;
                        };

                        if chunk.samples.is_empty() {
                            continue;
                        }

                        {
                            let mut metrics = sender_runtime.metrics.lock().await;
                            metrics.record_audio_processing(chunk.processing_time_ms);
                        }

                        if detect_voice_activity(&chunk.samples) {
                            sender_runtime
                                .last_voice_activity_ms
                                .store(now_epoch_ms(), Ordering::Relaxed);
                        }

                        if ENABLE_SILENCE_SUPPRESSION && is_silent_chunk(&chunk.samples) {
                            silent_streak += 1;
                            if silent_streak > SILENCE_CHUNK_GRACE {
                                suppressed_silence_chunks += 1;
                                if suppressed_silence_chunks % SILENCE_SUPPRESS_LOG_EVERY == 0 {
                                    info!(
                                        suppressed_silence_chunks,
                                        "suppressing sustained silence chunks before network send"
                                    );
                                }
                                continue;
                            }
                        } else {
                            silent_streak = 0;
                        }

                        batch_samples.extend_from_slice(&chunk.samples);
                        batch_chunks += 1;
                        if batch_chunks >= MAX_AUDIO_BATCH_CHUNKS {
                            flush_audio_batch(&sender_client, &sender_runtime, &mut batch_samples, &mut batch_chunks).await;
                        }
                    }
                }
            }

            if batch_chunks > 0 {
                flush_audio_batch(&sender_client, &sender_runtime, &mut batch_samples, &mut batch_chunks).await;
            }

            if ENABLE_SILENCE_SUPPRESSION && suppressed_silence_chunks > 0 {
                info!(
                    suppressed_silence_chunks,
                    "recording session completed with sustained silence suppression"
                );
            }
        });

        loop {
            match stop_rx.try_recv() {
                Ok(()) => break,
                Err(std::sync::mpsc::TryRecvError::Disconnected) => break,
                Err(std::sync::mpsc::TryRecvError::Empty) => {
                    tokio::time::sleep(Duration::from_millis(25)).await;
                }
            }
        }

        if let Err(err) = capturer.stop() {
            warn!("failed to stop audio capturer: {err}");
        }
        tokio::time::sleep(Duration::from_millis(120)).await;

        if let Err(err) = client.flush().await {
            warn!("failed to flush network stream: {err}");
        }

        processing_task.abort();
        sender_task.abort();

        // Ensure the pooled websocket is torn down before this worker runtime exits.
        // Otherwise the next recording session can reuse a stale connection and fail
        // with "Tokio 1.x context ... is being shutdown" on first send.
        if let Err(err) = client.disconnect().await {
            warn!("failed to disconnect websocket client during worker shutdown: {err}");
        }

        let dropped = dropped_audio_counter.load(Ordering::Relaxed);
        if dropped > 0 {
            let mut metrics = runtime_state.metrics.lock().await;
            metrics.record_audio_drop(dropped);
        }
    });
}

async fn flush_audio_batch(
    client: &ScribeClient,
    runtime_state: &Arc<RuntimeState>,
    batch_samples: &mut Vec<i16>,
    batch_chunks: &mut usize,
) {
    if *batch_chunks == 0 {
        return;
    }

    let send_start = Instant::now();
    match client.send_audio_chunk(batch_samples.as_slice()).await {
        Ok(()) => {
            let send_ms = send_start.elapsed().as_millis() as u64;
            if send_ms >= SLOW_NETWORK_SEND_MS {
                warn!(
                    send_ms,
                    chunks = *batch_chunks,
                    samples = batch_samples.len(),
                    "network send is slower than expected"
                );
            }

            let mut metrics = runtime_state.metrics.lock().await;
            metrics.record_network_send(send_ms, *batch_chunks);
        }
        Err(err) => {
            warn!("failed to send audio batch: {err}");
        }
    }

    batch_samples.clear();
    *batch_chunks = 0;
}

fn is_silent_chunk(samples: &[i16]) -> bool {
    if samples.is_empty() {
        return true;
    }

    let peak = max_abs_sample(samples);
    if peak > SILENCE_PEAK_THRESHOLD_I16 {
        return false;
    }

    let threshold_sq = f64::from(SILENCE_RMS_THRESHOLD) * f64::from(SILENCE_RMS_THRESHOLD);
    mean_square_normalized(samples) <= threshold_sq
}

fn detect_voice_activity(samples: &[i16]) -> bool {
    if samples.is_empty() {
        return false;
    }

    if max_abs_sample(samples) >= VOICE_ACTIVITY_PEAK_THRESHOLD_I16 {
        return true;
    }

    let threshold_sq =
        f64::from(VOICE_ACTIVITY_RMS_THRESHOLD) * f64::from(VOICE_ACTIVITY_RMS_THRESHOLD);
    mean_square_normalized(samples) >= threshold_sq
}

fn mean_square_normalized(samples: &[i16]) -> f64 {
    if samples.is_empty() {
        return 0.0;
    }

    let scale = f64::from(i16::MAX);
    let mut sum_sq = 0.0_f64;
    for sample in samples {
        let normalized = f64::from(*sample) / scale;
        sum_sq += normalized * normalized;
    }

    sum_sq / samples.len() as f64
}

fn max_abs_sample(samples: &[i16]) -> i16 {
    let mut max = 0_i16;
    for sample in samples {
        let abs = if *sample == i16::MIN {
            i16::MAX
        } else {
            sample.abs()
        };
        if abs > max {
            max = abs;
        }
    }
    max
}

fn now_epoch_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or(0)
}

async fn get_or_create_client(
    runtime: &RuntimeState,
    api_key: String,
    language_code: String,
) -> Arc<ScribeClient> {
    let mut binding = runtime.client_binding.lock().await;

    if let Some(existing) = binding.as_ref() {
        if existing.api_key == api_key && existing.language_code == language_code {
            return Arc::clone(&existing.client);
        }
    }

    if let Some(old_binding) = binding.take() {
        let old_client = Arc::clone(&old_binding.client);
        tauri::async_runtime::spawn(async move {
            if let Err(err) = old_client.disconnect().await {
                warn!("failed to disconnect stale websocket client: {err}");
            }
        });
    }

    let client = Arc::new(ScribeClient::new(
        api_key.clone(),
        language_code.clone(),
        runtime.network_events.clone(),
    ));

    *binding = Some(ClientBinding {
        api_key,
        language_code,
        client: Arc::clone(&client),
    });

    client
}

async fn disconnect_cached_client(runtime: &RuntimeState) {
    let old_client = {
        let mut binding = runtime.client_binding.lock().await;
        binding.take().map(|value| Arc::clone(&value.client))
    };

    if let Some(client) = old_client {
        tauri::async_runtime::spawn(async move {
            if let Err(err) = client.disconnect().await {
                warn!("failed to disconnect websocket client after settings update: {err}");
            }
        });
    }
}

fn emit_state(app_handle: &AppHandle, state_label: &str) {
    if let Err(err) = app_handle.emit(RECORDING_STATE_EVENT, state_label.to_string()) {
        warn!("failed to emit recording state event: {err}");
    }
}

fn emit_error(app_handle: &AppHandle, message: &str) {
    error!("{message}");
    if let Err(err) = app_handle.emit(RECORDING_STATE_EVENT, "Error".to_string()) {
        warn!("failed to emit recording state event: {err}");
    }
    if let Err(err) = app_handle.emit(RECORDING_ERROR_EVENT, message.to_string()) {
        warn!("failed to emit recording error event: {err}");
    }
}

fn read_config(app_handle: &AppHandle) -> Result<AppSettings, String> {
    let config_path = config_path(app_handle)?;

    if !config_path.exists() {
        return Ok(AppSettings::default());
    }

    let content = fs::read_to_string(config_path).map_err(|err| err.to_string())?;
    serde_json::from_str::<AppSettings>(&content).map_err(|err| err.to_string())
}

fn write_config(app_handle: &AppHandle, config: &AppSettings) -> Result<(), String> {
    let config_path = config_path(app_handle)?;
    if let Some(parent) = config_path.parent() {
        fs::create_dir_all(parent).map_err(|err| err.to_string())?;
    }

    let serialized = serde_json::to_string_pretty(config).map_err(|err| err.to_string())?;
    fs::write(config_path, serialized).map_err(|err| err.to_string())
}

fn config_path(app_handle: &AppHandle) -> Result<std::path::PathBuf, String> {
    let config_dir = app_handle
        .path()
        .app_config_dir()
        .map_err(|err| err.to_string())?;
    Ok(config_dir.join("config.json"))
}

fn normalize_loaded_settings(mut settings: AppSettings) -> AppSettings {
    settings.api_key = settings.api_key.trim().to_string();
    settings.language_code = normalize_language_code(&settings.language_code);
    settings.hotkey = normalize_hotkey(&settings.hotkey);

    if !(MIN_PARTIAL_REWRITE_MAX_BACKSPACE..=MAX_PARTIAL_REWRITE_MAX_BACKSPACE)
        .contains(&settings.partial_rewrite_max_backspace)
    {
        warn!(
            max_backspace = settings.partial_rewrite_max_backspace,
            "loaded partial rewrite max backspace is out of range; resetting to default"
        );
        settings.partial_rewrite_max_backspace = DEFAULT_PARTIAL_REWRITE_MAX_BACKSPACE;
    }

    if !(MIN_PARTIAL_REWRITE_WINDOW_MS..=MAX_PARTIAL_REWRITE_WINDOW_MS)
        .contains(&settings.partial_rewrite_window_ms)
    {
        warn!(
            window_ms = settings.partial_rewrite_window_ms,
            "loaded partial rewrite window ms is out of range; resetting to default"
        );
        settings.partial_rewrite_window_ms = DEFAULT_PARTIAL_REWRITE_WINDOW_MS;
    }

    settings
}

fn validate_settings(mut settings: AppSettings) -> Result<AppSettings, String> {
    settings.api_key = settings.api_key.trim().to_string();
    settings.language_code = normalize_language_code(&settings.language_code);
    if !matches!(settings.language_code.as_str(), "eng" | "zho") {
        return Err(
            "languageCode must be one of: eng (English), zho (Simplified Chinese)".to_string(),
        );
    }

    let trimmed_hotkey = settings.hotkey.trim();
    if trimmed_hotkey.is_empty() {
        return Err("hotkey cannot be empty".to_string());
    }
    validate_hotkey(trimmed_hotkey)?;
    settings.hotkey = trimmed_hotkey.to_string();

    if !(MIN_PARTIAL_REWRITE_MAX_BACKSPACE..=MAX_PARTIAL_REWRITE_MAX_BACKSPACE)
        .contains(&settings.partial_rewrite_max_backspace)
    {
        return Err(format!(
            "partialRewriteMaxBackspace must be between {MIN_PARTIAL_REWRITE_MAX_BACKSPACE} and {MAX_PARTIAL_REWRITE_MAX_BACKSPACE}"
        ));
    }

    if !(MIN_PARTIAL_REWRITE_WINDOW_MS..=MAX_PARTIAL_REWRITE_WINDOW_MS)
        .contains(&settings.partial_rewrite_window_ms)
    {
        return Err(format!(
            "partialRewriteWindowMs must be between {MIN_PARTIAL_REWRITE_WINDOW_MS} and {MAX_PARTIAL_REWRITE_WINDOW_MS}"
        ));
    }

    Ok(settings)
}

fn normalize_language_code(language_code: &str) -> String {
    let normalized = language_code.trim().to_lowercase();
    match normalized.as_str() {
        "" => default_language_code(),
        "en" | "eng" | "english" => "eng".to_string(),
        "zh" | "zh-cn" | "zh-hans" | "zh-tw" | "zh-hant" | "cn" | "chinese" | "zho" => {
            "zho".to_string()
        }
        "auto" => default_language_code(),
        _ => normalized,
    }
}

fn normalize_hotkey(hotkey: &str) -> String {
    let trimmed = hotkey.trim();
    if trimmed.is_empty() {
        return default_hotkey();
    }

    if validate_hotkey(trimmed).is_ok() {
        return trimmed.to_string();
    }

    warn!("loaded hotkey is invalid; resetting to default hotkey");
    default_hotkey()
}

#[cfg(desktop)]
fn parse_shortcut(hotkey: &str) -> Result<tauri_plugin_global_shortcut::Shortcut, String> {
    hotkey
        .parse::<tauri_plugin_global_shortcut::Shortcut>()
        .map_err(|err| format!("invalid hotkey `{hotkey}`: {err}"))
}

#[cfg(not(desktop))]
fn parse_shortcut(_hotkey: &str) -> Result<(), String> {
    Ok(())
}

#[cfg(desktop)]
fn validate_hotkey(hotkey: &str) -> Result<(), String> {
    parse_shortcut(hotkey).map(|_| ())
}

#[cfg(not(desktop))]
fn validate_hotkey(_hotkey: &str) -> Result<(), String> {
    Ok(())
}

#[cfg(desktop)]
fn apply_hotkey_change(
    app_handle: &AppHandle,
    previous_hotkey: &str,
    next_hotkey: &str,
) -> Result<(), String> {
    use tauri_plugin_global_shortcut::GlobalShortcutExt;

    let manager = app_handle.global_shortcut();

    if let Ok(previous_shortcut) = parse_shortcut(previous_hotkey) {
        if manager.is_registered(previous_shortcut) {
            if let Err(err) = manager.unregister(previous_shortcut) {
                warn!("failed to unregister old hotkey `{previous_hotkey}`: {err}");
            }
        }
    }

    let next_shortcut = parse_shortcut(next_hotkey)?;
    if let Err(err) = manager.register(next_shortcut) {
        if let Ok(previous_shortcut) = parse_shortcut(previous_hotkey) {
            if let Err(restore_err) = manager.register(previous_shortcut) {
                warn!("failed to restore old hotkey `{previous_hotkey}`: {restore_err}");
            }
        }
        return Err(format!("failed to register hotkey `{next_hotkey}`: {err}"));
    }

    Ok(())
}

#[cfg(not(desktop))]
fn apply_hotkey_change(
    _app_handle: &AppHandle,
    _previous_hotkey: &str,
    _next_hotkey: &str,
) -> Result<(), String> {
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{
        SILENCE_PEAK_THRESHOLD_I16, VOICE_ACTIVITY_PEAK_THRESHOLD_I16, detect_voice_activity,
        is_silent_chunk, max_abs_sample, mean_square_normalized,
    };

    #[test]
    fn silence_detector_accepts_zero_chunk() {
        let input = vec![0_i16; 1600];
        assert!(is_silent_chunk(&input));
        assert_eq!(mean_square_normalized(&input), 0.0);
    }

    #[test]
    fn silence_detector_rejects_voice_like_chunk() {
        let mut input = Vec::with_capacity(1600);
        for i in 0..1600 {
            let phase = (i as f32) * 0.08;
            let sample = (phase.sin() * 6000.0) as i16;
            input.push(sample);
        }

        assert!(!is_silent_chunk(&input));
    }

    #[test]
    fn max_abs_handles_i16_min() {
        let input = vec![i16::MIN, -120, 80];
        assert_eq!(max_abs_sample(&input), i16::MAX);
        assert!(max_abs_sample(&input) > SILENCE_PEAK_THRESHOLD_I16);
    }

    #[test]
    fn voice_activity_detects_peak_signal() {
        let input = vec![0_i16, VOICE_ACTIVITY_PEAK_THRESHOLD_I16 + 20, 0_i16];
        assert!(detect_voice_activity(&input));
    }
}
