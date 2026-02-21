use std::collections::VecDeque;
use std::time::{SystemTime, UNIX_EPOCH};

use serde::Serialize;

const DEFAULT_WINDOW_SIZE: usize = 256;
const E2E_P95_TARGET_MS: u64 = 500;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MetricSummary {
    pub samples: usize,
    pub average_ms: u64,
    pub p95_ms: u64,
    pub max_ms: u64,
}

impl MetricSummary {
    fn empty() -> Self {
        Self {
            samples: 0,
            average_ms: 0,
            p95_ms: 0,
            max_ms: 0,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PerformanceReport {
    pub generated_at_ms: u64,
    pub audio_processing: MetricSummary,
    pub network_send: MetricSummary,
    pub injection: MetricSummary,
    pub end_to_end: MetricSummary,
    pub dropped_audio_chunks: u64,
    pub dropped_committed_transcripts: u64,
    pub sent_audio_chunks: u64,
    pub sent_audio_batches: u64,
    pub warnings: Vec<String>,
}

#[derive(Debug)]
struct RollingMetric {
    values: VecDeque<u64>,
    capacity: usize,
}

impl RollingMetric {
    fn new(capacity: usize) -> Self {
        Self {
            values: VecDeque::with_capacity(capacity),
            capacity,
        }
    }

    fn record(&mut self, value_ms: u64) {
        if self.values.len() == self.capacity {
            self.values.pop_front();
        }
        self.values.push_back(value_ms);
    }

    fn summary(&self) -> MetricSummary {
        if self.values.is_empty() {
            return MetricSummary::empty();
        }

        let samples = self.values.len();
        let sum: u64 = self.values.iter().sum();
        let average_ms = sum / samples as u64;
        let max_ms = *self.values.iter().max().unwrap_or(&0);

        let mut sorted = self.values.iter().copied().collect::<Vec<_>>();
        sorted.sort_unstable();
        let p95_index = ((samples as f64 * 0.95).ceil() as usize)
            .saturating_sub(1)
            .min(samples - 1);
        let p95_ms = sorted[p95_index];

        MetricSummary {
            samples,
            average_ms,
            p95_ms,
            max_ms,
        }
    }
}

#[derive(Debug)]
pub struct RuntimeMetrics {
    audio_processing_ms: RollingMetric,
    network_send_ms: RollingMetric,
    injection_ms: RollingMetric,
    end_to_end_ms: RollingMetric,
    dropped_audio_chunks: u64,
    dropped_committed_transcripts: u64,
    sent_audio_chunks: u64,
    sent_audio_batches: u64,
}

impl RuntimeMetrics {
    pub fn new() -> Self {
        Self {
            audio_processing_ms: RollingMetric::new(DEFAULT_WINDOW_SIZE),
            network_send_ms: RollingMetric::new(DEFAULT_WINDOW_SIZE),
            injection_ms: RollingMetric::new(DEFAULT_WINDOW_SIZE),
            end_to_end_ms: RollingMetric::new(DEFAULT_WINDOW_SIZE),
            dropped_audio_chunks: 0,
            dropped_committed_transcripts: 0,
            sent_audio_chunks: 0,
            sent_audio_batches: 0,
        }
    }

    pub fn record_audio_processing(&mut self, processing_ms: u64) {
        self.audio_processing_ms.record(processing_ms);
    }

    pub fn record_network_send(&mut self, send_ms: u64, chunk_count: usize) {
        self.network_send_ms.record(send_ms);
        self.sent_audio_batches += 1;
        self.sent_audio_chunks += chunk_count as u64;
    }

    pub fn record_injection(&mut self, injection_ms: u64) {
        self.injection_ms.record(injection_ms);
    }

    pub fn record_end_to_end(&mut self, latency_ms: u64) {
        self.end_to_end_ms.record(latency_ms);
    }

    pub fn record_audio_drop(&mut self, count: u64) {
        self.dropped_audio_chunks += count;
    }

    pub fn record_committed_drop(&mut self, count: u64) {
        self.dropped_committed_transcripts += count;
    }

    pub fn report(&self) -> PerformanceReport {
        let audio_processing = self.audio_processing_ms.summary();
        let network_send = self.network_send_ms.summary();
        let injection = self.injection_ms.summary();
        let end_to_end = self.end_to_end_ms.summary();

        let mut warnings = Vec::new();
        if self.dropped_audio_chunks > 0 {
            warnings.push(format!(
                "Dropped {} audio chunks due to backpressure.",
                self.dropped_audio_chunks
            ));
        }
        if self.dropped_committed_transcripts > 0 {
            warnings.push(format!(
                "Dropped {} committed transcripts because queue was full.",
                self.dropped_committed_transcripts
            ));
        }
        if end_to_end.samples > 0 && end_to_end.p95_ms > E2E_P95_TARGET_MS {
            warnings.push(format!(
                "End-to-end P95 latency {}ms exceeded target {}ms.",
                end_to_end.p95_ms, E2E_P95_TARGET_MS
            ));
        }

        PerformanceReport {
            generated_at_ms: now_epoch_ms(),
            audio_processing,
            network_send,
            injection,
            end_to_end,
            dropped_audio_chunks: self.dropped_audio_chunks,
            dropped_committed_transcripts: self.dropped_committed_transcripts,
            sent_audio_chunks: self.sent_audio_chunks,
            sent_audio_batches: self.sent_audio_batches,
            warnings,
        }
    }
}

impl Default for RuntimeMetrics {
    fn default() -> Self {
        Self::new()
    }
}

fn now_epoch_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or(0)
}
