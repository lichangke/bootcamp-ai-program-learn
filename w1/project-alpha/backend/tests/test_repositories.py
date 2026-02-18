import os
from datetime import UTC, datetime

import pytest
from app.repositories.tag_repository import TagRepository
from app.repositories.ticket_repository import TicketRepository
from app.repositories.ticket_tag_repository import TicketTagRepository
from psycopg import connect
from psycopg.errors import CheckViolation, UniqueViolation
from tests.helpers.db_env import isolated_database


@pytest.fixture(scope="module")
def repository_database_url() -> str:
    base_url = os.getenv("TEST_DATABASE_URL")
    if not base_url:
        pytest.skip("Set TEST_DATABASE_URL to run repository tests.")

    with isolated_database(base_url, schema_prefix="project_alpha_repo_test") as scoped_url:
        yield scoped_url


@pytest.fixture(autouse=True)
def clean_database(repository_database_url: str) -> None:
    with connect(repository_database_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE ticket_tags, tags, tickets RESTART IDENTITY CASCADE")


def test_ticket_repository_crud(repository_database_url: str) -> None:
    repository = TicketRepository(database_url=repository_database_url)

    created = repository.create(title="Day 2 migration", description="create baseline db layer")
    assert created.id > 0
    assert created.status == "open"
    assert created.completed_at is None

    loaded = repository.get_by_id(created.id)
    assert loaded is not None
    assert loaded.title == "Day 2 migration"

    completed_at = datetime.now(UTC)
    updated = repository.update(
        ticket_id=created.id,
        title="Day 2 migration done",
        description="core tables ready",
        status="done",
        completed_at=completed_at,
    )
    assert updated is not None
    assert updated.status == "done"
    assert updated.completed_at is not None

    listing = repository.list(limit=10, offset=0)
    assert len(listing) == 1
    assert listing[0].id == created.id

    deleted = repository.delete(created.id)
    assert deleted is True
    assert repository.get_by_id(created.id) is None


def test_ticket_status_completed_at_constraint(repository_database_url: str) -> None:
    repository = TicketRepository(database_url=repository_database_url)

    with pytest.raises(CheckViolation):
        repository.create(
            title="invalid done ticket",
            description=None,
            status="done",
            completed_at=None,
        )

    with pytest.raises(CheckViolation):
        repository.create(
            title="invalid open ticket",
            description=None,
            status="open",
            completed_at=datetime.now(UTC),
        )


def test_tag_repository_unique_name_ci(repository_database_url: str) -> None:
    repository = TagRepository(database_url=repository_database_url)

    created = repository.create(name="Bug")
    assert created.name == "Bug"

    with pytest.raises(UniqueViolation):
        repository.create(name="bug")

    updated = repository.update(tag_id=created.id, name="Defect")
    assert updated is not None
    assert updated.name == "Defect"

    listing = repository.list()
    assert len(listing) == 1
    assert listing[0].name == "Defect"

    deleted = repository.delete(created.id)
    assert deleted is True
    assert repository.get_by_id(created.id) is None


def test_ticket_tag_repository_replace_and_cascade(repository_database_url: str) -> None:
    ticket_repository = TicketRepository(database_url=repository_database_url)
    tag_repository = TagRepository(database_url=repository_database_url)
    ticket_tag_repository = TicketTagRepository(database_url=repository_database_url)

    ticket = ticket_repository.create(title="tag relation", description=None)
    tag1 = tag_repository.create(name="backend")
    tag2 = tag_repository.create(name="database")

    ticket_tag_repository.replace_tags(ticket_id=ticket.id, tag_ids=[tag1.id, tag2.id, tag2.id])
    assert ticket_tag_repository.list_tag_ids(ticket_id=ticket.id) == [tag1.id, tag2.id]

    removed = tag_repository.delete(tag1.id)
    assert removed is True
    assert ticket_tag_repository.list_tag_ids(ticket_id=ticket.id) == [tag2.id]


def test_ticket_repository_list_filtered(repository_database_url: str) -> None:
    ticket_repository = TicketRepository(database_url=repository_database_url)
    tag_repository = TagRepository(database_url=repository_database_url)
    ticket_tag_repository = TicketTagRepository(database_url=repository_database_url)

    tag_backend = tag_repository.create(name="backend")
    tag_frontend = tag_repository.create(name="frontend")

    t1 = ticket_repository.create(title="Deploy backend service", description="api")
    t2 = ticket_repository.create(title="Polish frontend page", description="ui")
    t3 = ticket_repository.create(
        title="Release checklist",
        description="ops",
        status="done",
        completed_at=datetime.now(UTC),
    )

    ticket_tag_repository.replace_tags(ticket_id=t1.id, tag_ids=[tag_backend.id])
    ticket_tag_repository.replace_tags(ticket_id=t2.id, tag_ids=[tag_frontend.id])
    ticket_tag_repository.replace_tags(ticket_id=t3.id, tag_ids=[tag_backend.id, tag_frontend.id])

    filtered_by_status, total_status = ticket_repository.list_filtered(
        tag_id=None,
        q=None,
        status="done",
        limit=20,
        offset=0,
    )
    assert total_status == 1
    assert [ticket.id for ticket in filtered_by_status] == [t3.id]

    filtered_by_search, total_search = ticket_repository.list_filtered(
        tag_id=None,
        q="frontend",
        status=None,
        limit=20,
        offset=0,
    )
    assert total_search == 1
    assert [ticket.id for ticket in filtered_by_search] == [t2.id]

    filtered_by_tag, total_tag = ticket_repository.list_filtered(
        tag_id=tag_backend.id,
        q=None,
        status=None,
        limit=20,
        offset=0,
    )
    assert total_tag == 2
    assert [ticket.id for ticket in filtered_by_tag] == [t3.id, t1.id]

    paged, total_paged = ticket_repository.list_filtered(
        tag_id=None,
        q=None,
        status=None,
        limit=2,
        offset=0,
    )
    assert total_paged == 3
    assert len(paged) == 2

    tag_map = ticket_tag_repository.list_tag_ids_by_ticket_ids(ticket_ids=[t1.id, t2.id, t3.id])
    assert tag_map[t1.id] == [tag_backend.id]
    assert tag_map[t2.id] == [tag_frontend.id]
    assert tag_map[t3.id] == [tag_backend.id, tag_frontend.id]
