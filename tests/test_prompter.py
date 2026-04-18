"""Tests for server/service/enrich/prompter.py — Prompter.build_prompt()."""

import pytest

from server.service.enrich.prompter import Prompter


@pytest.fixture
def prompter() -> Prompter:
    return Prompter()


def test_build_prompt_returns_non_empty_string(prompter: Prompter) -> None:
    """build_prompt returns a non-empty string for any non-empty content."""
    result: str = prompter.build_prompt("Some fighter content here.")
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_build_prompt_includes_passed_content(prompter: Prompter) -> None:
    """The provided content appears verbatim inside the returned prompt."""
    content = "Rodtang is the ONE flyweight Muay Thai champion with 267 wins."
    result: str = prompter.build_prompt(content)
    assert content in result


def test_build_prompt_includes_bio_field(prompter: Prompter) -> None:
    """The prompt instructs Claude to return a 'bio' field."""
    result: str = prompter.build_prompt("test content")
    assert '"bio"' in result


def test_build_prompt_includes_fun_fact_field(prompter: Prompter) -> None:
    """The prompt instructs Claude to return a 'fun_fact' field."""
    result: str = prompter.build_prompt("test content")
    assert '"fun_fact"' in result


def test_build_prompt_includes_attributes_field(prompter: Prompter) -> None:
    """The prompt instructs Claude to return an 'attributes' dict."""
    result: str = prompter.build_prompt("test content")
    assert '"attributes"' in result


def test_build_prompt_includes_signature_weapons_field(prompter: Prompter) -> None:
    """The prompt instructs Claude to return 'signature_weapons'."""
    result: str = prompter.build_prompt("test content")
    assert '"signature_weapons"' in result


def test_build_prompt_includes_all_six_attribute_keys(prompter: Prompter) -> None:
    """All six attribute scoring keys appear in the prompt."""
    result: str = prompter.build_prompt("test content")
    for key in ("aggression", "power", "footwork", "clinch", "cardio", "technique"):
        assert key in result, f"Expected attribute key '{key}' in prompt"


def test_build_prompt_is_string_with_varying_content(prompter: Prompter) -> None:
    """Different content produces different prompts."""
    result_a: str = prompter.build_prompt("Fighter A content")
    result_b: str = prompter.build_prompt("Fighter B content")
    assert result_a != result_b


def test_build_prompt_contains_json_instruction(prompter: Prompter) -> None:
    """The prompt instructs Claude to return only a JSON object."""
    result: str = prompter.build_prompt("test content")
    assert "JSON" in result
