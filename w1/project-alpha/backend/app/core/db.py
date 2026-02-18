from psycopg import connect


def ping_database(database_url: str, timeout_seconds: int = 3) -> tuple[bool, str | None]:
    try:
        with connect(database_url, connect_timeout=timeout_seconds) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
        if result and result[0] == 1:
            return True, None
        return False, "Database ping returned an unexpected result."
    except Exception as exc:
        return False, str(exc)
