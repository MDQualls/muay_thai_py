import logging
import httpx
from server.config import settings

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


async def post_carousel(image_urls: list[str], caption: str) -> str:
    """Post an image to Instagram via the Meta Graph API.

    Args:
        image_url: Public URL to the card image (returned by uploader.upload_card)
        caption: Instagram caption text (Claude-generated or user-edited)

    Returns:
        str Instagram post ID returned by the Graph API

    TODO:
    Step 1 — Create a media container:
        POST {GRAPH_API_BASE}/{settings.meta_instagram_account_id}/media
        params: image_url=image_url, caption=caption, access_token=settings.meta_access_token
        Parse and store container_id from response JSON: response["id"]

    Step 2 — Publish the container:
        POST {GRAPH_API_BASE}/{settings.meta_instagram_account_id}/media_publish
        params: creation_id=container_id, access_token=settings.meta_access_token
        Parse and return post_id from response JSON: response["id"]

    - Use httpx.AsyncClient for both requests
    - Raise PublishError on non-200 responses or missing "id" in response
    """
    logger.info("Posting to Instagram: %s", image_url[:60])

    
    return "placeholder_instagram_post_id"
