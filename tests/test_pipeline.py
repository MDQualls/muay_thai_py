"""Tests for server/pipeline.py — save_generation() with an in-memory SQLite DB."""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlmodel import Session, select

from server.models import Card, Fighter, FighterProfile
from server.pipeline import save_generation


def test_save_generation_creates_new_fighter_row(
    db_session: Session,
    raw_data: dict[str, Any],
    enriched_data: dict[str, Any],
    card_paths: list[Path],
) -> None:
    """A Fighter row is created when no Fighter with that name exists."""
    fighter, _profile, _cards = save_generation(
        db_session, raw_data, enriched_data, card_paths, "Test caption"
    )

    assert fighter.id is not None
    assert fighter.name == enriched_data["name"]


def test_save_generation_updates_existing_fighter_row(
    db_session: Session,
    raw_data: dict[str, Any],
    enriched_data: dict[str, Any],
    card_paths: list[Path],
) -> None:
    """A second call with the same fighter name updates the existing row, not inserts."""
    save_generation(db_session, raw_data, enriched_data, card_paths, "Caption 1")
    fighters_after_first = db_session.exec(select(Fighter)).all()
    assert len(fighters_after_first) == 1
    first_id = fighters_after_first[0].id

    # Update the enriched data with new values
    updated_enriched = {**enriched_data, "nickname": "The New Nickname", "record_wins": 300}
    save_generation(db_session, raw_data, updated_enriched, card_paths, "Caption 2")

    fighters_after_second = db_session.exec(select(Fighter)).all()
    assert len(fighters_after_second) == 1
    assert fighters_after_second[0].id == first_id
    assert fighters_after_second[0].nickname == "The New Nickname"
    assert fighters_after_second[0].record_wins == 300


def test_save_generation_creates_fighter_profile_row(
    db_session: Session,
    raw_data: dict[str, Any],
    enriched_data: dict[str, Any],
    card_paths: list[Path],
) -> None:
    """A FighterProfile row is created and linked to the Fighter."""
    fighter, profile, _cards = save_generation(
        db_session, raw_data, enriched_data, card_paths, "Caption"
    )

    assert profile.id is not None
    assert profile.fighter_id == fighter.id
    assert profile.bio == enriched_data["bio"]
    assert profile.attr_aggression == enriched_data["attributes"]["aggression"]


def test_save_generation_creates_card_rows(
    db_session: Session,
    raw_data: dict[str, Any],
    enriched_data: dict[str, Any],
    card_paths: list[Path],
) -> None:
    """One Card row per path in card_paths is created, all linked to fighter and profile."""
    fighter, profile, cards = save_generation(
        db_session, raw_data, enriched_data, card_paths, "Caption"
    )

    assert len(cards) == len(card_paths)
    for card, path in zip(cards, card_paths):
        assert card.id is not None
        assert card.fighter_id == fighter.id
        assert card.profile_id == profile.id
        assert card.local_path == str(path)
        assert card.caption == "Caption"


def test_save_generation_returns_valid_ids_after_commit(
    db_session: Session,
    raw_data: dict[str, Any],
    enriched_data: dict[str, Any],
    card_paths: list[Path],
) -> None:
    """All returned objects have non-None IDs (session.refresh() was called)."""
    fighter, profile, cards = save_generation(
        db_session, raw_data, enriched_data, card_paths, "Caption"
    )

    assert fighter.id is not None
    assert profile.id is not None
    for card in cards:
        assert card.id is not None


def test_save_generation_returns_tuple_types(
    db_session: Session,
    raw_data: dict[str, Any],
    enriched_data: dict[str, Any],
    card_paths: list[Path],
) -> None:
    """Return value is (Fighter, FighterProfile, list[Card])."""
    result = save_generation(db_session, raw_data, enriched_data, card_paths, "Caption")

    assert isinstance(result, tuple)
    assert len(result) == 3
    fighter, profile, cards = result
    assert isinstance(fighter, Fighter)
    assert isinstance(profile, FighterProfile)
    assert isinstance(cards, list)
    assert all(isinstance(c, Card) for c in cards)


def test_save_generation_stores_signature_weapons_as_json(
    db_session: Session,
    raw_data: dict[str, Any],
    enriched_data: dict[str, Any],
    card_paths: list[Path],
) -> None:
    """signature_weapons is stored as a JSON string and round-trips correctly."""
    _fighter, profile, _cards = save_generation(
        db_session, raw_data, enriched_data, card_paths, "Caption"
    )

    decoded = json.loads(profile.signature_weapons)
    assert decoded == enriched_data["signature_weapons"]


def test_save_generation_two_calls_create_two_profiles(
    db_session: Session,
    raw_data: dict[str, Any],
    enriched_data: dict[str, Any],
    card_paths: list[Path],
) -> None:
    """Each call to save_generation inserts a new FighterProfile row."""
    save_generation(db_session, raw_data, enriched_data, card_paths, "Caption 1")
    save_generation(db_session, raw_data, enriched_data, card_paths, "Caption 2")

    profiles = db_session.exec(select(FighterProfile)).all()
    assert len(profiles) == 2
