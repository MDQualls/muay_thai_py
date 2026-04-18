"""Tests for server/enricher.py — enrich_fighter()."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.exceptions import EnrichmentError


def _make_mock_message(text: str) -> MagicMock:
    """Build a mock anthropic.types.Message whose content[0].text returns text."""
    content_block = MagicMock()
    content_block.text = text
    message = MagicMock()
    message.content = [content_block]
    return message


def _valid_claude_response_text(overrides: dict[str, Any] | None = None) -> str:
    """Return a valid JSON string matching the enricher's expected schema."""
    payload: dict[str, Any] = {
        "name": "Rodtang Jitmuangnon",
        "nickname": "The Iron Man",
        "nationality": "Thai",
        "gym": "Jitmuangnon Gym",
        "record_wins": 267,
        "record_losses": 42,
        "record_kos": 52,
        "fighting_style": "Aggressive pressure fighter",
        "signature_weapons": ["Teep", "Body kick", "Elbow"],
        "attributes": {
            "aggression": 10,
            "power": 9,
            "footwork": 6,
            "clinch": 8,
            "cardio": 9,
            "technique": 8,
        },
        "bio": "Great fighter. Very tough. Always wins.",
        "fun_fact": "He started training at age eight.",
        "career_highlight": "Reigning ONE Flyweight Champion",
        "hashtags": ["Rodtang", "MuayThai"],
    }
    if overrides:
        payload.update(overrides)
    return json.dumps(payload)


@pytest.mark.asyncio
async def test_enrich_fighter_raises_when_extract_empty(raw_data: dict[str, Any]) -> None:
    """EnrichmentError is raised immediately when wikipedia_extract is missing."""
    raw_data["wikipedia_extract"] = ""

    from server import enricher

    with pytest.raises(EnrichmentError, match="Wikipedia content"):
        await enricher.enrich_fighter(raw_data)


@pytest.mark.asyncio
async def test_enrich_fighter_raises_when_extract_missing(raw_data: dict[str, Any]) -> None:
    """EnrichmentError is raised when wikipedia_extract key is absent."""
    del raw_data["wikipedia_extract"]

    from server import enricher

    with pytest.raises(EnrichmentError):
        await enricher.enrich_fighter(raw_data)


@pytest.mark.asyncio
async def test_enrich_fighter_parses_valid_response(raw_data: dict[str, Any]) -> None:
    """A valid JSON Claude response is parsed into the expected dict structure."""
    mock_message = _make_mock_message(_valid_claude_response_text())

    with patch(
        "server.enricher.EnrichmentHandler",
        return_value=MagicMock(enrich=AsyncMock(return_value=mock_message)),
    ):
        from server import enricher

        result = await enricher.enrich_fighter(raw_data)

    assert result["name"] == "Rodtang Jitmuangnon"
    assert result["fighting_style"] == "Aggressive pressure fighter"
    assert isinstance(result["attributes"], dict)
    assert result["attributes"]["aggression"] == 10
    assert isinstance(result["signature_weapons"], list)
    assert result["bio"] == "Great fighter. Very tough. Always wins."


@pytest.mark.asyncio
async def test_enrich_fighter_applies_wiki_nickname_fallback(raw_data: dict[str, Any]) -> None:
    """When Claude returns null nickname, the wiki_nickname is used instead."""
    response_text = _valid_claude_response_text({"nickname": None})
    raw_data["wiki_nickname"] = "The Iron Man"
    mock_message = _make_mock_message(response_text)

    with patch(
        "server.enricher.EnrichmentHandler",
        return_value=MagicMock(enrich=AsyncMock(return_value=mock_message)),
    ):
        from server import enricher

        result = await enricher.enrich_fighter(raw_data)

    assert result["nickname"] == "The Iron Man"


@pytest.mark.asyncio
async def test_enrich_fighter_applies_wiki_wins_fallback(raw_data: dict[str, Any]) -> None:
    """When Claude returns null record_wins, wiki_wins is used as fallback."""
    response_text = _valid_claude_response_text({"record_wins": None})
    raw_data["wiki_wins"] = 267
    mock_message = _make_mock_message(response_text)

    with patch(
        "server.enricher.EnrichmentHandler",
        return_value=MagicMock(enrich=AsyncMock(return_value=mock_message)),
    ):
        from server import enricher

        result = await enricher.enrich_fighter(raw_data)

    assert result["record_wins"] == 267


@pytest.mark.asyncio
async def test_enrich_fighter_applies_wiki_losses_fallback(raw_data: dict[str, Any]) -> None:
    """When Claude returns null record_losses, wiki_losses is used as fallback."""
    response_text = _valid_claude_response_text({"record_losses": None})
    raw_data["wiki_losses"] = 42
    mock_message = _make_mock_message(response_text)

    with patch(
        "server.enricher.EnrichmentHandler",
        return_value=MagicMock(enrich=AsyncMock(return_value=mock_message)),
    ):
        from server import enricher

        result = await enricher.enrich_fighter(raw_data)

    assert result["record_losses"] == 42


@pytest.mark.asyncio
async def test_enrich_fighter_always_uses_wiki_draws(raw_data: dict[str, Any]) -> None:
    """record_draws is always sourced from wiki_draws, regardless of Claude output."""
    response_text = _valid_claude_response_text({"record_draws": 999})
    raw_data["wiki_draws"] = 10
    mock_message = _make_mock_message(response_text)

    with patch(
        "server.enricher.EnrichmentHandler",
        return_value=MagicMock(enrich=AsyncMock(return_value=mock_message)),
    ):
        from server import enricher

        result = await enricher.enrich_fighter(raw_data)

    assert result["record_draws"] == 10


@pytest.mark.asyncio
async def test_enrich_fighter_attaches_recent_results(raw_data: dict[str, Any]) -> None:
    """recent_results from raw_data are attached to the enriched output."""
    mock_message = _make_mock_message(_valid_claude_response_text())

    with patch(
        "server.enricher.EnrichmentHandler",
        return_value=MagicMock(enrich=AsyncMock(return_value=mock_message)),
    ):
        from server import enricher

        result = await enricher.enrich_fighter(raw_data)

    assert result["recent_results"] == raw_data["recent_results"]


@pytest.mark.asyncio
async def test_enrich_fighter_raises_on_invalid_json(raw_data: dict[str, Any]) -> None:
    """EnrichmentError is raised when Claude returns non-JSON text."""
    mock_message = _make_mock_message("This is not JSON at all!")

    with patch(
        "server.enricher.EnrichmentHandler",
        return_value=MagicMock(enrich=AsyncMock(return_value=mock_message)),
    ):
        from server import enricher

        with pytest.raises(EnrichmentError, match="invalid JSON"):
            await enricher.enrich_fighter(raw_data)


@pytest.mark.asyncio
async def test_enrich_fighter_strips_markdown_fences(raw_data: dict[str, Any]) -> None:
    """Markdown code fences around JSON are stripped before parsing."""
    wrapped = "```json\n" + _valid_claude_response_text() + "\n```"
    mock_message = _make_mock_message(wrapped)

    with patch(
        "server.enricher.EnrichmentHandler",
        return_value=MagicMock(enrich=AsyncMock(return_value=mock_message)),
    ):
        from server import enricher

        result = await enricher.enrich_fighter(raw_data)

    assert result["name"] == "Rodtang Jitmuangnon"
