import logging
import httpx
from server.config import settings
from server.exceptions import PublishError
import asyncio

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v25.0"


async def post_carousel(image_urls: list[str], caption: str) -> str:
    """Post an image to Instagram via the Meta Graph API.

    Args:
        iimage_urls: List of public URLs to the carousel slide images (3 items)
        caption: Instagram caption text

    Returns:
        str Instagram post ID returned by the Graph API
    """
    logger.info("Posting to Instagram")

    media_url = f"{GRAPH_API_BASE}/{settings.meta_instagram_account_id}/media"
    publish_url = f"{GRAPH_API_BASE}/{settings.meta_instagram_account_id}/media_publish"

    async with httpx.AsyncClient() as client:

        # Step 1 — item containers
        containers = []
        for image_url in image_urls:
            data = await _post(client, media_url, {
                "image_url": image_url,
                "is_carousel_item": "true",
                "access_token": settings.meta_access_token,
            }, error_context="item container")
            containers.append(data["id"])
            logger.info("Created item container: %s", data["id"])

        await asyncio.sleep(5)

        # Step 2 — carousel container
        data = await _post(client, media_url, {
            "media_type": "CAROUSEL",
            "children": ",".join(containers),
            "caption": caption,
            "access_token": settings.meta_access_token,
        }, error_context="carousel container")
        carousel_id = data["id"]
        logger.info("Created carousel container: %s", carousel_id)

        await asyncio.sleep(5)

        # Step 3 — publish
        data = await _post(client, publish_url, {
            "creation_id": carousel_id,
            "access_token": settings.meta_access_token,
        }, error_context="publish")
        logger.info("Published carousel post: %s", data["id"])

    return data["id"]


async def _post(
        client: httpx.AsyncClient,
        url: str,
        params: dict,
        error_context: str,
    ) -> dict:

    """Make a single authenticated POST to the Graph API and validate the response."""
    response = await client.post(url, params=params)
    data = response.json()

    if response.status_code != 200:
        raise PublishError(f"Graph API returned {response.status_code} ({error_context}): {data}")
    if "error" in data:
        raise PublishError(f"Graph API error ({error_context}): {data['error']['message']}")
    if "id" not in data:
        raise PublishError(f"Graph API returned no ID ({error_context}): {data}")

    return data
