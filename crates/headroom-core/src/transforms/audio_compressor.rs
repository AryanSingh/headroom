//! Audio compression via downsampling for multimodal payloads.
//!
//! Audio data sent through LLM APIs (e.g., OpenAI's `input_audio` blocks)
//! can consume massive token budgets. This module decodes audio, downsamples
//! to 8kHz mono 16-bit PCM WAV, and stores the original in CCR for lossless
//! retrieval.
//!
//! # Compression strategy
//!
//! 1. Decode base64 → raw audio bytes
//! 2. Hash original with BLAKE3 → 24-char CCR key
//! 3. Store original base64 in CcrStore under the key
//! 4. Decode audio via symphonia → PCM samples
//! 5. Downsample to 8kHz mono
//! 6. Encode to WAV → base64
//! 7. Return `compressed_base64<<ccr:{hash}>>`

use base64::Engine;

use crate::ccr::{compute_key, CcrStore};

/// Errors that can occur during audio compression.
#[derive(Debug, thiserror::Error)]
pub enum AudioCompressError {
    #[error("failed to decode base64: {0}")]
    Base64Decode(String),

    #[error("failed to decode audio stream: {0}")]
    DecodeError(String),

    #[error("no audio tracks found in the input")]
    NoAudioTrack,

    #[error("failed to encode WAV: {0}")]
    WavEncode(String),

    #[error("unsupported audio format")]
    UnsupportedFormat,
}

/// Target sample rate for compressed audio (8 kHz).
const TARGET_SAMPLE_RATE: u32 = 8000;

/// Compress a base64-encoded audio payload by downsampling to 8kHz mono WAV
/// and storing the original in the CCR store.
///
/// Returns the compressed base64 payload with the CCR marker appended.
pub fn compress_audio(
    base64_audio: &str,
    store: Option<&dyn CcrStore>,
) -> Result<String, AudioCompressError> {
    // 1. Decode base64
    let original_bytes = base64::engine::general_purpose::STANDARD
        .decode(base64_audio)
        .map_err(|e| AudioCompressError::Base64Decode(e.to_string()))?;

    // 2. Hash original → CCR key
    let hash = compute_key(&original_bytes);

    // 3. Store original in CCR
    if let Some(s) = store {
        s.put(&hash, base64_audio);
    }

    // 4. Decode audio to PCM samples
    let (samples, original_rate, channels) = decode_audio_to_pcm(&original_bytes)?;

    // 5. Downsample to 8kHz mono
    let mono_samples = if channels > 1 {
        // Mix stereo to mono by averaging pairs
        samples
            .chunks(channels as usize)
            .map(|frame| {
                let sum: i32 = frame.iter().map(|&s| s as i32).sum();
                (sum / channels as i32) as i16
            })
            .collect::<Vec<i16>>()
    } else {
        samples
    };

    let resampled = if original_rate != TARGET_SAMPLE_RATE {
        // Simple nearest-neighbor downsampling
        let ratio = original_rate as f64 / TARGET_SAMPLE_RATE as f64;
        let output_len = (mono_samples.len() as f64 / ratio) as usize;
        (0..output_len)
            .map(|i| {
                let src_idx = (i as f64 * ratio) as usize;
                mono_samples[src_idx.min(mono_samples.len() - 1)]
            })
            .collect::<Vec<i16>>()
    } else {
        mono_samples
    };

    // 6. Encode to WAV
    let wav_bytes = encode_wav(&resampled, TARGET_SAMPLE_RATE)?;

    // 7. Encode to base64
    let compressed_b64 = base64::engine::general_purpose::STANDARD.encode(&wav_bytes);

    Ok(format!("{}<<ccr:{}>>", compressed_b64, hash))
}

/// Decode audio bytes into raw i16 PCM samples, sample rate, and channel count.
///
/// Uses symphonia to decode the audio stream, then converts all samples to
/// i16 via `SampleBuffer::copy_planar_ref` which handles format conversion.
fn decode_audio_to_pcm(data: &[u8]) -> Result<(Vec<i16>, u32, u16), AudioCompressError> {
    use symphonia::core::audio::SampleBuffer;
    use symphonia::core::formats::FormatOptions;
    use symphonia::core::io::MediaSourceStream;
    use symphonia::core::meta::MetadataOptions;
    use symphonia::core::probe::Hint;

    let cursor = std::io::Cursor::new(data.to_vec());
    let mss = MediaSourceStream::new(Box::new(cursor), Default::default());

    let mut hint = Hint::new();
    // Try to detect format from magic bytes
    if data.len() >= 8 {
        if data[0] == 0xFF && (data[1] & 0xE0) == 0xE0 {
            hint.with_extension("mp3");
        } else if data[0] == 0x52 && data[1] == 0x49 && data[2] == 0x46 && data[3] == 0x46 {
            hint.with_extension("wav");
        } else if data[4] == 0x66 && data[5] == 0x74 && data[6] == 0x79 && data[7] == 0x70 {
            hint.with_extension("m4a");
        }
    }

    let probed = symphonia::default::get_probe()
        .format(
            &hint,
            mss,
            &FormatOptions::default(),
            &MetadataOptions::default(),
        )
        .map_err(|e| AudioCompressError::DecodeError(format!("format probe failed: {e}")))?;

    let mut format = probed.format;
    let track = format
        .tracks()
        .iter()
        .find(|t| t.codec_params.sample_rate.is_some())
        .ok_or(AudioCompressError::NoAudioTrack)?;

    let track_id = track.id;
    let sample_rate = track.codec_params.sample_rate.unwrap_or(44100);
    let channels = track
        .codec_params
        .channels
        .map(|c| c.count() as u16)
        .unwrap_or(1);
    let channels_b = track
        .codec_params
        .channels
        .unwrap_or(symphonia::core::audio::Channels::FRONT_LEFT);
    let codec_params = track.codec_params.clone();

    let mut decoder = symphonia::default::get_codecs()
        .make(&codec_params, &Default::default())
        .map_err(|e| AudioCompressError::DecodeError(format!("decoder init failed: {e}")))?;

    let mut all_samples: Vec<i16> = Vec::new();
    let spec = symphonia::core::audio::SignalSpec::new(sample_rate, channels_b);

    loop {
        let packet = match format.next_packet() {
            Ok(p) => p,
            Err(symphonia::core::errors::Error::IoError(ref e))
                if e.kind() == std::io::ErrorKind::UnexpectedEof =>
            {
                break
            }
            Err(e) => return Err(AudioCompressError::DecodeError(e.to_string())),
        };

        if packet.track_id() != track_id {
            continue;
        }

        match decoder.decode(&packet) {
            Ok(audio_buf) => {
                let n_frames = audio_buf.frames();
                if n_frames == 0 {
                    continue;
                }
                // Allocate a SampleBuffer with enough capacity for this packet
                let mut sample_buf: SampleBuffer<i16> = SampleBuffer::new(n_frames as u64, spec);
                sample_buf.copy_planar_ref(audio_buf);
                all_samples.extend_from_slice(sample_buf.samples());
            }
            Err(symphonia::core::errors::Error::DecodeError(_)) => {
                // Skip corrupt frames gracefully
                continue;
            }
            Err(e) => return Err(AudioCompressError::DecodeError(e.to_string())),
        }
    }

    if all_samples.is_empty() {
        return Err(AudioCompressError::DecodeError(
            "no audio samples decoded".into(),
        ));
    }

    Ok((all_samples, sample_rate, channels))
}

/// Encode i16 PCM samples to WAV bytes at the given sample rate (mono).
fn encode_wav(samples: &[i16], sample_rate: u32) -> Result<Vec<u8>, AudioCompressError> {
    let spec = hound::WavSpec {
        channels: 1,
        sample_rate,
        bits_per_sample: 16,
        sample_format: hound::SampleFormat::Int,
    };

    let mut buf = std::io::Cursor::new(Vec::new());
    {
        let mut writer = hound::WavWriter::new(&mut buf, spec)
            .map_err(|e| AudioCompressError::WavEncode(e.to_string()))?;
        for &sample in samples {
            writer
                .write_sample(sample)
                .map_err(|e| AudioCompressError::WavEncode(e.to_string()))?;
        }
        writer
            .finalize()
            .map_err(|e| AudioCompressError::WavEncode(e.to_string()))?;
    }

    Ok(buf.into_inner())
}

/// Check if a string looks like a base64-encoded audio payload.
///
/// Heuristics:
/// - Starts with `data:audio/` (data-URI)
pub fn looks_like_audio_base64(s: &str) -> bool {
    if s.starts_with("data:audio/") {
        return true;
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ccr::InMemoryCcrStore;
    use std::sync::Arc;

    #[test]
    fn looks_like_audio_data_uri() {
        assert!(looks_like_audio_base64("data:audio/wav;base64,UklGR"));
        assert!(looks_like_audio_base64("data:audio/mp3;base64,//uQx"));
        assert!(!looks_like_audio_base64("data:image/jpeg;base64,/9j/4AAQ"));
        assert!(!looks_like_audio_base64("hello world"));
    }

    #[test]
    fn encode_wav_produces_valid_header() {
        let samples = vec![0i16; 8000]; // 1 second of silence at 8kHz
        let wav = encode_wav(&samples, 8000).unwrap();
        // WAV header: RIFF....WAVE
        assert_eq!(&wav[0..4], b"RIFF");
        assert_eq!(&wav[8..12], b"WAVE");
        assert_eq!(&wav[12..16], b"fmt ");
    }

    #[test]
    fn compress_stores_original_in_ccr() {
        // Create a minimal WAV in memory (1 second silence at 8kHz mono)
        let samples = vec![0i16; 8000];
        let spec = hound::WavSpec {
            channels: 1,
            sample_rate: 8000,
            bits_per_sample: 16,
            sample_format: hound::SampleFormat::Int,
        };
        let mut wav_buf = std::io::Cursor::new(Vec::new());
        {
            let mut writer = hound::WavWriter::new(&mut wav_buf, spec).unwrap();
            for &s in &samples {
                writer.write_sample(s).unwrap();
            }
            writer.finalize().unwrap();
        }
        let wav_bytes = wav_buf.into_inner();
        let b64 = base64::engine::general_purpose::STANDARD.encode(&wav_bytes);

        let store: Arc<dyn CcrStore> = Arc::new(InMemoryCcrStore::new());
        let result = compress_audio(&b64, Some(store.as_ref())).unwrap();

        assert!(result.contains("<<ccr:"));
        assert!(result.ends_with(">>"));
        assert_eq!(store.len(), 1);
    }

    #[test]
    fn compress_without_store_works() {
        let samples = vec![0i16; 8000];
        let spec = hound::WavSpec {
            channels: 1,
            sample_rate: 8000,
            bits_per_sample: 16,
            sample_format: hound::SampleFormat::Int,
        };
        let mut wav_buf = std::io::Cursor::new(Vec::new());
        {
            let mut writer = hound::WavWriter::new(&mut wav_buf, spec).unwrap();
            for &s in &samples {
                writer.write_sample(s).unwrap();
            }
            writer.finalize().unwrap();
        }
        let wav_bytes = wav_buf.into_inner();
        let b64 = base64::engine::general_purpose::STANDARD.encode(&wav_bytes);

        let result = compress_audio(&b64, None).unwrap();
        assert!(result.contains("<<ccr:"));
    }

    #[test]
    fn compress_invalid_base64_errors() {
        let result = compress_audio("!!!not-valid-base64!!!", None);
        assert!(result.is_err());
    }
}
