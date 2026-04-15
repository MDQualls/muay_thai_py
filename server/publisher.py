import logging
import httpx
from server.config import settings
from server.exceptions import PublishError
import asyncio

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


async def post_carousel(image_urls: list[str], caption: str) -> str:
    """Post an image to Instagram via the Meta Graph API.

    Args:
        iimage_urls: List of public URLs to the carousel slide images (3 items)
        caption: Instagram caption text

    Returns:
        str Instagram post ID returned by the Graph API
    """
    logger.info("Posting to Instagram")

    async with httpx.AsyncClient() as client:

        # Create item containers (one per slide)
        containers = []
        for image_url in image_urls:
            post_url = f"{GRAPH_API_BASE}/{settings.meta_instagram_account_id}/media"
            item_response = await client.post(post_url, params={
                            "image_url": image_url,
                            "is_carousel_item": "true",
                            "access_token": settings.meta_access_token,
                        })
            data = item_response.json()
            if item_response.status_code != 200:
                raise PublishError(f"Graph API returned {item_response.status_code}: {data}")
            if "error" in data:
                raise PublishError(f"Graph API error creating container: {data['error']['message']}")
            if "id" not in data:
                raise PublishError(f"No container ID returned for {image_url}")
            containers.append(data["id"])
            logger.info("Created item container for slide: %s", data["id"])

        # Wait for Instagram to process the media before creating carousel
        logger.info("Waiting for Instagram to process media...")
        await asyncio.sleep(5)

        
        # Create the carousel container
        post_url = f"{GRAPH_API_BASE}/{settings.meta_instagram_account_id}/media"
        container_response = await client.post(post_url, params={
            "media_type": "CAROUSEL",
            "children": ",".join(containers),
            "caption": caption,
            "access_token": settings.meta_access_token
        })
        carousel_data = container_response.json()
        if container_response.status_code != 200:
            raise PublishError(f"Graph API returned {container_response.status_code}: {carousel_data}")
        if "error" in carousel_data:
            raise PublishError(f"Graph API error creating carousel: {carousel_data['error']['message']}")
        if "id" not in carousel_data:
            raise PublishError("No carousel container ID returned")
        carousel_id = carousel_data["id"]
        logger.info("Created carousel container: %s", carousel_id)

        # Wait for carousel container to be ready before publishing
        logger.info("Waiting for carousel container to be ready...")
        await asyncio.sleep(5)

        # Publish the carousel
        post_url = f"{GRAPH_API_BASE}/{settings.meta_instagram_account_id}/media_publish"
        publish_response = await client.post(post_url, params={
                            "creation_id": carousel_id,
                            "access_token": settings.meta_access_token,
                        })
        
        data = publish_response.json()        
        if publish_response.status_code != 200:
            raise PublishError(f"Graph API returned {publish_response.status_code}: {data}")
        if "error" in data:
            raise PublishError(f"Graph API error: {data['error']['message']}")
        if "id" not in data:
            raise PublishError(f"Graph API returned no ID in response: {data}")
        logger.info("Published carousel post: %s", data["id"])
            
    return data["id"]
