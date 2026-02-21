use thiserror::Error;

#[derive(Debug, Error)]
pub enum AppError {
    #[error("failed to initialize logging: {0}")]
    LoggingInit(String),
    #[error("runtime error: {0}")]
    Runtime(String),
}
