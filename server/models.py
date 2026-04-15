from datetime import datetime, UTC
from typing import Optional

from sqlmodel import Field, SQLModel


class Fighter(SQLModel, table=True):
    """One row per unique fighter ever processed by the app."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    nickname: Optional[str] = Field(default=None)
    nationality: Optional[str] = Field(default=None)
    gym: Optional[str] = Field(default=None)
    record_wins: Optional[int] = Field(default=None)
    record_losses: Optional[int] = Field(default=None)
    record_kos: Optional[int] = Field(default=None)
    wikipedia_url: Optional[str] = Field(default=None)
    # JSON-encoded list of fight history dicts from the scraper
    # e.g. '[{"opponent": "...", "result": "W", "method": "KO"}]'
    fight_history: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FighterProfile(SQLModel, table=True):
    """Claude's enriched analysis of a fighter.

    A fighter can have multiple profiles over time as their career evolves.
    Each enrichment run creates a new row.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    fighter_id: int = Field(foreign_key="fighter.id")
    fighting_style: str
    # JSON-encoded list e.g. '["Left body kick", "Elbow", "Clinch"]'
    signature_weapons: str
    # Attribute scores, each rated 1–10
    attr_aggression: int
    attr_power: int
    attr_footwork: int
    attr_clinch: int
    attr_cardio: int
    attr_technique: int
    bio: str
    fun_fact: Optional[str] = Field(default=None)
    career_highlight: Optional[str] = Field(default=None)
    hashtags: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Card(SQLModel, table=True):
    """One row per generated fighter card JPEG."""

    id: Optional[int] = Field(default=None, primary_key=True)
    fighter_id: int = Field(foreign_key="fighter.id")
    profile_id: int = Field(foreign_key="fighterprofile.id")
    # Path to the JPEG file on disk e.g. "output/rodtang_20240101_120000.jpg"
    local_path: str
    # Populated after the card is uploaded to Cloudflare R2
    r2_url: Optional[str] = Field(default=None)
    # Claude-generated Instagram caption
    caption: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InstagramPost(SQLModel, table=True):
    """One row per successful Instagram post."""

    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="card.id")
    # The post ID returned by the Meta Graph API
    instagram_id: str
    posted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # The exact caption text that was submitted to Instagram
    caption_used: str
