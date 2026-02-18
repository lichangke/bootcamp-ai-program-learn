from __future__ import annotations

import os
from pathlib import Path

import psycopg


def load_env_file(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def clean_sql(raw_sql: str) -> str:
    cleaned_lines: list[str] = []
    for line in raw_sql.splitlines():
        stripped = line.lstrip()
        # Skip psql meta commands (e.g. \set ON_ERROR_STOP on).
        if stripped.startswith("\\"):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def split_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_string = False
    idx = 0

    while idx < len(sql_text):
        ch = sql_text[idx]
        current.append(ch)

        if ch == "'":
            next_char = sql_text[idx + 1] if idx + 1 < len(sql_text) else ""
            if in_string and next_char == "'":
                current.append(next_char)
                idx += 1
            else:
                in_string = not in_string
        elif ch == ";" and not in_string:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []

        idx += 1

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)

    return statements


def resolve_project_paths() -> tuple[Path, Path]:
    project_root = Path(__file__).resolve().parents[2]
    env_path = project_root / ".env"
    seed_path = project_root / "seed.sql"
    return env_path, seed_path


def resolve_database_url(env_path: Path) -> str:
    env_values = load_env_file(env_path)
    database_url = os.getenv("DATABASE_URL") or env_values.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Set env var DATABASE_URL or add DATABASE_URL to .env."
        )
    return database_url


def execute_seed(database_url: str, seed_path: Path) -> None:
    if not seed_path.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_path}")

    raw_sql = seed_path.read_text(encoding="utf-8")
    sql_text = clean_sql(raw_sql)
    statements = split_statements(sql_text)
    if not statements:
        raise RuntimeError(f"No SQL statements found in {seed_path}")

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
                if cursor.description:
                    rows = cursor.fetchall()
                    if rows:
                        print(rows)
        connection.commit()


def main() -> None:
    env_path, seed_path = resolve_project_paths()
    database_url = resolve_database_url(env_path)
    execute_seed(database_url, seed_path)
    print("Seed completed successfully.")


if __name__ == "__main__":
    main()
