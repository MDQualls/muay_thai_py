import asyncio
import logging

import httpx

from server.config import settings
from server.exceptions import PublishError

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v25.0"
POLL_INTERVAL_SECONDS = 2.0
MAX_POLL_ATTEMPTS = 15  # 15 × 2s = 30s max wait per container


async def post_carousel(image_urls: list[str], caption: str) -> str:
    """Post an image to Instagram via the Meta Graph API.

    Args:
        image_urls: List of public URLs to the carousel slide images (3 items)
        caption: Instagram caption text

    Returns:
        str Instagram post ID returned by the Graph API
    """
    logger.info("Posting to Instagram")

    media_url = f"{GRAPH_API_BASE}/{settings.meta_instagram_account_id}/media"
    publish_url = f"{GRAPH_API_BASE}/{settings.meta_instagram_account_id}/media_publish"

    # Token is sent in the Authorization header — never in the URL — to keep it
    # out of proxy logs and HTTP access logs.
    auth_headers = {"Authorization": f"Bearer {settings.meta_access_token}"}

    async with httpx.AsyncClient(timeout=30.0, headers=auth_headers) as client:

        # Step 1 — item containers
        containers = []
        for image_url in image_urls:
            data = await _post(client, media_url, {
                "image_url": image_url,
                "is_carousel_item": "true",
            }, error_context="item container")
            container_id = data["id"]
            logger.info("Created item container: %s", container_id)
            await _wait_for_container(client, container_id)
            containers.append(container_id)

        # Step 2 — carousel container
        data = await _post(client, media_url, {
            "media_type": "CAROUSEL",
            "children": ",".join(containers),
            "caption": caption,
        }, error_context="carousel container")
        carousel_id = data["id"]
        logger.info("Created carousel container: %s", carousel_id)
        await _wait_for_container(client, carousel_id)

        # Step 3 — publish
        data = await _post(client, publish_url, {
            "creation_id": carousel_id,
        }, error_context="publish")
        logger.info("Published carousel post: %s", data["id"])

    return data["id"]


async def _wait_for_container(
    client: httpx.AsyncClient,
    container_id: str,
) -> None:
    """Poll the Graph API until a media container reaches FINISHED status.

    Args:
        client: Shared httpx async client.
        container_id: The Media Container ID returned by a previous creation call.

    Raises:
        PublishError: If the container enters an error state or times out.
    """
    url = f"{GRAPH_API_BASE}/{container_id}"
    params = {"fields": "status_code,status"}

    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        response = await client.get(url, params=params)
        data = response.json()

        if response.status_code != 200 or "error" in data:
            raise PublishError(f"Container status check failed for {container_id}: {data}")

        status_code = data.get("status_code")
        logger.info(
            "Container %s: %s (attempt %d/%d)",
            container_id, status_code, attempt, MAX_POLL_ATTEMPTS,
        )

        if status_code == "FINISHED":
            return
        if status_code in ("ERROR", "EXPIRED"):
            raise PublishError(
                f"Container {container_id} failed with status {status_code}: {data.get('status')}"
            )

        await asyncio.sleep(POLL_INTERVAL_SECONDS)

    raise PublishError(
        f"Container {container_id} did not reach FINISHED after {MAX_POLL_ATTEMPTS} attempts"
    )


async def _post(
        client: httpx.AsyncClient,
        url: str,
        data: dict,
        error_context: str,
    ) -> dict:
    """Make a single authenticated POST to the Graph API and validate the response."""
    response = await client.post(url, data=data)
    result = response.json()

    if response.status_code != 200:
        raise PublishError(f"Graph API returned {response.status_code} ({error_context}): {result}")
    if "error" in result:
        raise PublishError(f"Graph API error ({error_context}): {result['error']['message']}")
    if "id" not in result:
        raise PublishError(f"Graph API returned no ID ({error_context}): {result}")

    return result
