"""Shared pytest fixtures for the Muay Thai Fighter Card App test suite.

Environment variables are set before any server module is imported so that
pydantic-settings does not raise a validation error for missing required fields.
"""

import os

# ---------------------------------------------------------------------------
# Patch environment before ANY server import — pydantic-settings reads env at
# class-body evaluation time, so these must be set first.
# ---------------------------------------------------------------------------
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("META_ACCESS_TOKEN", "test-meta-token")
os.environ.setdefault("META_INSTAGRAM_ACCOUNT_ID", "test-ig-account")
os.environ.setdefault("R2_ACCESS_KEY_ID", "test-r2-key-id")
os.environ.setdefault("R2_SECRET_ACCESS_KEY", "test-r2-secret")
os.environ.setdefault("R2_BUCKET_NAME", "test-bucket")
os.environ.setdefault("R2_PUBLIC_URL", "https://cdn.test.example.com")
os.environ.setdefault("R2_ENDPOINT_URL", "https://r2.test.example.com")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine

from server import models  # noqa: F401 — registers all table metadata


# ---------------------------------------------------------------------------
# In-memory SQLite database
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session() -> Session:
    """Yield a fresh in-memory SQLite session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# Sample raw_data fixture — matches the shape returned by fetcher.get_fighter_data()
# ---------------------------------------------------------------------------


@pytest.fixture
def raw_data() -> dict:
    return {
        "name": "Rodtang Jitmuangnon",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Rodtang_Jitmuangnon",
        "wikipedia_extract": (
            "Rodtang Jitmuangnon is a Thai professional Muay Thai fighter. "
            "He is the reigning ONE Flyweight Muay Thai World Champion. "
            "Known for his aggressive style and iron chin, he rarely steps back. "
            "His nickname is The Iron Man. He has 267 wins, 42 losses, and 10 draws. "
            "Record KOs: 52."
        ),
        "wiki_nickname": "The Iron Man",
        "wiki_wins": 267,
        "wiki_losses": 42,
        "wiki_draws": 10,
        "recent_results": [
            {"opponent": "Superlek", "result": "W", "method": "Decision"},
            {"opponent": "Haggerty", "result": "W", "method": "KO"},
        ],
    }


# ---------------------------------------------------------------------------
# Sample enriched_data fixture — matches the shape returned by enricher.enrich_fighter()
# ---------------------------------------------------------------------------


@pytest.fixture
def enriched_data() -> dict:
    return {
        "name": "Rodtang Jitmuangnon",
        "nickname": "The Iron Man",
        "nationality": "Thai",
        "gym": "Jitmuangnon Gym",
        "record_wins": 267,
        "record_losses": 42,
        "record_kos": 52,
        "record_draws": 10,
        "fighting_style": "Aggressive pressure fighter with elite forward march",
        "signature_weapons": ["Teep", "Body kick", "Elbow", "Iron chin counter"],
        "attributes": {
            "aggression": 10,
            "power": 9,
            "footwork": 6,
            "clinch": 8,
            "cardio": 9,
            "technique": 8,
        },
        "bio": (
            "Rodtang Jitmuangnon is one of the most feared strikers in ONE Championship. "
            "He has defended the flyweight Muay Thai title multiple times against elite opposition. "
            "His relentless forward pressure and granite chin have made him a fan favourite worldwide."
        ),
        "fun_fact": "Rodtang began training at age eight and turned professional before his fourteenth birthday.",
        "career_highlight": "Reigning ONE Flyweight Muay Thai Champion",
        "hashtags": ["Rodtang", "MuayThai", "ONEChampionship", "JitmuangnongGym", "ThaiBoxing"],
        "recent_results": [
            {"opponent": "Superlek", "result": "W", "method": "Decision"},
            {"opponent": "Haggerty", "result": "W", "method": "KO"},
        ],
    }


# ---------------------------------------------------------------------------
# Sample card paths
# ---------------------------------------------------------------------------


@pytest.fixture
def card_paths() -> list[Path]:
    return [
        Path("output/rodtang_jitmuangnon_20240101_120000_000000_slide1.jpg"),
        Path("output/rodtang_jitmuangnon_20240101_120000_000001_slide2.jpg"),
        Path("output/rodtang_jitmuangnon_20240101_120000_000002_slide3.jpg"),
    ]
