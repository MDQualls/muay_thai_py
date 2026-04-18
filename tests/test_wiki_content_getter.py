"""Tests for server/service/wiki/wiki_content_getter.py — WikiContentGetter."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from server.exceptions import FetchError
from server.service.wiki.wiki_content_getter import WikiContentGetter


def _make_response(status_code: int, json_data: dict[str, Any]) -> MagicMock:
    """Build a mock httpx.Response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data
    return response


def _content_response(pageid: int, extract: str) -> dict[str, Any]:
    """Build a minimal Wikipedia content API response body."""
    return {
        "query": {
            "pages": {
                str(pageid): {
                    "pageid": pageid,
                    "title": "Test Fighter",
                    "extract": extract,
                }
            }
        }
    }


VALID_WIKI_DATA: dict[str, Any] = {
    "title": "Rodtang Jitmuangnon",
    "page_id": 60654920,
}


def test_init_raises_on_empty_dict() -> None:
    """FetchError is raised when wiki_data is an empty dict."""
    with pytest.raises(FetchError, match="Empty wiki_data"):
        WikiContentGetter({})


def test_init_raises_on_none() -> None:
    """FetchError is raised when wiki_data is falsy (None)."""
    with pytest.raises(FetchError):
        WikiContentGetter(None)  # type: ignore[arg-type]


def test_init_succeeds_with_valid_data() -> None:
    """WikiContentGetter instantiates without error when given valid wiki_data."""
    getter = WikiContentGetter(VALID_WIKI_DATA)
    assert getter.wiki_data == VALID_WIKI_DATA


@pytest.mark.asyncio
async def test_get_wiki_content_raises_when_pageid_missing() -> None:
    """FetchError is raised when wiki_data has no 'page_id' key."""
    getter = WikiContentGetter({"title": "Some Fighter"})
    with pytest.raises(FetchError, match="pageid"):
        await getter.get_wiki_content()


@pytest.mark.asyncio
async def test_get_wiki_content_raises_on_non_200() -> None:
    """FetchError is raised when Wikipedia returns a non-200 status code."""
    mock_response = _make_response(503, {})

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        getter = WikiContentGetter(VALID_WIKI_DATA)
        with pytest.raises(FetchError, match="503"):
            await getter.get_wiki_content()


@pytest.mark.asyncio
async def test_get_wiki_content_raises_when_extract_empty() -> None:
    """FetchError is raised when the page extract is an empty string."""
    mock_response = _make_response(200, _content_response(60654920, ""))

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        getter = WikiContentGetter(VALID_WIKI_DATA)
        with pytest.raises(FetchError, match="No content"):
            await getter.get_wiki_content()


@pytest.mark.asyncio
async def test_get_wiki_content_returns_merged_dict_with_content_key() -> None:
    """On success, result merges original wiki_data with a 'content' key."""
    extract_text = "Rodtang is a world champion Muay Thai fighter from Thailand."
    mock_response = _make_response(200, _content_response(60654920, extract_text))

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        getter = WikiContentGetter(VALID_WIKI_DATA)
        result = await getter.get_wiki_content()

    assert "content" in result
    assert result["content"] == extract_text
    assert result["title"] == VALID_WIKI_DATA["title"]
    assert result["page_id"] == VALID_WIKI_DATA["page_id"]


@pytest.mark.asyncio
async def test_get_wiki_content_raises_on_network_error() -> None:
    """FetchError is raised when httpx raises a RequestError."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        getter = WikiContentGetter(VALID_WIKI_DATA)
        with pytest.raises(FetchError, match="Network error"):
            await getter.get_wiki_content()
