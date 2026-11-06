from __future__ import annotations

from projectseal.core.masking import (
    MASK_CHAR,
    clean_value,
    clip_preview,
    format_assignment_preview,
    mask_secret,
)


def test_known_prefix_is_preserved_but_value_is_hidden() -> None:
    secret = "sk-proj-" + "AbCdEfGhIjKlMnOpQrStUvWx"
    masked = mask_secret(secret)
    assert masked.startswith("sk-proj-")
    assert secret[10:] not in masked
    assert secret not in masked
    assert MASK_CHAR in masked


def test_short_value_is_fully_masked() -> None:
    assert mask_secret("abc") == MASK_CHAR * 8
    assert mask_secret("") == MASK_CHAR * 8


def test_generic_value_does_not_leak_full_secret() -> None:
    secret = "SuperSecret123!"
    masked = mask_secret(secret)
    assert secret not in masked
    assert masked.startswith("Su")
    assert masked.endswith("3!")


def test_assignment_preview_contains_key_and_masked_value() -> None:
    preview = format_assignment_preview("DB_PASSWORD", "SuperSecret123!")
    assert "DB_PASSWORD" in preview
    assert "SuperSecret123!" not in preview
    assert MASK_CHAR in preview


def test_clip_preview_removes_newlines_and_limits_length() -> None:
    text = "a\nb\tc" + "x" * 200
    clipped = clip_preview(text)
    assert "\n" not in clipped
    assert "\t" not in clipped
    assert len(clipped) <= 96
    assert clipped.endswith("…")


def test_clean_value_strips_quotes_and_spaces() -> None:
    assert clean_value("  'value'  ") == "value"
    assert clean_value(' "value" ') == "value"
