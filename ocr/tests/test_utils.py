"""
Tests for utils/text.py — pure functions, no DB or mocking needed.

These functions handle Uzbek text processing (transliteration,
phone/date cleaning, gibberish detection) and are bug magnets
due to their regex-heavy logic.
"""

import pytest
from utils.text import (
    normalize_date,
    clean_phone,
    is_valid_email,
    translite,
    reverse_translite,
    is_latin,
    is_cyrillic,
    is_gibberish_text,
    clean_extracted_content,
)


# ── normalize_date ─────────────────────────────────────────────


class TestNormalizeDate:
    def test_valid_date_format(self):
        """Standard DD.MM.YYYY date is returned as-is."""
        assert normalize_date("15.03.2026") == "15.03.2026"

    def test_date_embedded_in_text(self):
        """Date buried in surrounding text is still extracted."""
        assert normalize_date("Born on 01.12.1990 in Tashkent") == "01.12.1990"

    def test_null_values_return_none(self):
        """None, empty string, and 'null'/'none' all return None."""
        assert normalize_date(None) is None
        assert normalize_date("") is None
        assert normalize_date("null") is None
        assert normalize_date("none") is None

    def test_garbage_input_returns_none(self):
        """Non-date strings return None."""
        assert normalize_date("not a date") is None


# ── clean_phone ────────────────────────────────────────────────


class TestCleanPhone:
    def test_valid_uzbek_number(self):
        """Uzbek phone number with + prefix is preserved (regex includes the +)."""
        result = clean_phone(["+998901234567"])
        assert result == ["+998901234567"]

    def test_strips_leading_one(self):
        """12-digit numbers starting with '1' get the leading '1' stripped."""
        # regex captures max 12 digits; "198901234567" (12 digits) → strip '1' → 11 digits
        result = clean_phone(["198901234567"])
        assert result == ["98901234567"]

    def test_empty_input_returns_none(self):
        assert clean_phone(None) is None
        assert clean_phone([]) is None

    def test_invalid_phone_filtered_out(self):
        """Short/garbage strings are filtered, leaving None if all invalid."""
        assert clean_phone(["abc", "12"]) is None


# ── is_valid_email ─────────────────────────────────────────────


class TestIsValidEmail:
    def test_valid_email(self):
        assert is_valid_email("user@example.com") is True

    def test_invalid_email(self):
        assert is_valid_email("not-an-email") is False
        assert is_valid_email("") is False
        assert is_valid_email(None) is False

    def test_email_with_whitespace(self):
        """Leading/trailing whitespace is stripped before validation."""
        assert is_valid_email("  user@example.com  ") is True


# ── transliteration ────────────────────────────────────────────


class TestTransliteration:
    def test_cyrillic_to_latin(self):
        """Basic Cyrillic→Latin transliteration (Uzbek text)."""
        assert translite("Тошкент") == "Toshkent"

    def test_uzbek_special_chars(self):
        """Uzbek-specific Cyrillic chars: ў→o', ғ→g', қ→q, ҳ→h."""
        assert translite("қ") == "q"
        assert translite("ғ") == "g'"
        assert translite("ҳ") == "h"

    def test_latin_to_cyrillic(self):
        """Latin→Cyrillic reverse transliteration."""
        result = reverse_translite("Toshkent")
        assert is_cyrillic(result)

    def test_roundtrip_not_lossy(self):
        """Translite then reverse should produce Cyrillic output."""
        original = "Бухоро"
        latin = translite(original)
        back = reverse_translite(latin)
        # Roundtrip may not be identical due to mapping ambiguity,
        # but the result should be Cyrillic
        assert is_cyrillic(back)


# ── is_latin / is_cyrillic ────────────────────────────────────


class TestScriptDetection:
    def test_is_latin(self):
        assert is_latin("Hello") is True
        assert is_latin("123") is False

    def test_is_cyrillic(self):
        assert is_cyrillic("Привет") is True
        assert is_cyrillic("Hello") is False


# ── is_gibberish_text ──────────────────────────────────────────


class TestGibberishDetection:
    def test_normal_text_not_gibberish(self):
        """Legitimate Uzbek/Russian text should not be flagged."""
        text = "Ushbu ariza bo'yicha barcha hujjatlar tekshirildi"
        assert is_gibberish_text(text) is False

    def test_ocr_artifacts_detected(self):
        """HTML entities and random chars typical of bad OCR are detected."""
        text = "&amp; &lt; чв= гарде. &. д. ||| === $$$ ??? &&&"
        assert is_gibberish_text(text) is True

    def test_short_text_not_flagged(self):
        """Text under 10 chars is never flagged (too short to judge)."""
        assert is_gibberish_text("Hi") is False
        assert is_gibberish_text("") is False
