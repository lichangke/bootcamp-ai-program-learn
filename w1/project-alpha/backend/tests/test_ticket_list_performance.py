import os
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from statistics import quantiles

import pytest
from app.main import app
from fastapi.testclient import TestClient
from psycopg import connect
from tests.helpers.db_env import isolated_database


@pytest.fixture(scope="module")
def performance_client() -> Iterator[TestClient]:
    base_url = os.getenv("TEST_DATABASE_URL")
    if not base_url:
        pytest.skip("Set TEST_DATABASE_URL to run performance tests.")

    with isolated_database(base_url, schema_prefix="project_alpha_perf_test") as scoped_url:
        with connect(scoped_url, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO tags (name) VALUES ('backend'), ('frontend'), ('ops')")
                cursor.execute("SELECT id FROM tags ORDER BY id ASC")
                tag_ids = [row[0] for row in cursor.fetchall()]

                rows = []
                for index in range(10_000):
                    status = "done" if index % 3 == 0 else "open"
                    completed_at = datetime.now(UTC) if status == "done" else None
                    title = f"ticket-{index} deploy backend"
                    rows.append((title, f"description {index}", status, completed_at))

                cursor.executemany(
                    """
                    INSERT INTO tickets (title, description, status, completed_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    rows,
                )

                cursor.execute("SELECT id FROM tickets ORDER BY id ASC")
                ticket_ids = [row[0] for row in cursor.fetchall()]

                tag_links = []
                for index, ticket_id in enumerate(ticket_ids):
                    tag_links.append((ticket_id, tag_ids[index % len(tag_ids)]))
                cursor.executemany(
                    "INSERT INTO ticket_tags (ticket_id, tag_id) VALUES (%s, %s)",
                    tag_links,
                )

        with TestClient(app) as client:
            yield client


def test_ticket_list_p95_under_500ms(performance_client: TestClient) -> None:
    durations: list[float] = []

    for _ in range(30):
        start = time.perf_counter()
        response = performance_client.get(
            "/api/tickets?q=deploy&status=open&page=1&page_size=20",
        )
        end = time.perf_counter()

        assert response.status_code == 200
        durations.append(end - start)

    p95 = quantiles(durations, n=20)[18]
    assert p95 < 0.5, f"P95 list query latency exceeded target: {p95:.4f}s"
