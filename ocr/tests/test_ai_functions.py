"""
Tests for pure helper functions in library/ai.py.

These functions extract JSON from AI responses and normalize
strings for fuzzy matching — no API calls needed.
"""

import pytest
from library.ai import _extract_json_from_response, _fuzzy_normalize


# ── _extract_json_from_response ────────────────────────────────


class TestExtractJsonFromResponse:
    def test_direct_json_object(self):
        """Response that starts with '{' is returned as-is."""
        raw = '{"department_id": "5", "reasoning": "test"}'
        assert _extract_json_from_response(raw) == raw

    def test_direct_json_array(self):
        """Response that starts with '[' is returned as-is."""
        raw = '[{"article": 1}]'
        assert _extract_json_from_response(raw) == raw

    def test_strips_thinking_tags(self):
        """Qwen3-style <think>...</think> tags are stripped before extraction."""
        raw = '<think>Let me analyze this...</think>{"result": true}'
        result = _extract_json_from_response(raw)
        assert result == '{"result": true}'

    def test_extracts_embedded_json(self):
        """JSON embedded in surrounding text is extracted."""
        raw = 'Here is the result: {"category_id": "3", "reasoning": "matches"} end.'
        result = _extract_json_from_response(raw)
        assert '"category_id": "3"' in result

    def test_empty_input_returns_empty(self):
        assert _extract_json_from_response("") == ""
        assert _extract_json_from_response(None) == ""


# ── _fuzzy_normalize ───────────────────────────────────────────


class TestFuzzyNormalize:
    def test_strips_apostrophes(self):
        """Apostrophes (o', g') are removed for fuzzy matching."""
        assert "'" not in _fuzzy_normalize("Toshkent shahri")
        assert "'" not in _fuzzy_normalize("g'uzor")

    def test_collapses_k_q_ambiguity(self):
        """Russian к→k and Uzbek қ→q both normalize to 'k'."""
        # "qashqadaryo" and "kashkadaryo" should normalize the same
        assert _fuzzy_normalize("qashqa") == _fuzzy_normalize("kashka")

    def test_collapses_u_o_ambiguity(self):
        """u→o collapse makes 'buxoro' and 'boxoro' match (same city, different spelling)."""
        # "buxoro": u→o → "boxoro"
        # "boxoro": no u → "boxoro"
        assert _fuzzy_normalize("buxoro") == _fuzzy_normalize("boxoro")
