use rubato::{
    Resampler, SincFixedIn, SincInterpolationParameters, SincInterpolationType, WindowFunction,
};

use super::AudioError;

pub struct AudioResampler {
    resampler: SincFixedIn<f32>,
    input_buffer: Vec<Vec<f32>>,
    input_frames_needed: usize,
    channels: usize,
}

impl AudioResampler {
    pub fn new(from_rate: u32, to_rate: u32, channels: usize) -> Result<Self, AudioError> {
        if from_rate == 0 || to_rate == 0 {
            return Err(AudioError::InvalidConfig(
                "sample rates must be greater than 0".to_string(),
            ));
        }
        if channels == 0 {
            return Err(AudioError::InvalidConfig(
                "channels must be greater than 0".to_string(),
            ));
        }

        let params = SincInterpolationParameters {
            sinc_len: 256,
            f_cutoff: 0.95,
            interpolation: SincInterpolationType::Linear,
            oversampling_factor: 256,
            window: WindowFunction::BlackmanHarris2,
        };

        let resample_ratio = to_rate as f64 / from_rate as f64;
        let chunk_size = ((from_rate as f64) * 0.1) as usize;

        let resampler = SincFixedIn::<f32>::new(resample_ratio, 2.0, params, chunk_size, channels)
            .map_err(|err| AudioError::ResamplerCreate(err.to_string()))?;

        let input_frames_needed = resampler.input_frames_next();
        let input_buffer = vec![Vec::with_capacity(chunk_size * 2); channels];
        Ok(Self {
            resampler,
            input_buffer,
            input_frames_needed,
            channels,
        })
    }

    pub fn process(&mut self, input: &[f32]) -> Result<Vec<i16>, AudioError> {
        if input.is_empty() {
            return Ok(Vec::new());
        }
        if input.len() % self.channels != 0 {
            return Err(AudioError::InvalidInput(
                "input sample count must match channel layout".to_string(),
            ));
        }

        for frame in input.chunks_exact(self.channels) {
            for (channel_idx, sample) in frame.iter().enumerate() {
                self.input_buffer[channel_idx].push(*sample);
            }
        }

        if self.input_buffer[0].len() < self.input_frames_needed {
            return Ok(Vec::new());
        }

        let input_chunk: Vec<Vec<f32>> = self
            .input_buffer
            .iter()
            .map(|channel| channel[..self.input_frames_needed].to_vec())
            .collect();

        let output_buffer = self
            .resampler
            .process(&input_chunk, None)
            .map_err(|err| AudioError::ResamplerProcess(err.to_string()))?;

        for channel_input in &mut self.input_buffer {
            channel_input.drain(..self.input_frames_needed);
        }

        let frame_count = output_buffer[0].len();
        let mut output = Vec::with_capacity(frame_count);
        for frame_idx in 0..frame_count {
            let mut mixed_sample = 0.0_f32;
            for channel_idx in 0..self.channels {
                mixed_sample += output_buffer[channel_idx][frame_idx];
            }
            mixed_sample /= self.channels as f32;
            output.push(convert_f32_to_i16(mixed_sample));
        }

        Ok(output)
    }
}

pub fn convert_f32_to_i16(sample: f32) -> i16 {
    (sample.clamp(-1.0, 1.0) * i16::MAX as f32) as i16
}

#[cfg(test)]
mod tests {
    use super::*;

    fn build_test_signal(samples: usize) -> Vec<f32> {
        (0..samples)
            .map(|index| (index as f32 * 0.001).sin())
            .collect()
    }

    #[test]
    fn conversion_clamps_expected_range() {
        assert_eq!(convert_f32_to_i16(0.0), 0);
        assert_eq!(convert_f32_to_i16(0.5), 16_383);
        assert_eq!(convert_f32_to_i16(-0.5), -16_383);
        assert_eq!(convert_f32_to_i16(1.2), 32_767);
        assert_eq!(convert_f32_to_i16(-1.3), -32_767);
    }

    #[test]
    fn resampler_produces_expected_output_length() {
        let mut resampler = match AudioResampler::new(48_000, 16_000, 1) {
            Ok(value) => value,
            Err(err) => panic!("failed to create resampler: {err}"),
        };

        let input = build_test_signal(4_800);
        let mut output = Vec::new();
        for _ in 0..4 {
            let chunk_result = resampler.process(&input);
            let chunk = match chunk_result {
                Ok(value) => value,
                Err(err) => panic!("resampler processing failed: {err}"),
            };
            if !chunk.is_empty() {
                output = chunk;
                break;
            }
        }

        assert!(!output.is_empty());
        let diff = (output.len() as isize - 1_600).abs();
        assert!(diff <= 120);
    }

    #[test]
    fn resampler_rejects_invalid_interleaved_input() {
        let mut resampler = match AudioResampler::new(48_000, 16_000, 2) {
            Ok(value) => value,
            Err(err) => panic!("failed to create resampler: {err}"),
        };

        let result = resampler.process(&[0.2, -0.3, 0.1]);
        assert!(matches!(result, Err(AudioError::InvalidInput(_))));
    }
}
