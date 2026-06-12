//! Image compression via local downsampling for multimodal payloads.
//!
//! High-resolution images sent through LLM APIs consume enormous token
//! budgets (a single 1024×1024 JPEG can be 150KB+ / ~50K tokens). This
//! module aggressively downsamples images to 256×256 thumbnails and stores
//! the original in the CCR store for lossless retrieval.
//!
//! # Compression strategy
//!
//! 1. Decode base64 → raw bytes
//! 2. Hash original with BLAKE3 → 24-char CCR key
//! 3. Store original base64 in CcrStore under the key
//! 4. Parse as image, resize to 256×256 (nearest-neighbor for speed)
//! 5. Re-encode to PNG → base64
//! 6. Return `compressed_base64<<ccr:{hash}>>`

use base64::Engine;

use crate::ccr::{compute_key, CcrStore};

/// Errors that can occur during image compression.
#[derive(Debug, thiserror::Error)]
pub enum ImageCompressError {
    #[error("failed to decode base64: {0}")]
    Base64Decode(String),

    #[error("failed to parse image: {0}")]
    ImageParse(String),

    #[error("failed to encode compressed image: {0}")]
    Encode(String),
}

/// Compress a base64-encoded image by downsampling to 256×256 and storing
/// the original in the CCR store.
///
/// Returns the compressed base64 payload with the CCR marker appended.
/// The marker enables lossless retrieval of the original image via
/// `headroom_retrieve`.
pub fn compress_image(
    base64_blob: &str,
    store: Option<&dyn CcrStore>,
) -> Result<String, ImageCompressError> {
    // 1. Decode base64
    let original_bytes = base64::engine::general_purpose::STANDARD
        .decode(base64_blob)
        .map_err(|e| ImageCompressError::Base64Decode(e.to_string()))?;

    // 2. Hash original → CCR key
    let hash = compute_key(&original_bytes);

    // 3. Store original in CCR
    if let Some(s) = store {
        s.put(&hash, base64_blob);
    }

    // 4. Parse as image
    let img = image::load_from_memory(&original_bytes)
        .map_err(|e| ImageCompressError::ImageParse(e.to_string()))?;

    // 5. Resize to 256×256
    let resized = img.resize(
        256,
        256,
        image::imageops::FilterType::Nearest,
    );

    // 6. Encode to PNG bytes
    let mut png_bytes: Vec<u8> = Vec::new();
    resized
        .write_to(&mut std::io::Cursor::new(&mut png_bytes), image::ImageFormat::Png)
        .map_err(|e| ImageCompressError::Encode(e.to_string()))?;

    // 7. Encode to base64
    let compressed_b64 = base64::engine::general_purpose::STANDARD.encode(&png_bytes);

    // 8. Return with CCR marker
    Ok(format!("{}<<ccr:{}>>", compressed_b64, hash))
}

/// Check if a string looks like a base64-encoded image.
///
/// Heuristics:
/// - Starts with `data:image/` (data-URI)
/// - Or is long base64 that decodes to a recognized image magic number
pub fn looks_like_image_base64(s: &str) -> bool {
    // Fast path: data-URI prefix
    if s.starts_with("data:image/") {
        return true;
    }

    // Check for common image base64 patterns — raw base64 without data-URI
    // prefix but with image magic bytes after decoding
    if s.len() < 64 {
        return false;
    }

    // Try decoding a small prefix to check magic bytes
    let decode_len = std::cmp::min(s.len(), 32);
    // Find a clean base64 boundary (multiple of 4)
    let clean_len = (decode_len / 4) * 4;
    if clean_len == 0 {
        return false;
    }

    if let Ok(bytes) = base64::engine::general_purpose::STANDARD
        .decode(&s[..clean_len])
    {
        // JPEG magic: FF D8 FF
        if bytes.len() >= 3 && bytes[0] == 0xFF && bytes[1] == 0xD8 && bytes[2] == 0xFF {
            return true;
        }
        // PNG magic: 89 50 4E 47
        if bytes.len() >= 4
            && bytes[0] == 0x89
            && bytes[1] == 0x50
            && bytes[2] == 0x4E
            && bytes[3] == 0x47
        {
            return true;
        }
        // GIF magic: 47 49 46 38
        if bytes.len() >= 4 && bytes[0] == 0x47 && bytes[1] == 0x49 && bytes[2] == 0x46 && bytes[3] == 0x38 {
            return true;
        }
        // WebP magic: RIFF....WEBP
        if bytes.len() >= 4 && bytes[0] == 0x52 && bytes[1] == 0x49 && bytes[2] == 0x46 && bytes[3] == 0x46 {
            return true;
        }
        // BMP magic: 42 4D
        if bytes.len() >= 2 && bytes[0] == 0x42 && bytes[1] == 0x4D {
            return true;
        }
    }

    false
}

/// Extract the MIME type from a data-URI image string.
///
/// Returns `Some("image/jpeg")`, `Some("image/png")`, etc. if the string
/// starts with `data:image/`. Returns `None` otherwise.
pub fn extract_image_mime(s: &str) -> Option<&str> {
    if !s.starts_with("data:") {
        return None;
    }
    let rest = &s[5..]; // skip "data:"
    let end = rest.find(';')?;
    let mime = &rest[..end];
    if mime.starts_with("image/") {
        Some(mime)
    } else {
        None
    }
}

/// Strip the data-URI prefix from a base64 image string, returning just
/// the raw base64 data.
///
/// Handles formats like:
/// - `data:image/jpeg;base64,/9j/4AAQ...`
/// - `data:image/png;base64,iVBORw0...`
pub fn strip_data_uri_prefix(s: &str) -> &str {
    if let Some(pos) = s.find(",") {
        // Everything after the comma is the raw base64
        &s[pos + 1..]
    } else {
        s
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ccr::InMemoryCcrStore;
    use std::sync::Arc;

    #[test]
    fn looks_like_image_data_uri() {
        assert!(looks_like_image_base64("data:image/jpeg;base64,/9j/4AAQ"));
        assert!(looks_like_image_base64("data:image/png;base64,iVBORw0KGgo"));
        assert!(!looks_like_image_base64("data:audio/wav;base64,UklGR"));
        assert!(!looks_like_image_base64("hello world"));
    }

    #[test]
    fn extract_image_mime_works() {
        assert_eq!(
            extract_image_mime("data:image/jpeg;base64,/9j/4AAQ"),
            Some("image/jpeg")
        );
        assert_eq!(
            extract_image_mime("data:image/png;base64,abc"),
            Some("image/png")
        );
        assert_eq!(extract_image_mime("data:text/plain;hello"), None);
        assert_eq!(extract_image_mime("not a data uri"), None);
    }

    #[test]
    fn strip_data_uri_prefix_works() {
        assert_eq!(
            strip_data_uri_prefix("data:image/jpeg;base64,/9j/4AAQ"),
            "/9j/4AAQ"
        );
        assert_eq!(
            strip_data_uri_prefix("rawbase64data"),
            "rawbase64data"
        );
    }

    #[test]
    fn compress_stores_original_in_ccr() {
        // Create a tiny valid PNG (1×1 red pixel)
        let img = image::DynamicImage::new_rgb8(1, 1);
        let mut png_buf = std::io::Cursor::new(Vec::new());
        img.write_to(&mut png_buf, image::ImageFormat::Png).unwrap();
        let png_bytes = png_buf.into_inner();
        let b64 = base64::engine::general_purpose::STANDARD.encode(&png_bytes);

        let store: Arc<dyn CcrStore> = Arc::new(InMemoryCcrStore::new());
        let result = compress_image(&b64, Some(store.as_ref())).unwrap();

        // Result should contain the CCR marker
        assert!(result.contains("<<ccr:"));
        assert!(result.ends_with(">>"));

        // Store should have the original
        assert_eq!(store.len(), 1);
    }

    #[test]
    fn compress_without_store_works() {
        // Create a tiny valid PNG (1×1 blue pixel)
        let img = image::DynamicImage::new_rgb8(1, 1);
        let mut png_buf = std::io::Cursor::new(Vec::new());
        img.write_to(&mut png_buf, image::ImageFormat::Png).unwrap();
        let png_bytes = png_buf.into_inner();
        let b64 = base64::engine::general_purpose::STANDARD.encode(&png_bytes);

        let result = compress_image(&b64, None).unwrap();
        assert!(result.contains("<<ccr:"));
    }

    #[test]
    fn compress_invalid_base64_errors() {
        let result = compress_image("!!!not-valid-base64!!!", None);
        assert!(result.is_err());
    }
}
