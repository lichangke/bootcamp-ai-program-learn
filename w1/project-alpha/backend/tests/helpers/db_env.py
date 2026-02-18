import os
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4

from alembic import command
from alembic.config import Config
from app.core.config import get_settings
from psycopg import connect, sql


def with_search_path(database_url: str, schema_name: str) -> str:
  parsed = urlparse(database_url)
  query = dict(parse_qsl(parsed.query, keep_blank_values=True))
  option = f"-csearch_path={schema_name}"

  if query.get("options"):
      query["options"] = f"{query['options']} {option}"
  else:
      query["options"] = option

  return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


@contextmanager
def isolated_database(base_url: str, *, schema_prefix: str) -> Iterator[str]:
    schema_name = f"{schema_prefix}_{uuid4().hex[:8]}"
    scoped_url = with_search_path(base_url, schema_name)
    previous_database_url = os.getenv("DATABASE_URL")

    with connect(base_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))

    os.environ["DATABASE_URL"] = scoped_url
    get_settings.cache_clear()

    alembic_config = Config("alembic.ini")
    command.upgrade(alembic_config, "head")
    command.upgrade(alembic_config, "head")

    try:
        yield scoped_url
    finally:
        with connect(base_url, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name)),
                )

        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
        get_settings.cache_clear()
