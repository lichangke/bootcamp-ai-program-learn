"""Application context container and access helpers."""

from dataclasses import dataclass

from pg_mcp.config.settings import Settings
from pg_mcp.security.validator import SQLValidator
from pg_mcp.services.executor import SQLExecutor
from pg_mcp.services.llm import LLMService
from pg_mcp.services.schema import SchemaService


@dataclass
class AppContext:
    """Dependency container for runtime services."""

    settings: Settings
    validator: SQLValidator
    executor: SQLExecutor
    schema_service: SchemaService
    llm_service: LLMService

    async def close(self) -> None:
        """Close managed resources."""
        await self.llm_service.close()
        await self.executor.close()


_context: AppContext | None = None


def get_context() -> AppContext:
    """Return globally registered app context."""
    if _context is None:
        raise RuntimeError("AppContext is not initialized.")
    return _context


def set_context(ctx: AppContext) -> None:
    """Set global app context reference."""
    global _context
    _context = ctx


def clear_context() -> None:
    """Clear global app context reference."""
    global _context
    _context = None

