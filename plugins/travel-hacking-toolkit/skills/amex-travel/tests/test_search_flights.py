#!/usr/bin/env python3
"""Offline unit tests for amex-travel form-filling logic.

The `patchright` import in search_flights.py is lazy (inside the browser
functions), so importing the module is safe. These tests exercise the pure
control flow of the May-2026 UI fixes with a fake page/element — no browser.

Run:
    python3 -m unittest discover -s skills/amex-travel/tests
"""

import importlib.util
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "scripts", "search_flights.py")
_spec = importlib.util.spec_from_file_location("amex_search_flights", _SCRIPT)
sf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sf)


class FakeElement:
    def __init__(self, *, visible=True, select_raises=False):
        self._visible = visible
        self._select_raises = select_raises
        self.clicked = False
        self.selected = None

    def is_visible(self):
        return self._visible

    def click(self):
        self.clicked = True

    def type(self, text, delay=0):
        pass

    def select_option(self, value, timeout=0):
        if self._select_raises:
            raise Exception("Element is not a <select> element")
        self.selected = value


class FakeKeyboard:
    def __init__(self):
        self.pressed = []

    def press(self, key):
        self.pressed.append(key)


class FakePage:
    """query_selector consults `handlers`: a list of (predicate, element).
    First predicate whose `substr` is in the selector string wins."""

    def __init__(self, handlers):
        self.handlers = handlers  # list of (substr, element)
        self.keyboard = FakeKeyboard()
        self.wait_selector_calls = []

    def query_selector(self, selector):
        for substr, el in self.handlers:
            if substr in selector:
                return el
        return None

    def wait_for_timeout(self, ms):
        pass

    def wait_for_selector(self, selector, state=None, timeout=0):
        self.wait_selector_calls.append(selector)
        return object()

    def evaluate(self, *args, **kwargs):
        pass


class SetCabinTests(unittest.TestCase):
    def test_native_select_path(self):
        el = FakeElement(select_raises=False)
        page = FakePage([("flight-class-dropdown", el)])
        self.assertTrue(sf._set_cabin(page, "Business", "BUSINESS"))
        self.assertEqual(el.selected, "BUSINESS")  # used native select
        self.assertFalse(el.clicked)               # did not need the click path

    def test_custom_component_click_fallback(self):
        trigger = FakeElement(select_raises=True)   # not a native <select>
        option = FakeElement(visible=True)
        # trigger matches the dropdown selector; option matches has-text("Business")
        page = FakePage([("flight-class-dropdown", trigger), ('has-text("Business")', option)])
        self.assertTrue(sf._set_cabin(page, "Business", "BUSINESS"))
        self.assertTrue(trigger.clicked)   # opened the custom dropdown
        self.assertTrue(option.clicked)    # clicked the matching option

    def test_missing_dropdown_returns_false(self):
        page = FakePage([])  # nothing matches
        self.assertFalse(sf._set_cabin(page, "Business", "BUSINESS"))


class FillAirportFieldTests(unittest.TestCase):
    def test_clicks_option_not_enter(self):
        inp = FakeElement(visible=True)
        option = FakeElement(visible=True)
        # input matches the given selector; option matches listbox/option selectors
        page = FakePage([("locationsInput", inp), ('role="option"', option)])
        self.assertTrue(sf._fill_airport_field(page, 'input[id*="locationsInput_departure"]', "SFO"))
        self.assertTrue(option.clicked)          # clicked the autocomplete option
        self.assertEqual(page.keyboard.pressed, [])  # did NOT fall back to Enter

    def test_enter_fallback_when_no_option(self):
        inp = FakeElement(visible=True)
        page = FakePage([("locationsInput", inp)])  # no option element present
        self.assertTrue(sf._fill_airport_field(page, 'input[id*="locationsInput_departure"]', "SFO"))
        self.assertEqual(page.keyboard.pressed, ["Enter"])  # last-resort Enter


class RaisingPage(FakePage):
    def query_selector(self, selector):
        raise Exception("page crashed")


class CaptchaDetectionTests(unittest.TestCase):
    def test_detects_captcha_marker(self):
        page = FakePage([("captcha", FakeElement())])
        self.assertTrue(sf._captcha_present(page))

    def test_no_captcha(self):
        page = FakePage([])
        self.assertFalse(sf._captcha_present(page))

    def test_page_error_is_not_a_captcha(self):
        self.assertFalse(sf._captcha_present(RaisingPage([])))

    def test_sentinel_printed_on_stdout(self):
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            sf._emit_human_login_needed("captcha on the travel portal login gate")
        self.assertIn("AMEX_HUMAN_LOGIN_NEEDED", out.getvalue())


class CredentialGuardTests(unittest.TestCase):
    def test_unresolved_secret_reference(self):
        self.assertTrue(sf._unresolved_secret("secret://Vault/item/username"))
        self.assertTrue(sf._unresolved_secret('"vault://item/username"'))
        self.assertFalse(sf._unresolved_secret("actual_username"))
        self.assertFalse(sf._unresolved_secret(""))
        self.assertFalse(sf._unresolved_secret(None))

    def test_sentinel_printed_on_stdout(self):
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            sf._emit_bad_credentials("AMEX_USERNAME is an unresolved secret reference")
        self.assertIn("AMEX_BAD_CREDENTIALS", out.getvalue())


if __name__ == "__main__":
    unittest.main()
