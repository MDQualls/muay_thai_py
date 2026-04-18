"""Tests for server/publisher.py — _post() helper function."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from server.exceptions import PublishError
from server.publisher import _post


def _make_client_with_response(status_code: int, json_data: dict[str, Any]) -> MagicMock:
    """Build a mock httpx.AsyncClient whose post() returns the given status and body."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data

    client = MagicMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_post_raises_publish_error_on_non_200() -> None:
    """PublishError is raised when the Graph API returns a non-200 status code."""
    client = _make_client_with_response(400, {"message": "Bad Request"})

    with pytest.raises(PublishError, match="400"):
        await _post(client, "https://graph.example.com/media", {}, "item container")


@pytest.mark.asyncio
async def test_post_raises_publish_error_on_403() -> None:
    """PublishError is raised on 403 Forbidden (e.g. expired token)."""
    client = _make_client_with_response(403, {"error": {"message": "Invalid OAuth token"}})

    with pytest.raises(PublishError):
        await _post(client, "https://graph.example.com/media", {}, "item container")


@pytest.mark.asyncio
async def test_post_raises_publish_error_when_response_has_error_key() -> None:
    """PublishError is raised when the response body contains an 'error' key."""
    client = _make_client_with_response(
        200,
        {"error": {"message": "Invalid parameter", "code": 100}},
    )

    with pytest.raises(PublishError, match="Invalid parameter"):
        await _post(client, "https://graph.example.com/media", {}, "carousel container")


@pytest.mark.asyncio
async def test_post_raises_publish_error_when_id_key_missing() -> None:
    """PublishError is raised when the 200 response body has no 'id' key."""
    client = _make_client_with_response(200, {"status": "ok"})  # no "id"

    with pytest.raises(PublishError, match="no ID"):
        await _post(client, "https://graph.example.com/media_publish", {}, "publish")


@pytest.mark.asyncio
async def test_post_returns_result_dict_on_success() -> None:
    """Returns the response dict when the API responds 200 with an 'id' key."""
    expected = {"id": "17896795336362831"}
    client = _make_client_with_response(200, expected)

    result = await _post(client, "https://graph.example.com/media_publish", {}, "publish")

    assert result == expected
    assert result["id"] == "17896795336362831"


@pytest.mark.asyncio
async def test_post_passes_data_to_client_post() -> None:
    """The data payload is forwarded to client.post() unchanged."""
    expected_response = {"id": "abc123"}
    client = _make_client_with_response(200, expected_response)

    payload = {"image_url": "https://cdn.example.com/card.jpg", "is_carousel_item": "true"}
    url = "https://graph.example.com/12345/media"

    await _post(client, url, payload, "item container")

    client.post.assert_called_once_with(url, data=payload)


@pytest.mark.asyncio
async def test_post_error_context_appears_in_publish_error_message() -> None:
    """The error_context label appears in the PublishError message."""
    client = _make_client_with_response(500, {})

    with pytest.raises(PublishError, match="carousel container"):
        await _post(client, "https://graph.example.com/media", {}, "carousel container")
