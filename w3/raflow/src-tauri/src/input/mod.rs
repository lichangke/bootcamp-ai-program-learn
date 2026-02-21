pub mod injector;

use hanconv::t2s;
use thiserror::Error;

pub const DEFAULT_INJECTION_THRESHOLD: usize = 10;
pub const MAX_TRANSCRIPT_LENGTH: usize = 10_000;
pub const DEFAULT_PARTIAL_REWRITE_ENABLED: bool = true;
pub const DEFAULT_PARTIAL_REWRITE_MAX_BACKSPACE: usize = 12;
pub const DEFAULT_PARTIAL_REWRITE_WINDOW_MS: u64 = 140;
pub const MIN_PARTIAL_REWRITE_MAX_BACKSPACE: usize = 0;
pub const MAX_PARTIAL_REWRITE_MAX_BACKSPACE: usize = 64;
pub const MIN_PARTIAL_REWRITE_WINDOW_MS: u64 = 0;
pub const MAX_PARTIAL_REWRITE_WINDOW_MS: u64 = 2_000;

#[derive(Debug, Error)]
pub enum InputError {
    #[error("failed to initialize input injector: {0}")]
    Initialization(String),
    #[error("failed to simulate keyboard input: {0}")]
    Keyboard(String),
    #[error("clipboard operation failed: {0}")]
    Clipboard(String),
    #[error("invalid transcript: {0}")]
    Validation(#[from] ValidationError),
}

#[derive(Debug, Error, PartialEq, Eq)]
pub enum ValidationError {
    #[error("text exceeds maximum length of {MAX_TRANSCRIPT_LENGTH} characters")]
    TooLong,
    #[error("text contains suspicious shell-like tokens")]
    MaliciousContent,
}

pub fn validate_transcript(text: &str) -> Result<String, ValidationError> {
    if text.chars().count() > MAX_TRANSCRIPT_LENGTH {
        return Err(ValidationError::TooLong);
    }

    let cleaned: String = text
        .chars()
        .filter(|c| !c.is_control() || c.is_whitespace())
        .collect();

    if contains_malicious_patterns(&cleaned) {
        return Err(ValidationError::MaliciousContent);
    }

    Ok(cleaned)
}

pub fn normalize_transcript_text(text: &str, language_code: &str) -> String {
    let trimmed = text.trim();
    if trimmed.is_empty() {
        return String::new();
    }

    if language_code.trim() == "zho" {
        t2s(trimmed)
    } else {
        trimmed.to_string()
    }
}

pub fn append_terminal_punctuation(text: &str) -> String {
    let trimmed = text.trim();
    if trimmed.is_empty() {
        return String::new();
    }

    if has_terminal_punctuation(trimmed) {
        return trimmed.to_string();
    }

    let suffix = if contains_cjk(trimmed) { "，" } else { "." };
    format!("{trimmed}{suffix}")
}

pub fn resolve_committed_punctuation_delta(committed_text: &str, injected_text: &str) -> String {
    let committed = committed_text.trim();
    if committed.is_empty() {
        return String::new();
    }

    let injected = injected_text.trim();
    if injected.is_empty() || committed == injected {
        return String::new();
    }

    if let Some(delta) = committed.strip_prefix(injected) {
        if delta
            .trim()
            .chars()
            .all(|ch| is_terminal_punctuation(ch) || is_closing_punctuation_wrapper(ch))
        {
            return delta.to_string();
        }
    }

    if has_terminal_punctuation(injected) {
        return String::new();
    }

    extract_terminal_punctuation_suffix(committed)
}

fn contains_malicious_patterns(text: &str) -> bool {
    let dangerous_patterns = ["$(", "`", ";", "&&", "||", "|", ">", "<"];
    dangerous_patterns
        .iter()
        .any(|pattern| text.contains(pattern))
}

fn has_terminal_punctuation(text: &str) -> bool {
    let mut chars = text.chars().rev();
    for ch in chars.by_ref() {
        if is_closing_punctuation_wrapper(ch) {
            continue;
        }
        return is_terminal_punctuation(ch);
    }
    false
}

fn is_terminal_punctuation(ch: char) -> bool {
    matches!(ch, '.' | ',' | '!' | '?' | '，' | '。' | '！' | '？')
}

fn is_closing_punctuation_wrapper(ch: char) -> bool {
    matches!(ch, '"' | '\'' | '”' | '’' | ')' | ']' | '}')
}

fn extract_terminal_punctuation_suffix(text: &str) -> String {
    let trimmed_end = text.trim_end();
    if trimmed_end.is_empty() {
        return String::new();
    }

    let chars: Vec<(usize, char)> = trimmed_end.char_indices().collect();
    if chars.is_empty() {
        return String::new();
    }

    let mut index = chars.len() - 1;
    while index > 0 && is_closing_punctuation_wrapper(chars[index].1) {
        index -= 1;
    }

    if !is_terminal_punctuation(chars[index].1) {
        return String::new();
    }

    let start = chars[index].0;
    trimmed_end[start..].to_string()
}

fn contains_cjk(text: &str) -> bool {
    text.chars().any(is_cjk)
}

fn is_cjk(ch: char) -> bool {
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validation_accepts_normal_text() {
        let result = validate_transcript("Hello world");
        assert!(result.is_ok());
    }

    #[test]
    fn validation_rejects_overlong_text() {
        let input = "a".repeat(MAX_TRANSCRIPT_LENGTH + 1);
        let result = validate_transcript(&input);
        assert!(matches!(result, Err(ValidationError::TooLong)));
    }

    #[test]
    fn validation_rejects_malicious_content() {
        let result = validate_transcript("hello && rm -rf /");
        assert!(matches!(result, Err(ValidationError::MaliciousContent)));
    }

    #[test]
    fn append_punctuation_for_english_sentence() {
        assert_eq!(append_terminal_punctuation("hello world"), "hello world.");
    }

    #[test]
    fn append_punctuation_for_chinese_sentence() {
        assert_eq!(append_terminal_punctuation("你好 世界"), "你好 世界，");
    }

    #[test]
    fn keep_existing_terminal_punctuation() {
        assert_eq!(append_terminal_punctuation("done!"), "done!");
        assert_eq!(append_terminal_punctuation("好的，"), "好的，");
    }

    #[test]
    fn normalize_traditional_chinese_to_simplified() {
        assert_eq!(normalize_transcript_text("後臺開發", "zho"), "后台开发");
    }

    #[test]
    fn committed_delta_returns_punctuation_only() {
        assert_eq!(
            resolve_committed_punctuation_delta("hello world.", "hello world"),
            "."
        );
        assert_eq!(resolve_committed_punctuation_delta("你好，", "你好"), "，");
    }

    #[test]
    fn committed_delta_ignores_non_punctuation_suffix() {
        assert_eq!(
            resolve_committed_punctuation_delta("hello world again", "hello world"),
            ""
        );
    }
}
