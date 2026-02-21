use std::time::{Duration, Instant};

use base64::Engine;
use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tauri::async_runtime::JoinHandle;
use thiserror::Error;
use tokio::net::TcpStream;
use tokio::sync::{Mutex, broadcast};
use tokio_tungstenite::tungstenite::client::IntoClientRequest;
use tokio_tungstenite::tungstenite::{self, Message};
use tokio_tungstenite::{MaybeTlsStream, WebSocketStream, connect_async};
use tracing::{debug, info, warn};

type WsStream = WebSocketStream<MaybeTlsStream<TcpStream>>;
type WsWriter = futures_util::stream::SplitSink<WsStream, Message>;

const DEFAULT_WS_URL: &str = "wss://api.elevenlabs.io/v1/speech-to-text/realtime";
const DEFAULT_MODEL_ID: &str = "scribe_v2_realtime";
const DEFAULT_AUDIO_FORMAT: &str = "pcm_16000";
const DEFAULT_SAMPLE_RATE: u32 = 16_000;
const DEFAULT_COMMIT_STRATEGY: &str = "vad";
const DEFAULT_IDLE_TIMEOUT_SECONDS: u64 = 30;
const DEFAULT_RECONNECT_ATTEMPTS: u8 = 2;
const DEFAULT_VAD_THRESHOLD: f32 = 0.6;
const DEFAULT_MIN_SPEECH_DURATION_MS: u16 = 180;
const DEFAULT_MAX_BUFFER_DELAY_MS: u16 = 1000;

#[derive(Debug, Error)]
pub enum NetworkError {
    #[error("api key is not configured")]
    MissingApiKey,
    #[error("failed to build websocket request: {0}")]
    RequestBuild(String),
    #[error("invalid api key header: {0}")]
    InvalidHeaderValue(String),
    #[error("failed to connect websocket: {0}")]
    ConnectFailed(String),
    #[error("failed to serialize websocket payload: {0}")]
    Serialize(String),
    #[error("failed to send websocket payload: {0}")]
    WebSocketSend(String),
    #[error("failed to close websocket connection: {0}")]
    WebSocketClose(String),
}

#[derive(Debug, Clone, Serialize)]
pub struct InputAudioChunk {
    pub message_type: &'static str,
    pub audio_base_64: String,
    pub sample_rate: u32,
}

impl InputAudioChunk {
    fn from_pcm_samples(samples: &[i16]) -> Self {
        let audio_base_64 = encode_pcm_base64(samples);
        Self {
            message_type: "input_audio_chunk",
            audio_base_64,
            sample_rate: DEFAULT_SAMPLE_RATE,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct FlushMessage {
    pub message_type: &'static str,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "message_type")]
pub enum ScribeEvent {
    #[serde(rename = "session_started")]
    SessionStarted {
        session_id: String,
        #[serde(default)]
        config: serde_json::Value,
    },
    #[serde(rename = "partial_transcript")]
    PartialTranscript {
        text: String,
        #[serde(default)]
        created_at_ms: u64,
    },
    #[serde(rename = "committed_transcript")]
    CommittedTranscript {
        text: String,
        #[serde(default)]
        confidence: f32,
        #[serde(default)]
        created_at_ms: u64,
    },
    #[serde(rename = "input_error")]
    InputError { error_message: String },
    #[serde(rename = "error")]
    Error {
        #[serde(default)]
        error_message: String,
        #[serde(default)]
        error: String,
    },
    #[serde(rename = "auth_error")]
    AuthError {
        #[serde(default)]
        error_message: String,
        #[serde(default)]
        error: String,
    },
    #[serde(other)]
    Unknown,
}

#[derive(Debug, Clone)]
pub enum NetworkEvent {
    Scribe(ScribeEvent),
    TransportError(String),
}

pub struct ScribeClient {
    api_key: String,
    model_id: String,
    language_code: String,
    ws_url: String,
    reconnect_attempts: u8,
    pool: Mutex<ConnectionPool>,
    event_tx: broadcast::Sender<NetworkEvent>,
}

struct ConnectionPool {
    connection: Option<ManagedConnection>,
    last_used: Instant,
    idle_timeout: Duration,
}

struct ManagedConnection {
    writer: Mutex<WsWriter>,
    reader_task: JoinHandle<()>,
}

impl ManagedConnection {
    async fn shutdown(self) -> Result<(), NetworkError> {
        let mut writer = self.writer.lock().await;
        let close_result = writer.send(Message::Close(None)).await;
        drop(writer);
        self.reader_task.abort();

        match close_result {
            Ok(()) => Ok(()),
            Err(err) if is_expected_close_error(&err) => Ok(()),
            Err(err) => Err(NetworkError::WebSocketClose(err.to_string())),
        }
    }
}

impl ScribeClient {
    pub fn new(
        api_key: String,
        language_code: String,
        event_tx: broadcast::Sender<NetworkEvent>,
    ) -> Self {
        let idle_timeout = Duration::from_secs(DEFAULT_IDLE_TIMEOUT_SECONDS);
        Self {
            api_key,
            model_id: DEFAULT_MODEL_ID.to_string(),
            language_code,
            ws_url: DEFAULT_WS_URL.to_string(),
            reconnect_attempts: DEFAULT_RECONNECT_ATTEMPTS,
            pool: Mutex::new(ConnectionPool {
                connection: None,
                last_used: Instant::now(),
                idle_timeout,
            }),
            event_tx,
        }
    }

    pub async fn ensure_connected(&self) -> Result<(), NetworkError> {
        self.ensure_connection().await.map(|_| ())
    }

    pub async fn send_audio_chunk(&self, samples: &[i16]) -> Result<(), NetworkError> {
        if samples.is_empty() {
            return Ok(());
        }

        let payload = InputAudioChunk::from_pcm_samples(samples);
        self.send_payload(&payload).await
    }

    pub async fn flush(&self) -> Result<(), NetworkError> {
        // Keep compatibility with existing call sites; close/commit semantics are server-managed.
        // We intentionally do not send a custom "flush" message because the STT API expects
        // input_audio_chunk payloads and may reject unknown message types.
        Ok(())
    }

    pub async fn disconnect(&self) -> Result<(), NetworkError> {
        self.invalidate_connection().await
    }

    async fn send_payload<T>(&self, payload: &T) -> Result<(), NetworkError>
    where
        T: Serialize,
    {
        let serialized = serde_json::to_string(payload)
            .map_err(|err| NetworkError::Serialize(err.to_string()))?;
        self.send_text_with_reconnect(serialized).await
    }

    async fn send_text_with_reconnect(&self, message: String) -> Result<(), NetworkError> {
        let mut attempts_remaining = 1_u8;
        loop {
            self.ensure_connection().await?;

            let send_result = {
                let mut pool = self.pool.lock().await;
                pool.last_used = Instant::now();

                if let Some(connection) = pool.connection.as_mut() {
                    let mut writer = connection.writer.lock().await;
                    writer.send(Message::Text(message.clone().into())).await
                } else {
                    unreachable!("connection must exist after ensure_connection")
                }
            };

            match send_result {
                Ok(()) => return Ok(()),
                Err(err) => {
                    warn!("websocket send failed, invalidating connection: {err}");
                    if let Err(close_err) = self.invalidate_connection().await {
                        warn!("failed to invalidate websocket after send failure: {close_err}");
                    }
                    if attempts_remaining == 0 {
                        return Err(NetworkError::WebSocketSend(err.to_string()));
                    }
                    attempts_remaining -= 1;
                }
            }
        }
    }

    async fn ensure_connection(&self) -> Result<(), NetworkError> {
        if self.api_key.trim().is_empty() {
            return Err(NetworkError::MissingApiKey);
        }

        let mut maybe_stale = None;

        {
            let mut pool = self.pool.lock().await;
            if pool.last_used.elapsed() > pool.idle_timeout {
                maybe_stale = pool.connection.take();
            }
        }

        if let Some(stale) = maybe_stale {
            let _ = stale.shutdown().await;
        }

        let mut pool = self.pool.lock().await;
        if pool.connection.is_none() {
            let connection = self.connect_with_retry().await?;
            pool.connection = Some(connection);
            info!("websocket connection created");
        }
        pool.last_used = Instant::now();
        Ok(())
    }

    async fn connect_with_retry(&self) -> Result<ManagedConnection, NetworkError> {
        let mut last_error = None;
        for attempt in 0..=self.reconnect_attempts {
            match self.connect_once().await {
                Ok(connection) => return Ok(connection),
                Err(err) => {
                    last_error = Some(err.to_string());
                    let _ = self.event_tx.send(NetworkEvent::TransportError(format!(
                        "connection attempt {} failed: {}",
                        attempt + 1,
                        err
                    )));
                    if attempt < self.reconnect_attempts {
                        tokio::time::sleep(Duration::from_millis(250)).await;
                    }
                }
            }
        }

        Err(NetworkError::ConnectFailed(
            last_error.unwrap_or_else(|| "unknown error".to_string()),
        ))
    }

    async fn connect_once(&self) -> Result<ManagedConnection, NetworkError> {
        let mut query = vec![
            format!("model_id={}", self.model_id),
            format!("audio_format={}", DEFAULT_AUDIO_FORMAT),
            format!("commit_strategy={}", DEFAULT_COMMIT_STRATEGY),
            format!("vad_threshold={DEFAULT_VAD_THRESHOLD}"),
            format!("min_speech_duration_ms={DEFAULT_MIN_SPEECH_DURATION_MS}"),
            format!("max_buffer_delay_ms={DEFAULT_MAX_BUFFER_DELAY_MS}"),
        ];
        if !self.language_code.trim().is_empty() {
            query.push(format!("language_code={}", self.language_code));
        }
        let url = format!("{}?{}", self.ws_url, query.join("&"));

        let mut request = url
            .into_client_request()
            .map_err(|err| NetworkError::RequestBuild(err.to_string()))?;
        let api_key_header = self.api_key.parse().map_err(
            |err: tungstenite::http::header::InvalidHeaderValue| {
                NetworkError::InvalidHeaderValue(err.to_string())
            },
        )?;
        request.headers_mut().insert("xi-api-key", api_key_header);

        let (ws_stream, _) = connect_async(request)
            .await
            .map_err(|err| NetworkError::ConnectFailed(err.to_string()))?;
        let (writer, mut reader) = ws_stream.split();
        let event_tx = self.event_tx.clone();

        let reader_task = tauri::async_runtime::spawn(async move {
            loop {
                match reader.next().await {
                    Some(Ok(Message::Text(text))) => {
                        match serde_json::from_str::<ScribeEvent>(text.as_ref()) {
                            Ok(event) => {
                                if matches!(event, ScribeEvent::Unknown) {
                                    if let Some(extracted) =
                                        extract_scribe_error_message(text.as_ref())
                                    {
                                        let _ = event_tx.send(NetworkEvent::TransportError(
                                            format!("scribe error: {extracted}"),
                                        ));
                                    } else {
                                        warn!("received unknown scribe event payload: {}", text);
                                    }
                                } else {
                                    let _ = event_tx.send(NetworkEvent::Scribe(event));
                                }
                            }
                            Err(err) => {
                                if let Some(extracted) = extract_scribe_error_message(text.as_ref())
                                {
                                    let _ = event_tx.send(NetworkEvent::TransportError(format!(
                                        "scribe parse fallback: {extracted}"
                                    )));
                                } else {
                                    warn!("failed to parse scribe event: {err}; payload={}", text);
                                }
                            }
                        }
                    }
                    Some(Ok(Message::Binary(_))) => {
                        debug!("ignored websocket binary payload");
                    }
                    Some(Ok(Message::Ping(_))) | Some(Ok(Message::Pong(_))) => {}
                    Some(Ok(Message::Close(frame))) => {
                        let raw_reason = frame
                            .as_ref()
                            .map(|close| close.reason.to_string())
                            .unwrap_or_default();
                        let reason = if raw_reason.trim().is_empty() {
                            "remote closed".to_string()
                        } else {
                            raw_reason
                        };
                        let _ = event_tx.send(NetworkEvent::TransportError(format!(
                            "websocket closed: {reason}"
                        )));
                        break;
                    }
                    Some(Ok(Message::Frame(_))) => {}
                    Some(Err(err)) => {
                        let _ = event_tx.send(NetworkEvent::TransportError(format!(
                            "websocket receive error: {err}"
                        )));
                        break;
                    }
                    None => {
                        let _ = event_tx.send(NetworkEvent::TransportError(
                            "websocket stream ended".to_string(),
                        ));
                        break;
                    }
                }
            }
        });

        Ok(ManagedConnection {
            writer: Mutex::new(writer),
            reader_task,
        })
    }

    async fn invalidate_connection(&self) -> Result<(), NetworkError> {
        let maybe_connection = {
            let mut pool = self.pool.lock().await;
            pool.connection.take()
        };

        if let Some(connection) = maybe_connection {
            if let Err(err) = connection.shutdown().await {
                warn!("failed to shutdown websocket connection: {err}");
            }
        }

        Ok(())
    }
}

fn encode_pcm_base64(samples: &[i16]) -> String {
    let mut pcm_bytes = Vec::with_capacity(samples.len() * 2);
    for sample in samples {
        pcm_bytes.extend_from_slice(&sample.to_le_bytes());
    }
    base64::engine::general_purpose::STANDARD.encode(pcm_bytes)
}

fn extract_scribe_error_message(payload: &str) -> Option<String> {
    let value = serde_json::from_str::<Value>(payload).ok()?;
    let message_type = value
        .get("message_type")
        .and_then(|item| item.as_str())
        .unwrap_or("unknown");
    let error_message = value
        .get("error_message")
        .and_then(|item| item.as_str())
        .or_else(|| value.get("error").and_then(|item| item.as_str()))
        .unwrap_or("");

    if !error_message.is_empty() {
        Some(format!("{message_type}: {error_message}"))
    } else if message_type != "unknown" {
        Some(format!("{message_type}: {payload}"))
    } else {
        None
    }
}

fn is_expected_close_error(err: &tungstenite::Error) -> bool {
    matches!(
        err,
        tungstenite::Error::AlreadyClosed | tungstenite::Error::ConnectionClosed
    ) || err
        .to_string()
        .contains("Sending after closing is not allowed")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn input_chunk_serialization_contains_message_type() {
        let payload = InputAudioChunk::from_pcm_samples(&[1, -2, 32767]);
        let serialized = serde_json::to_string(&payload).expect("payload should serialize");

        assert!(serialized.contains("\"message_type\":\"input_audio_chunk\""));
        assert!(serialized.contains("\"audio_base_64\""));
        assert!(serialized.contains("\"sample_rate\":16000"));
    }

    #[test]
    fn scribe_event_deserialization_supports_transcript_variants() {
        let partial = r#"{"message_type":"partial_transcript","text":"hello","created_at_ms":123}"#;
        let committed = r#"{"message_type":"committed_transcript","text":"world","confidence":0.97,"created_at_ms":456}"#;

        let parsed_partial: ScribeEvent =
            serde_json::from_str(partial).expect("partial event should parse");
        let parsed_committed: ScribeEvent =
            serde_json::from_str(committed).expect("committed event should parse");

        assert!(matches!(
            parsed_partial,
            ScribeEvent::PartialTranscript { text, .. } if text == "hello"
        ));
        assert!(matches!(
            parsed_committed,
            ScribeEvent::CommittedTranscript {
                text,
                confidence,
                ..
            } if text == "world" && confidence > 0.9
        ));
    }

    #[test]
    fn pcm_encoding_is_little_endian() {
        let encoded = encode_pcm_base64(&[0x0102, -2]);
        let decoded = base64::engine::general_purpose::STANDARD
            .decode(encoded)
            .expect("base64 decode should succeed");

        assert_eq!(decoded, vec![0x02, 0x01, 0xFE, 0xFF]);
    }

    #[test]
    fn extract_scribe_error_from_unknown_payload() {
        let payload = r#"{"message_type":"invalid_request","error_message":"bad field"}"#;
        let extracted = extract_scribe_error_message(payload).expect("expected extracted message");
        assert!(extracted.contains("invalid_request"));
        assert!(extracted.contains("bad field"));
    }
}
