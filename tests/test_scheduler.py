"""Tests for server/scheduler.py — helper functions using an in-memory DB."""

from pathlib import Path
from unittest.mock import patch

import pytest
from sqlmodel import Session

from server.models import Card, Fighter, FighterProfile, FighterQueue, InstagramPost
from server.scheduler import _build_cron_kwargs, _has_been_posted, load_scheduler_config


# ---------------------------------------------------------------------------
# _has_been_posted
# ---------------------------------------------------------------------------


def test_has_been_posted_returns_false_when_fighter_not_in_db(db_session: Session) -> None:
    """Returns False when there is no Fighter row matching the name."""
    result = _has_been_posted(db_session, "Unknown Fighter")
    assert result is False


def test_has_been_posted_returns_false_when_fighter_exists_but_no_post(
    db_session: Session,
) -> None:
    """Returns False when the Fighter exists but has no linked InstagramPost."""
    fighter = Fighter(name="Rodtang Jitmuangnon")
    db_session.add(fighter)
    db_session.commit()
    db_session.refresh(fighter)

    result = _has_been_posted(db_session, "Rodtang Jitmuangnon")
    assert result is False


def test_has_been_posted_returns_false_when_card_exists_but_no_post(
    db_session: Session,
) -> None:
    """Returns False when Fighter and Card exist but no InstagramPost is linked."""
    fighter = Fighter(name="Buakaw Banchamek")
    db_session.add(fighter)
    db_session.commit()
    db_session.refresh(fighter)

    profile = FighterProfile(
        fighter_id=fighter.id,
        fighting_style="Aggressive",
        signature_weapons="[]",
        attr_aggression=8,
        attr_power=8,
        attr_footwork=7,
        attr_clinch=7,
        attr_cardio=9,
        attr_technique=8,
        bio="A great fighter.",
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    card = Card(
        fighter_id=fighter.id,
        profile_id=profile.id,
        local_path="output/buakaw_slide1.jpg",
    )
    db_session.add(card)
    db_session.commit()

    result = _has_been_posted(db_session, "Buakaw Banchamek")
    assert result is False


def test_has_been_posted_returns_true_when_instagram_post_exists(
    db_session: Session,
) -> None:
    """Returns True when Fighter has a Card with a linked InstagramPost."""
    fighter = Fighter(name="Saenchai")
    db_session.add(fighter)
    db_session.commit()
    db_session.refresh(fighter)

    profile = FighterProfile(
        fighter_id=fighter.id,
        fighting_style="Technical counter-fighter",
        signature_weapons="[]",
        attr_aggression=7,
        attr_power=7,
        attr_footwork=10,
        attr_clinch=8,
        attr_cardio=9,
        attr_technique=10,
        bio="Saenchai is arguably the greatest Muay Thai fighter of all time.",
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    card = Card(
        fighter_id=fighter.id,
        profile_id=profile.id,
        local_path="output/saenchai_slide1.jpg",
    )
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)

    post = InstagramPost(
        card_id=card.id,
        instagram_id="ig_post_123",
        caption_used="Amazing fighter!",
    )
    db_session.add(post)
    db_session.commit()

    result = _has_been_posted(db_session, "Saenchai")
    assert result is True


# ---------------------------------------------------------------------------
# load_scheduler_config
# ---------------------------------------------------------------------------


def test_load_scheduler_config_returns_defaults_when_file_missing() -> None:
    """Returns default config dict when data/scheduler_config.json does not exist."""
    with patch("server.scheduler.Path.exists", return_value=False):
        config = load_scheduler_config()

    assert config["enabled"] is True
    assert config["days"] == ["mon", "tue", "wed", "thu", "fri"]
    assert config["time"] == "09:00"
    assert config["timezone"] == "UTC"


def test_load_scheduler_config_returns_defaults_on_malformed_json(tmp_path: Path) -> None:
    """Returns defaults when the config file contains invalid JSON."""
    config_file = tmp_path / "scheduler_config.json"
    config_file.write_text("{not valid json")

    with patch("server.scheduler.Path", return_value=config_file):
        # Patch the config_path construction inside load_scheduler_config
        with patch("server.scheduler.Path") as mock_path_class:
            mock_path_instance = mock_path_class.return_value
            mock_path_instance.exists.return_value = True
            mock_path_instance.read_text.return_value = "{not valid json"

            config = load_scheduler_config()

    assert config["enabled"] is True
    assert config["days"] == ["mon", "tue", "wed", "thu", "fri"]


def test_load_scheduler_config_returns_defaults_when_days_missing() -> None:
    """Returns defaults when config file has no 'days' key."""
    import json

    with patch("server.scheduler.Path") as mock_path_class:
        mock_path_instance = mock_path_class.return_value
        mock_path_instance.exists.return_value = True
        mock_path_instance.read_text.return_value = json.dumps({"time": "10:00"})

        config = load_scheduler_config()

    assert config["days"] == ["mon", "tue", "wed", "thu", "fri"]


def test_load_scheduler_config_returns_file_data_when_valid() -> None:
    """Returns parsed config data when the file exists and is valid."""
    import json

    file_content = json.dumps(
        {"enabled": False, "days": ["mon", "wed"], "time": "14:30", "timezone": "America/Chicago"}
    )

    with patch("server.scheduler.Path") as mock_path_class:
        mock_path_instance = mock_path_class.return_value
        mock_path_instance.exists.return_value = True
        mock_path_instance.read_text.return_value = file_content

        config = load_scheduler_config()

    assert config["enabled"] is False
    assert config["days"] == ["mon", "wed"]
    assert config["time"] == "14:30"
    assert config["timezone"] == "America/Chicago"


# ---------------------------------------------------------------------------
# _build_cron_kwargs
# ---------------------------------------------------------------------------


def test_build_cron_kwargs_parses_time_correctly() -> None:
    """Hour and minute are correctly parsed from the HH:MM time string."""
    config = {
        "days": ["mon", "wed", "fri"],
        "time": "14:30",
        "timezone": "America/Chicago",
    }
    result = _build_cron_kwargs(config)

    assert result["hour"] == 14
    assert result["minute"] == 30


def test_build_cron_kwargs_joins_days_with_comma() -> None:
    """Days list is joined into a comma-separated string for APScheduler."""
    config = {
        "days": ["mon", "tue", "wed"],
        "time": "09:00",
        "timezone": "UTC",
    }
    result = _build_cron_kwargs(config)

    assert result["day_of_week"] == "mon,tue,wed"


def test_build_cron_kwargs_passes_timezone() -> None:
    """Timezone is passed through to the cron kwargs."""
    config = {
        "days": ["fri"],
        "time": "18:00",
        "timezone": "Europe/London",
    }
    result = _build_cron_kwargs(config)

    assert result["timezone"] == "Europe/London"


def test_build_cron_kwargs_defaults_timezone_to_utc() -> None:
    """When timezone is absent from config, UTC is used as default."""
    config = {
        "days": ["sat"],
        "time": "12:00",
    }
    result = _build_cron_kwargs(config)

    assert result["timezone"] == "UTC"


def test_build_cron_kwargs_midnight_time() -> None:
    """Midnight (00:00) is parsed as hour=0, minute=0."""
    config = {
        "days": ["sun"],
        "time": "00:00",
        "timezone": "UTC",
    }
    result = _build_cron_kwargs(config)

    assert result["hour"] == 0
    assert result["minute"] == 0


def test_build_cron_kwargs_single_day() -> None:
    """A single day list produces a plain string, not a trailing comma."""
    config = {
        "days": ["mon"],
        "time": "09:00",
        "timezone": "UTC",
    }
    result = _build_cron_kwargs(config)

    assert result["day_of_week"] == "mon"
