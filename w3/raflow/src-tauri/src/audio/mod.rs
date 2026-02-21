pub mod capturer;
mod denoiser;
pub mod resampler;

use std::sync::{
    Arc,
    atomic::{AtomicU64, Ordering},
};

use rtrb::Consumer;
use thiserror::Error;
use tokio::sync::mpsc;
use tokio::sync::mpsc::error::TrySendError;
use tokio::time::{Duration, sleep};
use tracing::{debug, warn};

use self::denoiser::AudioDenoiser;
pub use capturer::{AudioCapturer, AudioConfig};
pub use resampler::{AudioResampler, convert_f32_to_i16};

const BACKPRESSURE_WARN_EVERY: u64 = 50;

#[derive(Debug, Clone)]
pub struct ProcessedAudioChunk {
    pub samples: Vec<i16>,
    pub processing_time_ms: u64,
}

#[derive(Debug, Error)]
pub enum AudioError {
    #[error("invalid audio config: {0}")]
    InvalidConfig(String),
    #[error("no audio input device available")]
    NoInputDevice,
    #[error("failed to read default input config: {0}")]
    DefaultInputConfig(String),
    #[error("unsupported audio sample format: {0}")]
    UnsupportedSampleFormat(String),
    #[error("failed to build audio stream: {0}")]
    StreamBuild(String),
    #[error("audio stream is not initialized")]
    StreamNotInitialized,
    #[error("failed to start audio stream: {0}")]
    StreamStart(String),
    #[error("failed to stop audio stream: {0}")]
    StreamStop(String),
    #[error("ring buffer consumer has already been taken")]
    ConsumerAlreadyTaken,
    #[error("audio ring buffer is full and chunks are being dropped")]
    RingBufferFull,
    #[error("failed to create resampler: {0}")]
    ResamplerCreate(String),
    #[error("failed to process resampler chunk: {0}")]
    ResamplerProcess(String),
    #[error("invalid audio input: {0}")]
    InvalidInput(String),
    #[error("output channel receiver dropped")]
    OutputChannelClosed,
}

pub async fn audio_processing_task(
    mut consumer: Consumer<Vec<f32>>,
    tx: mpsc::Sender<ProcessedAudioChunk>,
    config: AudioConfig,
    dropped_counter: Arc<AtomicU64>,
) -> Result<(), AudioError> {
    let mut denoiser = AudioDenoiser::for_sample_rate(config.input_sample_rate);
    if denoiser.is_none() {
        warn!(
            input_sample_rate = config.input_sample_rate,
            "nnnoiseless denoiser bypassed because sample rate is not 48kHz"
        );
    }

    let mut resampler = AudioResampler::new(
        config.input_sample_rate,
        config.target_sample_rate,
        usize::from(config.channels),
    )?;

    let target_samples =
        (((config.input_sample_rate as usize) * (config.chunk_duration_ms as usize)) / 1000).max(1);
    let mut accumulator = Vec::with_capacity(target_samples * 2);

    loop {
        let mut consumed_any = false;

        while let Ok(chunk) = consumer.pop() {
            consumed_any = true;
            accumulator.extend_from_slice(&chunk);

            while accumulator.len() >= target_samples {
                let mut to_process: Vec<f32> = accumulator.drain(..target_samples).collect();
                if let Some(denoise) = denoiser.as_mut() {
                    denoise.process_chunk_in_place(&mut to_process);
                }
                let process_start = std::time::Instant::now();
                let resampled = resampler.process(&to_process)?;
                if !resampled.is_empty() {
                    let processing_time_ms = process_start.elapsed().as_millis() as u64;
                    debug!(
                        input_samples = target_samples,
                        output_samples = resampled.len(),
                        processing_time_ms,
                        "audio chunk processed"
                    );

                    let output = ProcessedAudioChunk {
                        samples: resampled,
                        processing_time_ms,
                    };

                    match tx.try_send(output) {
                        Ok(()) => {}
                        Err(TrySendError::Full(_)) => {
                            let dropped = dropped_counter.fetch_add(1, Ordering::Relaxed) + 1;
                            if dropped.is_multiple_of(BACKPRESSURE_WARN_EVERY) {
                                warn!(
                                    dropped_audio_chunks = dropped,
                                    "dropping processed chunks because sender is saturated"
                                );
                            }
                        }
                        Err(TrySendError::Closed(_)) => {
                            return Err(AudioError::OutputChannelClosed);
                        }
                    }
                }
            }
        }

        if !consumed_any {
            sleep(Duration::from_millis(10)).await;
        }

        if tx.is_closed() {
            warn!("audio pipeline sender closed");
            return Err(AudioError::OutputChannelClosed);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rtrb::RingBuffer;
    use std::sync::{Arc, atomic::AtomicU64};
    use tokio::time::timeout;

    #[tokio::test]
    async fn processing_task_emits_audio_frames() {
        let config = AudioConfig::default();
        let (mut producer, consumer) = RingBuffer::<Vec<f32>>::new(128);
        let (tx, mut rx) = mpsc::channel::<ProcessedAudioChunk>(8);
        let dropped_counter = Arc::new(AtomicU64::new(0));

        let input_chunk: Vec<f32> = (0..4800).map(|i| (i as f32 * 0.001).sin()).collect();

        assert!(producer.push(input_chunk.clone()).is_ok());
        assert!(producer.push(input_chunk).is_ok());

        let task_handle =
            tokio::spawn(audio_processing_task(consumer, tx, config, dropped_counter));

        let recv_result = timeout(Duration::from_millis(1200), rx.recv()).await;
        let has_data = matches!(recv_result, Ok(Some(chunk)) if !chunk.samples.is_empty());
        assert!(has_data);

        drop(rx);
        task_handle.abort();
    }
}
