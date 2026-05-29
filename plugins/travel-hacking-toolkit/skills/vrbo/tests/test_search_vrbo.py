#!/usr/bin/env python3
"""Unit tests for the vrbo skill's pure logic.

No browser, network, or Patchright required — the `patchright` import in
search_vrbo.py is lazy (inside `search()`), so importing the module is safe.

Run with either:
    python3 -m unittest discover -s skills/vrbo/tests
    python3 -m pytest skills/vrbo/tests
"""

import importlib.util
import os
import unittest

# Load search_vrbo.py by path (it lives in ../scripts, not on sys.path).
_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "scripts", "search_vrbo.py")
_spec = importlib.util.spec_from_file_location("search_vrbo", _SCRIPT)
sv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sv)


class BuildSearchUrlTests(unittest.TestCase):
    def test_includes_core_params(self):
        url = sv.build_search_url("Canmore, Alberta, Canada", "2026-06-26", "2026-07-02", 3, 0, False)
        self.assertTrue(url.startswith("https://www.vrbo.com/search?"))
        self.assertIn("startDate=2026-06-26", url)
        self.assertIn("endDate=2026-07-02", url)
        self.assertIn("adults=3", url)

    def test_url_encodes_destination(self):
        url = sv.build_search_url("Canmore, Alberta", "2026-06-26", "2026-07-02", 2, 0, False)
        # Comma and space must be percent-encoded, not raw.
        self.assertIn("destination=Canmore%2C%20Alberta", url)
        self.assertNotIn("destination=Canmore, Alberta", url)

    def test_children_and_pets_optional(self):
        without = sv.build_search_url("X", "2026-06-26", "2026-07-02", 2, 0, False)
        self.assertNotIn("children=", without)
        self.assertNotIn("petIncluded", without)
        with_extras = sv.build_search_url("X", "2026-06-26", "2026-07-02", 2, 2, True)
        self.assertIn("children=2", with_extras)
        self.assertIn("petIncluded=true", with_extras)


class BlockMarkerTests(unittest.TestCase):
    def test_detects_hard_429(self):
        self.assertTrue(sv.text_has_block_marker("Too Many Requests"))
        self.assertTrue(sv.text_has_block_marker("Provisioned request rate has been exceeded"))

    def test_detects_soft_interstitial(self):
        self.assertTrue(sv.text_has_block_marker("Please verify you are human to continue"))
        self.assertTrue(sv.text_has_block_marker("Press & Hold to confirm"))
        self.assertTrue(sv.text_has_block_marker("Pardon Our Interruption"))

    def test_case_insensitive(self):
        self.assertTrue(sv.text_has_block_marker("too many requests"))
        self.assertTrue(sv.text_has_block_marker("ACCESS DENIED"))

    def test_benign_text_not_blocked(self):
        self.assertFalse(sv.text_has_block_marker("Mountain Retreat w/ Views & Hot Tub"))
        self.assertFalse(sv.text_has_block_marker(""))
        self.assertFalse(sv.text_has_block_marker(None))


class ParsePriceTests(unittest.TestCase):
    def test_real_vrbo_string(self):
        # Verified live SERP format.
        p = sv.parse_price("The current price is CA $867 CA $867 CA $6,841 total includes taxes & fees")
        self.assertEqual(p["pricePerNight"], 867)
        self.assertEqual(p["priceTotal"], 6841)
        self.assertTrue(p["priceIncludesTaxes"])

    def test_strips_thousands_separator(self):
        p = sv.parse_price("CA $9,999 CA $9,999 CA $69,519 total includes taxes & fees")
        self.assertEqual(p["pricePerNight"], 9999)
        self.assertEqual(p["priceTotal"], 69519)

    def test_total_without_taxes_phrase(self):
        p = sv.parse_price("$312 total")
        self.assertEqual(p["priceTotal"], 312)
        self.assertFalse(p["priceIncludesTaxes"])

    def test_no_price(self):
        for empty in (None, "", "no digits here"):
            p = sv.parse_price(empty)
            self.assertIsNone(p["pricePerNight"])
            self.assertIsNone(p["priceTotal"])
            self.assertIsNone(p["priceIncludesTaxes"])


class SkeletonTests(unittest.TestCase):
    def test_all_null_is_skeleton(self):
        self.assertTrue(sv.is_skeleton({"id": None, "name": None, "url": None, "priceText": None}))

    def test_any_identity_field_is_not_skeleton(self):
        self.assertFalse(sv.is_skeleton({"id": "p123", "name": None, "url": None}))
        self.assertFalse(sv.is_skeleton({"id": None, "name": "Cabin", "url": None}))
        self.assertFalse(sv.is_skeleton({"id": None, "name": None, "url": "https://vrbo.com/p1"}))


class EnrichListingsTests(unittest.TestCase):
    def _sample(self):
        return [
            {"id": "p1", "name": "Condo", "url": "u1", "priceText": "CA $200 CA $200 CA $1,400 total includes taxes & fees", "bedrooms": 2},
            {"id": None, "name": None, "url": None, "priceText": None},  # skeleton
            {"id": "p3", "name": "Cabin", "url": "u3", "priceText": "CA $500 CA $3,000 total", "bedrooms": 4},
            {"id": "p4", "name": "Studio", "url": "u4", "priceText": None, "bedrooms": None},
        ]

    def test_drops_skeletons_and_parses_prices(self):
        out = sv.enrich_listings(self._sample())
        self.assertEqual(len(out), 3)  # skeleton removed
        first = next(l for l in out if l["id"] == "p1")
        self.assertEqual(first["pricePerNight"], 200)
        self.assertEqual(first["priceTotal"], 1400)
        self.assertTrue(first["priceIncludesTaxes"])

    def test_min_bedrooms_keeps_unknown(self):
        out = sv.enrich_listings(self._sample(), min_bedrooms=3)
        ids = {l["id"] for l in out}
        self.assertIn("p3", ids)       # 4 BR ≥ 3 → kept
        self.assertIn("p4", ids)       # unknown bedrooms → kept (don't drop on missing data)
        self.assertNotIn("p1", ids)    # 2 BR < 3 → dropped

    def test_limit(self):
        out = sv.enrich_listings(self._sample(), limit=1)
        self.assertEqual(len(out), 1)


class ExtractJsTests(unittest.TestCase):
    def test_extract_js_defines_three_layers(self):
        # Guard against accidentally deleting a fallback layer during refactors.
        js = sv.EXTRACT_JS
        self.assertIn("__PLUS_REDUX_STORE__", js)
        self.assertIn("lodging-card-responsive", js)
        self.assertIn("dom:anchors", js)


if __name__ == "__main__":
    unittest.main()
