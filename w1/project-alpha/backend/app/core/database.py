from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection, connect
from psycopg.rows import dict_row

from app.core.config import get_settings


def get_database_url() -> str:
    return get_settings().database_url


@contextmanager
def get_connection(database_url: str | None = None) -> Iterator[Connection]:
    url = database_url or get_database_url()
    with connect(url, row_factory=dict_row) as connection:
        yield connection
