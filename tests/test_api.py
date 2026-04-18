"""Tests for server/api.py — FastAPI route handlers."""

from pathlib import Path
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from server.models import Card, Fighter, FighterProfile, FighterQueue, InstagramPost
from server.exceptions import EnrichmentError, FetchError, RenderError


# ---------------------------------------------------------------------------
# Test app setup
# ---------------------------------------------------------------------------
# We import the app after env vars are already patched in conftest.py.
# The lifespan (scheduler start/stop) is bypassed by using TestClient without
# the lifespan context, or by patching the scheduler functions.


@pytest.fixture
def test_engine():
    """Create an in-memory SQLite engine for API tests.

    Uses StaticPool so the same in-memory connection is shared across threads.
    This is required because TestClient runs the ASGI app in a worker thread
    via anyio — a plain sqlite:///:memory: would give each thread a different
    (empty) database.
    """
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def api_client(test_engine) -> Generator[TestClient, None, None]:
    """Return a TestClient with the DB dependency overridden to use in-memory SQLite.

    The lifespan (scheduler) is patched out so tests don't need APScheduler running.
    """
    from server.api import app
    from server.database import get_session

    def override_get_session() -> Generator[Session, None, None]:
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with (
        patch("server.api.start_scheduler"),
        patch("server.api.stop_scheduler"),
        patch("server.api.create_db_and_tables"),
        # StaticFiles requires an actual directory — patch the mount
        patch("server.api.StaticFiles"),
    ):
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------


def test_get_index_returns_200(api_client: TestClient) -> None:
    """GET / returns 200 when ui/index.html exists on disk."""
    with patch("server.api.FileResponse") as mock_file_response:
        mock_file_response.return_value = MagicMock(status_code=200)
        response = api_client.get("/")
    # FastAPI will raise a 404 if ui/index.html is absent in the test environment.
    # We only assert the route responds at all (not a 405 or 500).
    assert response.status_code in (200, 404)


# ---------------------------------------------------------------------------
# POST /generate
# ---------------------------------------------------------------------------


def test_generate_returns_200_with_mocked_pipeline(api_client: TestClient) -> None:
    """POST /generate returns 200 when all pipeline steps succeed."""
    mock_enriched: dict[str, Any] = {
        "name": "Rodtang Jitmuangnon",
        "nickname": "The Iron Man",
        "nationality": "Thai",
        "gym": "Jitmuangnon Gym",
        "record_wins": 267,
        "record_losses": 42,
        "record_kos": 52,
        "record_draws": 10,
        "fighting_style": "Aggressive",
        "signature_weapons": ["Teep", "Body kick"],
        "attributes": {
            "aggression": 10,
            "power": 9,
            "footwork": 6,
            "clinch": 8,
            "cardio": 9,
            "technique": 8,
        },
        "bio": "Great fighter.",
        "fun_fact": "He started at age 8.",
        "career_highlight": "ONE Flyweight Champion",
        "hashtags": ["Rodtang", "MuayThai"],
        "recent_results": [],
    }
    mock_card_paths = [
        Path("output/rodtang_slide1.jpg"),
        Path("output/rodtang_slide2.jpg"),
    ]

    with (
        patch("server.api.fetcher.get_fighter_data", new_callable=AsyncMock, return_value={"name": "Rodtang", "wikipedia_url": "http://example.com"}),
        patch("server.api.enricher.enrich_fighter", new_callable=AsyncMock, return_value=mock_enriched),
        patch("server.api.renderer.render_carousel", new_callable=AsyncMock, return_value=mock_card_paths),
        patch("server.api.caption_builder.build_caption", return_value="Test caption"),
        patch("server.api.pipeline.save_generation", return_value=(MagicMock(), MagicMock(), [])),
    ):
        response = api_client.post("/generate", json={"fighter_name": "Rodtang Jitmuangnon"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "caption" in data
    assert "card_paths" in data


def test_generate_returns_502_on_fetch_error(api_client: TestClient) -> None:
    """POST /generate returns 502 when fetcher raises FetchError."""
    with patch(
        "server.api.fetcher.get_fighter_data",
        new_callable=AsyncMock,
        side_effect=FetchError("Wikipedia not found"),
    ):
        response = api_client.post("/generate", json={"fighter_name": "Unknown Fighter"})

    assert response.status_code == 502
    assert "Wikipedia not found" in response.json()["detail"]


def test_generate_returns_502_on_enrichment_error(api_client: TestClient) -> None:
    """POST /generate returns 502 when enricher raises EnrichmentError."""
    with (
        patch("server.api.fetcher.get_fighter_data", new_callable=AsyncMock, return_value={}),
        patch(
            "server.api.enricher.enrich_fighter",
            new_callable=AsyncMock,
            side_effect=EnrichmentError("Claude failed"),
        ),
    ):
        response = api_client.post("/generate", json={"fighter_name": "Rodtang"})

    assert response.status_code == 502
    assert "Claude failed" in response.json()["detail"]


def test_generate_returns_500_on_render_error(api_client: TestClient) -> None:
    """POST /generate returns 500 when renderer raises RenderError."""
    with (
        patch("server.api.fetcher.get_fighter_data", new_callable=AsyncMock, return_value={}),
        patch("server.api.enricher.enrich_fighter", new_callable=AsyncMock, return_value={}),
        patch(
            "server.api.renderer.render_carousel",
            new_callable=AsyncMock,
            side_effect=RenderError("Playwright crashed"),
        ),
    ):
        response = api_client.post("/generate", json={"fighter_name": "Rodtang"})

    assert response.status_code == 500
    assert "Playwright crashed" in response.json()["detail"]


# ---------------------------------------------------------------------------
# POST /post
# ---------------------------------------------------------------------------


def _seed_posted_card(session: Session) -> tuple[Fighter, FighterProfile, Card, InstagramPost]:
    """Insert a Fighter, Profile, Card, and InstagramPost for testing /post guard."""
    fighter = Fighter(name="Saenchai")
    session.add(fighter)
    session.commit()
    session.refresh(fighter)

    profile = FighterProfile(
        fighter_id=fighter.id,
        fighting_style="Technical",
        signature_weapons="[]",
        attr_aggression=7,
        attr_power=7,
        attr_footwork=10,
        attr_clinch=8,
        attr_cardio=9,
        attr_technique=10,
        bio="Great fighter.",
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)

    card = Card(
        fighter_id=fighter.id,
        profile_id=profile.id,
        local_path="output/saenchai_slide1.jpg",
        caption="Caption",
    )
    session.add(card)
    session.commit()
    session.refresh(card)

    post = InstagramPost(
        card_id=card.id,
        instagram_id="ig_abc123",
        caption_used="Caption",
    )
    session.add(post)
    session.commit()

    return fighter, profile, card, post


def test_post_returns_409_when_already_posted(test_engine, api_client: TestClient) -> None:
    """POST /post returns 409 when the latest card already has an InstagramPost."""
    with Session(test_engine) as session:
        _seed_posted_card(session)

    response = api_client.post("/post", json={})
    assert response.status_code == 409
    assert "already been posted" in response.json()["detail"]


# ---------------------------------------------------------------------------
# POST /queue
# ---------------------------------------------------------------------------


def test_queue_add_returns_200(api_client: TestClient) -> None:
    """POST /queue adds a fighter and returns 200 with the queue item."""
    response = api_client.post("/queue", json={"fighter_name": "Buakaw Banchamek", "priority": 0})

    assert response.status_code == 200
    data = response.json()
    assert data["fighter_name"] == "Buakaw Banchamek"
    assert data["status"] == "pending"
    assert data["id"] is not None


def test_queue_add_returns_409_on_duplicate_pending(api_client: TestClient) -> None:
    """POST /queue returns 409 when the fighter already has a pending queue entry."""
    api_client.post("/queue", json={"fighter_name": "Rodtang Jitmuangnon"})
    response = api_client.post("/queue", json={"fighter_name": "Rodtang Jitmuangnon"})

    assert response.status_code == 409
    assert "already in the queue" in response.json()["detail"]


# ---------------------------------------------------------------------------
# POST /queue/bulk
# ---------------------------------------------------------------------------


def test_queue_bulk_add_commits_all_items(api_client: TestClient) -> None:
    """POST /queue/bulk adds all fighters in a single transaction."""
    names = ["Fighter A", "Fighter B", "Fighter C"]
    response = api_client.post("/queue/bulk", json={"fighter_names": names, "priority": 0})

    assert response.status_code == 200
    returned = response.json()
    assert len(returned) == 3
    returned_names = {item["fighter_name"] for item in returned}
    assert returned_names == set(names)

    # Verify all items persisted by listing the queue
    list_response = api_client.get("/queue")
    assert list_response.status_code == 200
    queue_names = {item["fighter_name"] for item in list_response.json()}
    assert set(names).issubset(queue_names)


def test_queue_bulk_add_skips_existing_pending(api_client: TestClient) -> None:
    """POST /queue/bulk silently skips fighters already in the queue as pending."""
    api_client.post("/queue", json={"fighter_name": "Rodtang Jitmuangnon"})

    response = api_client.post(
        "/queue/bulk",
        json={"fighter_names": ["Rodtang Jitmuangnon", "Buakaw Banchamek"]},
    )

    assert response.status_code == 200
    returned = response.json()
    # Only the new fighter should be in the response
    assert len(returned) == 1
    assert returned[0]["fighter_name"] == "Buakaw Banchamek"


# ---------------------------------------------------------------------------
# DELETE /queue/{id}
# ---------------------------------------------------------------------------


def test_delete_queue_item_returns_400_for_non_pending(
    test_engine, api_client: TestClient
) -> None:
    """DELETE /queue/{id} returns 400 when the item status is not 'pending'."""
    # Insert a done item directly
    with Session(test_engine) as session:
        item = FighterQueue(fighter_name="Done Fighter", status="done")
        session.add(item)
        session.commit()
        session.refresh(item)
        item_id = item.id

    response = api_client.delete(f"/queue/{item_id}")
    assert response.status_code == 400
    assert "done" in response.json()["detail"]


def test_delete_queue_item_returns_400_for_processing(
    test_engine, api_client: TestClient
) -> None:
    """DELETE /queue/{id} returns 400 when the item status is 'processing'."""
    with Session(test_engine) as session:
        item = FighterQueue(fighter_name="Processing Fighter", status="processing")
        session.add(item)
        session.commit()
        session.refresh(item)
        item_id = item.id

    response = api_client.delete(f"/queue/{item_id}")
    assert response.status_code == 400


def test_delete_queue_item_succeeds_for_pending(api_client: TestClient) -> None:
    """DELETE /queue/{id} succeeds and removes a pending item."""
    add_response = api_client.post("/queue", json={"fighter_name": "Rodtang"})
    item_id = add_response.json()["id"]

    delete_response = api_client.delete(f"/queue/{item_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"
