"""Pydantic settings models."""

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseModel):
    """Single PostgreSQL connection configuration."""

    name: str
    host: str = "localhost"
    port: int = 5432
    database: str
    username: str
    password: SecretStr
    ssl_mode: str = "prefer"
    min_connections: int = 1
    max_connections: int = 10
    is_default: bool = False


class DeepSeekConfig(BaseModel):
    """DeepSeek API configuration."""

    api_key: SecretStr
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    temperature: float = 0.1
    max_tokens: int = 2000
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_base_delay: float = 1.0


class QueryConfig(BaseModel):
    """SQL execution limits."""

    timeout_seconds: int = 30
    max_rows: int = 100
    max_rows_limit: int = 1000
    default_return_mode: str = "both"


class SchemaCacheConfig(BaseModel):
    """Schema cache policy."""

    ttl_minutes: int = 60
    auto_refresh: bool = True


class SecurityConfig(BaseModel):
    """Security policy for SQL validation."""

    allowed_statement_types: list[str] = ["Select"]
    allowed_ast_nodes: list[str] = [
        "Select",
        "From",
        "Join",
        "Where",
        "Group",
        "Having",
        "Order",
        "Limit",
        "Offset",
        "With",
        "CTE",
        "Union",
        "Intersect",
        "Except",
        "Subquery",
        "Column",
        "Table",
        "Alias",
        "Star",
        "Identifier",
        "Literal",
        "Ordered",
        "Desc",
        "Asc",
        "Paren",
        "Func",
        "Anonymous",
        "Case",
        "Cast",
        "Between",
        "In",
        "Like",
        "And",
        "Or",
        "Not",
        "Eq",
        "EQ",
        "NEq",
        "GT",
        "GTE",
        "LT",
        "LTE",
        "Add",
        "Sub",
        "Mul",
        "Div",
        "Mod",
        "Neg",
        "Distinct",
        "All",
        "Null",
        "Boolean",
        "Interval",
        "Extract",
        "Coalesce",
        "NullIf",
        "Greatest",
        "Least",
        "Count",
        "Sum",
        "Avg",
        "Min",
        "Max",
        "TableAlias",
    ]
    blocked_functions: list[str] = [
        "pg_sleep",
        "lo_export",
        "lo_import",
        "pg_read_file",
        "pg_write_file",
        "pg_read_binary_file",
        "pg_ls_dir",
        "pg_stat_file",
        "pg_terminate_backend",
        "pg_cancel_backend",
        "pg_reload_conf",
        "set_config",
        "current_setting",
    ]
    blocked_constructs: list[str] = [
        "Into",
        "Copy",
        "Lock",
    ]
    enable_prompt_injection_check: bool = True


class Settings(BaseSettings):
    """Top-level service settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

    server_name: str = "pg-mcp-server"
    log_level: str = "INFO"
    databases: list[DatabaseConfig] = Field(default_factory=list)
    deepseek: DeepSeekConfig
    query: QueryConfig = Field(default_factory=QueryConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    schema_cache: SchemaCacheConfig = Field(default_factory=SchemaCacheConfig)

    @field_validator("databases", mode="before")
    @classmethod
    def _normalize_database_list(cls, value):
        """Support DATABASES__0__... style env parsing from dict to list."""
        if isinstance(value, dict):
            numeric_keys = [key for key in value if str(key).isdigit()]
            if numeric_keys:
                return [value[key] for key in sorted(numeric_keys, key=lambda item: int(str(item)))]
        return value

    @property
    def default_database(self) -> DatabaseConfig | None:
        """Return the configured default database."""
        for db in self.databases:
            if db.is_default:
                return db
        return self.databases[0] if self.databases else None
