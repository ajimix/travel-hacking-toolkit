#!/usr/bin/env python3
"""Interactive session refresh for the Amex travel portal.

The travel-portal login gate is captcha-protected (see SKILL.md, Known
Limitation), so a fully automated fresh login is impossible. When
search_flights.py prints AMEX_HUMAN_LOGIN_NEEDED, run this script on your
LOCAL machine (not Docker). It opens a real Chrome window on the travel
portal; complete the login yourself (password + captcha + email code +
"Add This Device"). The script watches for the logged-in state, saves the
session cookies that the Docker runs mount, and exits.

Usage:
    python3 scripts/refresh_login.py
    python3 scripts/refresh_login.py --timeout 300
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from search_flights import (  # noqa: E402
    AMEX_FLIGHTS_URL,
    get_cookie_path,
    get_profile_dir,
    is_logged_in,
    save_cookies,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Seconds to wait for you to finish logging in (default 600)",
    )
    args = parser.parse_args()

    if os.path.exists("/.dockerenv") or os.environ.get("DOCKER"):
        print(
            "ERROR: refresh_login.py must run on your local machine, not in "
            "Docker. It needs a visible Chrome window you can interact with.",
            file=sys.stderr,
        )
        sys.exit(2)

    profile_dir = get_profile_dir()
    cookie_path = get_cookie_path()
    os.makedirs(profile_dir, exist_ok=True)

    from patchright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                channel="chrome",
                headless=False,
                viewport={"width": 1400, "height": 900},
                args=["--disable-blink-features=AutomationControlled"],
            )
        except Exception:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                viewport={"width": 1400, "height": 900},
                args=["--disable-blink-features=AutomationControlled"],
            )

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(AMEX_FLIGHTS_URL, timeout=60000)

        print("", file=sys.stderr)
        print("A Chrome window is open on the Amex travel portal.", file=sys.stderr)
        print(
            "Log in yourself: password, captcha, email code, and choose "
            '"Add This Device" so 2FA is skipped next time.',
            file=sys.stderr,
        )
        print(
            f"Waiting up to {args.timeout}s for the logged-in travel page...",
            file=sys.stderr,
        )

        deadline = time.time() + args.timeout
        while time.time() < deadline:
            try:
                if "/login" not in page.url.lower() and is_logged_in(page):
                    save_cookies(ctx, cookie_path)
                    print("AMEX_SESSION_REFRESHED", flush=True)
                    print(
                        f"Session saved. Profile: {profile_dir}", file=sys.stderr
                    )
                    ctx.close()
                    return
            except Exception:
                # Page mid-navigation or window closed; keep polling
                if not ctx.pages:
                    print("ERROR: Browser window closed.", file=sys.stderr)
                    sys.exit(1)
                page = ctx.pages[0]
            time.sleep(2)

        print("ERROR: Timed out waiting for login.", file=sys.stderr)
        ctx.close()
        sys.exit(1)


if __name__ == "__main__":
    main()
