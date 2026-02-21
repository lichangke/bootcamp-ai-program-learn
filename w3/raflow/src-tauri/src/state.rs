use std::collections::VecDeque;
use std::sync::Arc;
use std::sync::atomic::AtomicU64;
use std::thread::JoinHandle;

use serde::Serialize;
use tokio::sync::{Mutex, Notify, broadcast};

use crate::input::{
    DEFAULT_PARTIAL_REWRITE_ENABLED, DEFAULT_PARTIAL_REWRITE_MAX_BACKSPACE,
    DEFAULT_PARTIAL_REWRITE_WINDOW_MS,
};
use crate::metrics::RuntimeMetrics;
use crate::network::{NetworkEvent, ScribeClient};

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CommittedTranscript {
    pub text: String,
    pub confidence: f32,
    pub created_at_ms: u64,
}

pub struct RecordingSession {
    pub stop_tx: std::sync::mpsc::Sender<()>,
    pub worker_handle: JoinHandle<()>,
}

pub struct ClientBinding {
    pub api_key: String,
    pub language_code: String,
    pub client: Arc<ScribeClient>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum TranscriptInjectionMode {
    #[default]
    Undetermined,
    RealtimeCursor,
    ClipboardOnly,
}

#[derive(Default)]
pub struct LivePartialTracker {
    pub injected_text: String,
    pub disabled_until_commit: bool,
    pub mode: TranscriptInjectionMode,
    pub pending_clipboard_text: String,
    pub last_rewrite_at_ms: u64,
}

impl LivePartialTracker {
    pub fn reset_for_session(&mut self) {
        self.injected_text.clear();
        self.disabled_until_commit = false;
        self.mode = TranscriptInjectionMode::Undetermined;
        self.last_rewrite_at_ms = 0;
    }

    pub fn reset_after_commit(&mut self) {
        self.injected_text.clear();
        self.disabled_until_commit = false;
        self.last_rewrite_at_ms = 0;
    }
}

pub struct RuntimeState {
    pub is_recording: Mutex<bool>,
    pub current_hotkey: Mutex<String>,
    pub partial_rewrite_enabled: Mutex<bool>,
    pub partial_rewrite_max_backspace: Mutex<usize>,
    pub partial_rewrite_window_ms: Mutex<u64>,
    pub overlay_visible: Mutex<bool>,
    pub session: Mutex<Option<RecordingSession>>,
    pub client_binding: Mutex<Option<ClientBinding>>,
    pub live_partial_tracker: Mutex<LivePartialTracker>,
    pub last_voice_activity_ms: AtomicU64,
    pub committed_queue: Mutex<VecDeque<CommittedTranscript>>,
    pub injection_notify: Arc<Notify>,
    pub network_events: broadcast::Sender<NetworkEvent>,
    pub metrics: Mutex<RuntimeMetrics>,
}

#[derive(Clone)]
pub struct AppState {
    runtime: Arc<RuntimeState>,
}

impl AppState {
    pub fn new() -> Self {
        let (network_events, _) = broadcast::channel(256);
        let runtime = RuntimeState {
            is_recording: Mutex::new(false),
            current_hotkey: Mutex::new("Ctrl+N".to_string()),
            partial_rewrite_enabled: Mutex::new(DEFAULT_PARTIAL_REWRITE_ENABLED),
            partial_rewrite_max_backspace: Mutex::new(DEFAULT_PARTIAL_REWRITE_MAX_BACKSPACE),
            partial_rewrite_window_ms: Mutex::new(DEFAULT_PARTIAL_REWRITE_WINDOW_MS),
            overlay_visible: Mutex::new(true),
            session: Mutex::new(None),
            client_binding: Mutex::new(None),
            live_partial_tracker: Mutex::new(LivePartialTracker::default()),
            last_voice_activity_ms: AtomicU64::new(0),
            committed_queue: Mutex::new(VecDeque::new()),
            injection_notify: Arc::new(Notify::new()),
            network_events,
            metrics: Mutex::new(RuntimeMetrics::new()),
        };
        Self {
            runtime: Arc::new(runtime),
        }
    }

    pub fn runtime(&self) -> Arc<RuntimeState> {
        Arc::clone(&self.runtime)
    }
}
