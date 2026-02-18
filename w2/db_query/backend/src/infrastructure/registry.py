from __future__ import annotations

from urllib.parse import urlparse

from src.domain.interfaces.db_adapter import DbAdapter
from src.infrastructure.adapters.mysql.adapter import MySqlAdapter
from src.infrastructure.adapters.postgres.adapter import PostgresAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._by_scheme: dict[str, DbAdapter] = {}

    def register(self, adapter: DbAdapter) -> None:
        for scheme in adapter.schemes:
            self._by_scheme[scheme.lower()] = adapter

    def resolve_by_url(self, url: str) -> DbAdapter:
        scheme = urlparse(url).scheme.lower()
        adapter = self._by_scheme.get(scheme)
        if adapter is None:
            supported = ", ".join(sorted(self._by_scheme.keys()))
            raise ValueError(f"Unsupported database scheme '{scheme}'. Supported: {supported}")
        return adapter


def build_default_registry() -> AdapterRegistry:
    registry = AdapterRegistry()
    registry.register(PostgresAdapter())
    registry.register(MySqlAdapter())
    return registry
