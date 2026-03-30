"""
Tests for pure helper functions in library/ai.py.

These functions normalize strings for fuzzy matching — no API calls needed.
"""

import pytest
from library.ai import _fuzzy_normalize


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
