use nnnoiseless::DenoiseState;

const RNNOISE_SAMPLE_RATE: u32 = 48_000;
const I16_SCALE: f32 = i16::MAX as f32;

pub struct AudioDenoiser {
    state: Box<DenoiseState<'static>>,
    input_frame: [f32; DenoiseState::FRAME_SIZE],
    output_frame: [f32; DenoiseState::FRAME_SIZE],
    first_frame: bool,
}

impl AudioDenoiser {
    pub const FRAME_SIZE: usize = DenoiseState::FRAME_SIZE;

    pub fn for_sample_rate(sample_rate: u32) -> Option<Self> {
        if sample_rate == RNNOISE_SAMPLE_RATE {
            Some(Self::new())
        } else {
            None
        }
    }

    fn new() -> Self {
        Self {
            state: DenoiseState::new(),
            input_frame: [0.0; DenoiseState::FRAME_SIZE],
            output_frame: [0.0; DenoiseState::FRAME_SIZE],
            first_frame: true,
        }
    }

    pub fn process_chunk_in_place(&mut self, samples: &mut [f32]) {
        for frame in samples.chunks_exact_mut(Self::FRAME_SIZE) {
            for (idx, sample) in frame.iter().enumerate() {
                self.input_frame[idx] =
                    (*sample * I16_SCALE).clamp(i16::MIN as f32, i16::MAX as f32);
            }

            self.state
                .process_frame(&mut self.output_frame[..], &self.input_frame[..]);

            if self.first_frame {
                // RNNoise output has a startup transient on the very first frame.
                self.first_frame = false;
                continue;
            }

            for (idx, sample) in frame.iter_mut().enumerate() {
                *sample = (self.output_frame[idx] / I16_SCALE).clamp(-1.0, 1.0);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::AudioDenoiser;

    #[test]
    fn denoiser_keeps_signal_in_normalized_range() {
        let mut denoiser = AudioDenoiser::for_sample_rate(48_000).expect("denoiser enabled");
        let mut samples: Vec<f32> = (0..(AudioDenoiser::FRAME_SIZE * 4))
            .map(|idx| (idx as f32 * 0.003).sin() * 0.5)
            .collect();

        denoiser.process_chunk_in_place(&mut samples);

        assert!(samples.iter().all(|value| value.is_finite()));
        assert!(samples.iter().all(|value| *value >= -1.0 && *value <= 1.0));
    }
}
