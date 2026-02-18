import os
from collections.abc import Iterator

import pytest
from app.main import app
from fastapi.testclient import TestClient
from tests.helpers.db_env import isolated_database


@pytest.fixture(scope="module")
def integration_client() -> Iterator[TestClient]:
    base_url = os.getenv("TEST_DATABASE_URL")
    if not base_url:
        pytest.skip("Set TEST_DATABASE_URL to run integration tests.")

    with isolated_database(base_url, schema_prefix="project_alpha_api_test"):
        with TestClient(app) as client:
            yield client


def test_ticket_tag_end_to_end_flow(integration_client: TestClient) -> None:
    backend_tag = integration_client.post("/api/tags", json={"name": "backend"})
    assert backend_tag.status_code == 201
    backend_id = backend_tag.json()["data"]["id"]

    urgent_tag = integration_client.post("/api/tags", json={"name": "urgent"})
    assert urgent_tag.status_code == 201
    urgent_id = urgent_tag.json()["data"]["id"]

    created_ticket = integration_client.post(
        "/api/tickets",
        json={
            "title": "Build day7 integration coverage",
            "description": "exercise all endpoints",
            "tag_ids": [backend_id, urgent_id],
        },
    )
    assert created_ticket.status_code == 201
    ticket_payload = created_ticket.json()["data"]
    ticket_id = ticket_payload["id"]
    assert ticket_payload["status"] == "open"
    assert ticket_payload["tag_ids"] == [backend_id, urgent_id]

    loaded_ticket = integration_client.get(f"/api/tickets/{ticket_id}")
    assert loaded_ticket.status_code == 200
    assert loaded_ticket.json()["data"]["title"] == "Build day7 integration coverage"

    updated_ticket = integration_client.put(
        f"/api/tickets/{ticket_id}",
        json={
            "title": "Build day7 integration tests",
            "description": "updated desc",
            "tag_ids": [backend_id],
        },
    )
    assert updated_ticket.status_code == 200
    assert updated_ticket.json()["data"]["tag_ids"] == [backend_id]

    completed_ticket = integration_client.patch(f"/api/tickets/{ticket_id}/complete")
    assert completed_ticket.status_code == 200
    assert completed_ticket.json()["data"]["status"] == "done"
    assert completed_ticket.json()["data"]["completed_at"] is not None

    reopened_ticket = integration_client.patch(f"/api/tickets/{ticket_id}/reopen")
    assert reopened_ticket.status_code == 200
    assert reopened_ticket.json()["data"]["status"] == "open"
    assert reopened_ticket.json()["data"]["completed_at"] is None

    list_all = integration_client.get("/api/tickets?page=1&page_size=20")
    assert list_all.status_code == 200
    assert list_all.json()["meta"]["total"] == 1

    list_by_tag = integration_client.get(f"/api/tickets?tag_id={backend_id}&page=1&page_size=20")
    assert list_by_tag.status_code == 200
    assert len(list_by_tag.json()["data"]) == 1

    list_by_search = integration_client.get("/api/tickets?q=integration&page=1&page_size=20")
    assert list_by_search.status_code == 200
    assert len(list_by_search.json()["data"]) == 1

    list_by_status = integration_client.get("/api/tickets?status=open&page=1&page_size=20")
    assert list_by_status.status_code == 200
    assert len(list_by_status.json()["data"]) == 1

    removed_tag = integration_client.delete(f"/api/tags/{urgent_id}")
    assert removed_tag.status_code == 204

    after_tag_delete = integration_client.get(f"/api/tickets/{ticket_id}")
    assert after_tag_delete.status_code == 200
    assert after_tag_delete.json()["data"]["tag_ids"] == [backend_id]

    removed_ticket = integration_client.delete(f"/api/tickets/{ticket_id}")
    assert removed_ticket.status_code == 204

    not_found_ticket = integration_client.get(f"/api/tickets/{ticket_id}")
    assert not_found_ticket.status_code == 404
    assert not_found_ticket.json()["error"]["code"] == "TICKET_NOT_FOUND"
