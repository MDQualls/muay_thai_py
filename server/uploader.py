import logging

logger = logging.getLogger(__name__)


async def upload_card(card_path: str) -> str:
    """Upload the card PNG to Cloudflare R2 and return a public URL.

    Args:
        card_path: Local path to the card PNG e.g. "output/card.png"

    Returns:
        str public URL to the uploaded image e.g. "https://pub.r2.dev/card_20240101.png"

    TODO:
    - Import settings from server.config
    - Create a boto3 S3 client configured for Cloudflare R2:
        boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
        )
    - Generate a timestamped filename e.g. "card_20240101_120000.png"
    - Upload with s3.upload_file(card_path, settings.r2_bucket_name, filename)
    - Return f"{settings.r2_public_url}/{filename}"
    - Wrap in try/except ClientError, log and raise UploadError on failure
    - Run the upload in a thread pool via asyncio.to_thread() to avoid blocking
    """
    logger.info("Uploading card to R2: %s", card_path)

    # TODO: implement R2 upload
    return "https://example.com/card.png"
