from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import cast

from src.models.connection import DatabaseConnection, SupportedDialect
from src.models.metadata import SchemaMetadata

DEFAULT_DB_DIR = Path.home() / ".db_query"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "db_query.db"


def get_db_path() -> Path:
    return DEFAULT_DB_PATH


def init_storage() -> None:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS connections (
                name TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                dialect TEXT NOT NULL DEFAULT 'postgres',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        _migrate_connections_table(connection)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                connection_name TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (connection_name),
                FOREIGN KEY (connection_name) REFERENCES connections(name) ON DELETE CASCADE
            )
            """
        )
        connection.commit()


def _migrate_connections_table(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()
    rows = cursor.execute("PRAGMA table_info(connections)").fetchall()
    columns = {str(row[1]) for row in rows}
    if "dialect" not in columns:
        cursor.execute(
            "ALTER TABLE connections "
            "ADD COLUMN dialect TEXT NOT NULL DEFAULT 'postgres'"
        )
        cursor.execute("UPDATE connections SET dialect = 'mysql' WHERE url LIKE 'mysql://%'")
        cursor.execute(
            "UPDATE connections SET dialect = 'postgres' "
            "WHERE dialect IS NULL OR dialect = ''"
        )


def _get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def upsert_connection(connection_model: DatabaseConnection) -> None:
    with _get_connection() as connection:
        connection.execute(
            """
            INSERT INTO connections (name, url, dialect, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                url = excluded.url,
                dialect = excluded.dialect,
                updated_at = excluded.updated_at
            """,
            (
                connection_model.name,
                connection_model.url,
                connection_model.dialect,
                connection_model.created_at.isoformat(),
                connection_model.updated_at.isoformat(),
            ),
        )
        connection.commit()


def list_connections() -> list[DatabaseConnection]:
    with _get_connection() as connection:
        rows = connection.execute(
            """
            SELECT name, url, dialect, created_at, updated_at
            FROM connections
            ORDER BY name ASC
            """
        ).fetchall()
    return [
        DatabaseConnection(
            name=str(row["name"]),
            url=str(row["url"]),
            dialect=_resolve_dialect_value(row["dialect"], str(row["url"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
            status="unknown",
        )
        for row in rows
    ]


def get_connection_by_name(name: str) -> DatabaseConnection | None:
    with _get_connection() as connection:
        row = connection.execute(
            """
            SELECT name, url, dialect, created_at, updated_at
            FROM connections
            WHERE name = ?
            """,
            (name,),
        ).fetchone()
    if row is None:
        return None
    return DatabaseConnection(
        name=str(row["name"]),
        url=str(row["url"]),
        dialect=_resolve_dialect_value(row["dialect"], str(row["url"])),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
        status="unknown",
    )


def _resolve_dialect_value(raw_dialect: object, url: str) -> SupportedDialect:
    if isinstance(raw_dialect, str):
        normalized = raw_dialect.lower()
        if normalized in {"postgres", "mysql"}:
            return cast(SupportedDialect, normalized)
    return _infer_dialect_from_url(url)


def _infer_dialect_from_url(url: str) -> SupportedDialect:
    lower_url = url.lower()
    if lower_url.startswith("mysql://"):
        return "mysql"
    return "postgres"


def delete_connection(name: str) -> bool:
    with _get_connection() as connection:
        cursor = connection.execute("DELETE FROM connections WHERE name = ?", (name,))
        connection.commit()
    return cursor.rowcount > 0


def save_metadata(connection_name: str, metadata: SchemaMetadata) -> None:
    metadata_for_storage = metadata
    if metadata.connection_name != connection_name:
        metadata_for_storage = metadata.model_copy(update={"connection_name": connection_name})

    metadata_json = metadata_for_storage.model_dump_json(by_alias=True)
    with _get_connection() as connection:
        connection.execute(
            """
            INSERT INTO metadata (connection_name, metadata_json, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(connection_name) DO UPDATE SET
                metadata_json = excluded.metadata_json,
                fetched_at = excluded.fetched_at
            """,
            (connection_name, metadata_json, metadata_for_storage.fetched_at.isoformat()),
        )
        connection.commit()


def get_metadata(connection_name: str) -> SchemaMetadata | None:
    with _get_connection() as connection:
        row = connection.execute(
            """
            SELECT metadata_json
            FROM metadata
            WHERE connection_name = ?
            """,
            (connection_name,),
        ).fetchone()
    if row is None:
        return None
    data = json.loads(str(row["metadata_json"]))
    return SchemaMetadata.model_validate(data)
