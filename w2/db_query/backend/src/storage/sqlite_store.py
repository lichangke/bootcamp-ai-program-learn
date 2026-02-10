from __future__ import annotations

import sqlite3
from pathlib import Path

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
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
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

