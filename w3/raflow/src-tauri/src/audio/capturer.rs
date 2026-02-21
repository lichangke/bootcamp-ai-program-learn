use std::sync::{
    Arc,
    atomic::{AtomicUsize, Ordering},
};

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{SampleFormat, Stream, StreamConfig};
use rtrb::{Consumer, Producer, RingBuffer};
use tracing::{debug, warn};

use super::AudioError;

#[derive(Debug, Clone)]
pub struct AudioConfig {
    pub input_sample_rate: u32,
    pub target_sample_rate: u32,
    pub channels: u16,
    pub buffer_size: u32,
    pub chunk_duration_ms: u32,
}

impl Default for AudioConfig {
    fn default() -> Self {
        Self {
            input_sample_rate: 48_000,
            target_sample_rate: 16_000,
            channels: 1,
            buffer_size: 480,
            chunk_duration_ms: 100,
        }
    }
}

pub struct AudioCapturer {
    pub config: AudioConfig,
    stream: Option<Stream>,
    consumer: Option<Consumer<Vec<f32>>>,
    dropped_chunks: Arc<AtomicUsize>,
    pub device_name: String,
}

impl AudioCapturer {
    pub fn new(mut config: AudioConfig) -> Result<Self, AudioError> {
        if config.channels == 0 {
            return Err(AudioError::InvalidConfig(
                "channels must be greater than 0".to_string(),
            ));
        }
        if config.channels != 1 {
            return Err(AudioError::InvalidConfig(
                "phase 1 only supports mono output".to_string(),
            ));
        }
        if config.buffer_size == 0 {
            return Err(AudioError::InvalidConfig(
                "buffer_size must be greater than 0".to_string(),
            ));
        }

        let host = cpal::default_host();
        let device = host
            .default_input_device()
            .ok_or(AudioError::NoInputDevice)?;

        let device_name = match device.name() {
            Ok(name) => name,
            Err(_) => "unknown-input-device".to_string(),
        };

        let supported_config = device
            .default_input_config()
            .map_err(|err| AudioError::DefaultInputConfig(err.to_string()))?;
        let sample_format = supported_config.sample_format();
        let stream_config: StreamConfig = supported_config.into();
        config.input_sample_rate = stream_config.sample_rate.0;

        let ring_capacity =
            ((config.input_sample_rate as usize / config.buffer_size as usize) * 2).max(64);
        let (producer, consumer) = RingBuffer::<Vec<f32>>::new(ring_capacity);
        let dropped_chunks = Arc::new(AtomicUsize::new(0));

        let input_channels = usize::from(stream_config.channels);
        let stream = match sample_format {
            SampleFormat::F32 => build_stream_f32(
                &device,
                &stream_config,
                input_channels,
                producer,
                Arc::clone(&dropped_chunks),
            )?,
            SampleFormat::I16 => build_stream_i16(
                &device,
                &stream_config,
                input_channels,
                producer,
                Arc::clone(&dropped_chunks),
            )?,
            SampleFormat::U16 => build_stream_u16(
                &device,
                &stream_config,
                input_channels,
                producer,
                Arc::clone(&dropped_chunks),
            )?,
            other => {
                return Err(AudioError::UnsupportedSampleFormat(format!("{other:?}")));
            }
        };

        debug!(
            device_name = device_name.as_str(),
            input_sample_rate = config.input_sample_rate,
            target_sample_rate = config.target_sample_rate,
            "audio capturer initialized"
        );

        Ok(Self {
            config,
            stream: Some(stream),
            consumer: Some(consumer),
            dropped_chunks,
            device_name,
        })
    }

    pub fn take_consumer(&mut self) -> Result<Consumer<Vec<f32>>, AudioError> {
        self.consumer.take().ok_or(AudioError::ConsumerAlreadyTaken)
    }

    pub fn start(&self) -> Result<(), AudioError> {
        match &self.stream {
            Some(stream) => stream
                .play()
                .map_err(|err| AudioError::StreamStart(err.to_string())),
            None => Err(AudioError::StreamNotInitialized),
        }
    }

    pub fn stop(&self) -> Result<(), AudioError> {
        match &self.stream {
            Some(stream) => stream
                .pause()
                .map_err(|err| AudioError::StreamStop(err.to_string())),
            None => Err(AudioError::StreamNotInitialized),
        }
    }

    pub fn dropped_chunk_count(&self) -> usize {
        self.dropped_chunks.load(Ordering::Relaxed)
    }

    pub fn ensure_no_overflow(&self) -> Result<(), AudioError> {
        if self.dropped_chunk_count() > 0 {
            return Err(AudioError::RingBufferFull);
        }
        Ok(())
    }
}

fn build_stream_f32(
    device: &cpal::Device,
    stream_config: &StreamConfig,
    input_channels: usize,
    mut producer: Producer<Vec<f32>>,
    dropped_chunks: Arc<AtomicUsize>,
) -> Result<Stream, AudioError> {
    let dropped_for_error = Arc::clone(&dropped_chunks);
    device
        .build_input_stream(
            stream_config,
            move |data: &[f32], _| {
                let mono_chunk = interleaved_f32_to_mono(data, input_channels);
                if producer.push(mono_chunk).is_err() {
                    mark_dropped(&dropped_chunks);
                }
            },
            move |err| {
                warn!("audio stream callback error: {err}");
                mark_dropped(&dropped_for_error);
            },
            None,
        )
        .map_err(|err| AudioError::StreamBuild(err.to_string()))
}

fn build_stream_i16(
    device: &cpal::Device,
    stream_config: &StreamConfig,
    input_channels: usize,
    mut producer: Producer<Vec<f32>>,
    dropped_chunks: Arc<AtomicUsize>,
) -> Result<Stream, AudioError> {
    let dropped_for_error = Arc::clone(&dropped_chunks);
    device
        .build_input_stream(
            stream_config,
            move |data: &[i16], _| {
                let mono_chunk = interleaved_i16_to_mono(data, input_channels);
                if producer.push(mono_chunk).is_err() {
                    mark_dropped(&dropped_chunks);
                }
            },
            move |err| {
                warn!("audio stream callback error: {err}");
                mark_dropped(&dropped_for_error);
            },
            None,
        )
        .map_err(|err| AudioError::StreamBuild(err.to_string()))
}

fn build_stream_u16(
    device: &cpal::Device,
    stream_config: &StreamConfig,
    input_channels: usize,
    mut producer: Producer<Vec<f32>>,
    dropped_chunks: Arc<AtomicUsize>,
) -> Result<Stream, AudioError> {
    let dropped_for_error = Arc::clone(&dropped_chunks);
    device
        .build_input_stream(
            stream_config,
            move |data: &[u16], _| {
                let mono_chunk = interleaved_u16_to_mono(data, input_channels);
                if producer.push(mono_chunk).is_err() {
                    mark_dropped(&dropped_chunks);
                }
            },
            move |err| {
                warn!("audio stream callback error: {err}");
                mark_dropped(&dropped_for_error);
            },
            None,
        )
        .map_err(|err| AudioError::StreamBuild(err.to_string()))
}

fn interleaved_f32_to_mono(data: &[f32], input_channels: usize) -> Vec<f32> {
    if input_channels <= 1 {
        return data.to_vec();
    }

    let mut mono = Vec::with_capacity(data.len() / input_channels);
    for frame in data.chunks_exact(input_channels) {
        let sum: f32 = frame.iter().copied().sum();
        mono.push(sum / input_channels as f32);
    }
    mono
}

fn interleaved_i16_to_mono(data: &[i16], input_channels: usize) -> Vec<f32> {
    if input_channels <= 1 {
        return data
            .iter()
            .map(|sample| *sample as f32 / i16::MAX as f32)
            .collect();
    }

    let mut mono = Vec::with_capacity(data.len() / input_channels);
    for frame in data.chunks_exact(input_channels) {
        let mut sum = 0.0_f32;
        for sample in frame {
            sum += *sample as f32 / i16::MAX as f32;
        }
        mono.push(sum / input_channels as f32);
    }
    mono
}

fn interleaved_u16_to_mono(data: &[u16], input_channels: usize) -> Vec<f32> {
    if input_channels <= 1 {
        return data
            .iter()
            .map(|sample| (*sample as f32 / u16::MAX as f32) * 2.0 - 1.0)
            .collect();
    }

    let mut mono = Vec::with_capacity(data.len() / input_channels);
    for frame in data.chunks_exact(input_channels) {
        let mut sum = 0.0_f32;
        for sample in frame {
            sum += (*sample as f32 / u16::MAX as f32) * 2.0 - 1.0;
        }
        mono.push(sum / input_channels as f32);
    }
    mono
}

fn mark_dropped(counter: &AtomicUsize) {
    let total = counter.fetch_add(1, Ordering::Relaxed) + 1;
    if total.is_multiple_of(100) {
        warn!(
            dropped_chunks = total,
            "audio chunks dropped due to ring buffer pressure"
        );
    }
}
