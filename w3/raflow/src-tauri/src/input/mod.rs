pub mod injector;

use thiserror::Error;

pub const DEFAULT_INJECTION_THRESHOLD: usize = 10;
pub const MAX_TRANSCRIPT_LENGTH: usize = 10_000;

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

fn contains_malicious_patterns(text: &str) -> bool {
    let dangerous_patterns = ["$(", "`", ";", "&&", "||", "|", ">", "<"];
    dangerous_patterns
        .iter()
        .any(|pattern| text.contains(pattern))
}

fn has_terminal_punctuation(text: &str) -> bool {
    let mut chars = text.chars().rev();
    for ch in chars.by_ref() {
        if matches!(ch, '"' | '\'' | '”' | '’' | ')' | ']' | '}') {
            continue;
        }
        return matches!(ch, '.' | ',' | '!' | '?' | '，' | '。' | '！' | '？');
    }
    false
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
}
