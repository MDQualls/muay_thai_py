import logging

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Claude / Anthropic
    anthropic_api_key: str = ""

    # Meta / Instagram
    meta_access_token: str = ""
    meta_instagram_account_id: str = ""

    # Cloudflare R2
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_public_url: str = ""
    r2_endpoint_url: str = ""

    # Database
    database_url: str = "sqlite:///data/muaythai.db"

    class Config:
        pass


settings = Settings()
