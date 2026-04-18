"""Tests for server/service/wiki/wiki_searcher.py — WikiSearcher."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from server.exceptions import FetchError
from server.service.wiki.wiki_searcher import WikiSearcher


def _make_response(status_code: int, json_data: dict[str, Any]) -> MagicMock:
    """Build a mock httpx.Response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data
    return response


def _search_response(title: str, pageid: int) -> dict[str, Any]:
    """Build a minimal Wikipedia search API response body."""
    return {
        "query": {
            "search": [
                {"title": title, "pageid": pageid, "snippet": "..."}
            ]
        }
    }


@pytest.mark.asyncio
async def test_init_raises_on_empty_string() -> None:
    """ValueError is raised when fighter_name is an empty string."""
    with pytest.raises(ValueError):
        WikiSearcher("")


@pytest.mark.asyncio
async def test_init_raises_on_whitespace_only() -> None:
    """ValueError is raised when fighter_name is only whitespace."""
    with pytest.raises(ValueError):
        WikiSearcher("   ")


@pytest.mark.asyncio
async def test_do_wiki_search_raises_fetch_error_on_non_200() -> None:
    """FetchError is raised when Wikipedia returns a non-200 status code."""
    mock_response = _make_response(500, {})

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        searcher = WikiSearcher("Rodtang Jitmuangnon")
        with pytest.raises(FetchError, match="500"):
            await searcher.do_wiki_search()


@pytest.mark.asyncio
async def test_do_wiki_search_raises_fetch_error_when_results_empty() -> None:
    """FetchError is raised when the search results list is empty."""
    mock_response = _make_response(200, {"query": {"search": []}})

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        searcher = WikiSearcher("Rodtang Jitmuangnon")
        with pytest.raises(FetchError, match="No Wikipedia article"):
            await searcher.do_wiki_search()


@pytest.mark.asyncio
async def test_do_wiki_search_raises_fetch_error_when_title_has_no_matching_word() -> None:
    """FetchError is raised when no word from the fighter name appears in the result title."""
    # "Rodtang Jitmuangnon" — meaningful words are "Rodtang" and "Jitmuangnon"
    # The returned title contains neither
    mock_response = _make_response(200, _search_response("Completely Unrelated Article", 99999))

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        searcher = WikiSearcher("Rodtang Jitmuangnon")
        with pytest.raises(FetchError, match="No relevant"):
            await searcher.do_wiki_search()


@pytest.mark.asyncio
async def test_do_wiki_search_succeeds_when_name_word_in_title() -> None:
    """Returns title and page_id when at least one meaningful name word is in the title."""
    mock_response = _make_response(200, _search_response("Rodtang Jitmuangnon", 60654920))

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        searcher = WikiSearcher("Rodtang Jitmuangnon")
        result = await searcher.do_wiki_search()

    assert result["title"] == "Rodtang Jitmuangnon"
    assert result["page_id"] == 60654920


@pytest.mark.asyncio
async def test_do_wiki_search_returns_title_and_page_id_keys() -> None:
    """The result dict has exactly the 'title' and 'page_id' keys."""
    mock_response = _make_response(200, _search_response("Buakaw Banchamek", 12345))

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        searcher = WikiSearcher("Buakaw Banchamek")
        result = await searcher.do_wiki_search()

    assert "title" in result
    assert "page_id" in result


@pytest.mark.asyncio
async def test_do_wiki_search_partial_name_match_succeeds() -> None:
    """Succeeds when only one word from the fighter name matches the article title."""
    # "Buakaw" is in the title; "Banchamek" is not — still a valid match
    mock_response = _make_response(200, _search_response("Buakaw Por Pramuk", 11111))

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        searcher = WikiSearcher("Buakaw Banchamek")
        result = await searcher.do_wiki_search()

    assert result["title"] == "Buakaw Por Pramuk"


@pytest.mark.asyncio
async def test_do_wiki_search_raises_on_network_error() -> None:
    """FetchError is raised when httpx raises a RequestError (network failure)."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        searcher = WikiSearcher("Rodtang Jitmuangnon")
        with pytest.raises(FetchError, match="Network error"):
            await searcher.do_wiki_search()
