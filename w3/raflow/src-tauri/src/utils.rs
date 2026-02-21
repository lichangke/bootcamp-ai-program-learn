use std::time::{SystemTime, UNIX_EPOCH};

/// Returns the current time as milliseconds since Unix epoch.
pub fn now_epoch_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or(0)
}

/// Checks if a character is a CJK (Chinese, Japanese, Korean) character.
pub fn is_cjk(ch: char) -> bool {
    matches!(
        ch as u32,
        0x3400..=0x4DBF
            | 0x4E00..=0x9FFF
            | 0xF900..=0xFAFF
            | 0x20000..=0x2A6DF
            | 0x2A700..=0x2B73F
            | 0x2B740..=0x2B81F
            | 0x2B820..=0x2CEAF
            | 0x2CEB0..=0x2EBEF
            | 0x3000..=0x303F
    )
}

/// Checks if text contains any CJK characters.
pub fn contains_cjk(text: &str) -> bool {
    text.chars().any(is_cjk)
}

/// Checks if a character is punctuation that can join text segments.
pub fn is_join_boundary_punctuation(ch: char) -> bool {
    matches!(
        ch,
        '.' | ',' | '!' | '?' | ';' | ':' | '，' | '。' | '！' | '？' | '；' | '：' | '、'
    )
}
