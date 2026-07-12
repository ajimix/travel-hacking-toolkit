#!/usr/bin/env python3
"""Offline unit tests for Chase 2FA method selection.

The bug (issue #18): on accounts whose ONLY 2FA option is the mobile-app push,
the flow fell through to the SMS path and timed out. `_choose_2fa_method` is the
pure decision function; these tests lock in that a push-only picker resolves to
'mobile'. The `patchright` import in search_flights.py is lazy, so importing the
module is safe.

Run:
    python3 -m unittest discover -s skills/chase-travel/tests
"""

import importlib.util
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "scripts", "search_flights.py")
_spec = importlib.util.spec_from_file_location("chase_search_flights", _SCRIPT)
sf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sf)

PICKER = "let's make sure it's you. choose how to verify."


class Choose2faMethodTests(unittest.TestCase):
    def test_sms_available(self):
        self.assertEqual(sf._choose_2fa_method(PICKER, {"hasSms": True, "hasMobile": False}), "sms")

    def test_mobile_only(self):
        self.assertEqual(sf._choose_2fa_method(PICKER, {"hasSms": False, "hasMobile": True}), "mobile")

    def test_push_only_undetected_defaults_mobile(self):
        # The bug case: neither card's shadow-DOM text was captured, but we are
        # clearly on the picker → assume mobile push (SMS would show an #sms card).
        self.assertEqual(sf._choose_2fa_method(PICKER, {"hasSms": False, "hasMobile": False}), "mobile")

    def test_both_available_prefers_sms(self):
        # SMS is automatable via the code hook, so prefer it when offered.
        self.assertEqual(sf._choose_2fa_method(PICKER, {"hasSms": True, "hasMobile": True}), "sms")

    def test_not_on_picker_defaults_sms(self):
        # No options detected and not obviously the picker → historical default.
        self.assertEqual(sf._choose_2fa_method("some other page", {"hasSms": False, "hasMobile": False}), "sms")

    def test_confirm_identity_wording_also_counts_as_picker(self):
        self.assertEqual(
            sf._choose_2fa_method("Confirm your identity", {"hasSms": False, "hasMobile": False}),
            "mobile",
        )


if __name__ == "__main__":
    unittest.main()
