import logging 
import boto3
import asyncio
from server.config import settings
from pathlib import Path
from botocore.exceptions import ClientError
from server.exceptions import UploadError

logger = logging.getLogger(__name__)

s3_client = boto3.client(
    "s3",
    endpoint_url=settings.r2_endpoint_url,
    aws_access_key_id=settings.r2_access_key_id,
    aws_secret_access_key=settings.r2_secret_access_key,
    region_name="auto",
)

async def upload_carousel(card_paths: list[Path]) -> list[str]:
    """Upload the card PNG to Cloudflare R2 and return a public URL.

    Args:
        card_paths: Local paths to the cards' PNGs e.g. ["output/card.png","output/card.png",]

    Returns:
        list[str] public URLs to the uploaded images
        e.g. ["https://pub.r2.dev/card_slide1.png", ...]

    """
    logger.info("Uploading cards to R2")

    
    urls = []
    for card_path in card_paths:
        
        filename = card_path.name
        public_url = f"{settings.r2_public_url}/{filename}"
        
        try:        
            await asyncio.to_thread(
                s3_client.upload_file, 
                str(card_path), 
                settings.r2_bucket_name,
                filename
            )
        except ClientError as e:
            logger.error("R2 upload failed for %s: %s", filename, e)
            raise UploadError(f"Failed to upload {filename}") from e        
        
        urls.append(public_url)

    return urls
    
    
