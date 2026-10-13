#!/usr/bin/env python3
"""Search Skyscanner via Patchright (undetected Playwright).

Skyscanner sits behind PerimeterX. Plain Playwright / agent-browser get a
"Press & Hold" CAPTCHA on every results page. Patchright in headed mode gets
through for results and month-calendar pages. The per-itinerary "deals" page
(which names the seller: airline vs Mytrip/Gotogate/Trip.com/...) is guarded
harder and usually needs a human to press & hold once; after that the
clearance cookie lives in the persistent profile and later runs pass.

Requires: pip install patchright && patchright install chromium
Must run headed. A Chrome window appears while the script runs.

Usage:
    skyscanner.py search --origin BCN --dest LHR --depart 2026-11-20 [--return 2026-11-27]
                         [--adults 1] [--children 5,9] [--cabin economy] [--market UK]
                         [--sort best|cheapest|fastest] [--limit 15] [--json]
    skyscanner.py month  --origin BCN --dest LHR --month 2026-11 [--market UK] [--json]
    skyscanner.py deals  --url <config URL from search output> [--market UK] [--json]
                         [--captcha-wait 120]
"""

import argparse
import json
import os
import random
import re
import signal
import sys
import time
from datetime import date, datetime

from patchright.sync_api import sync_playwright

PROFILE_DIR = os.path.expanduser(
    os.environ.get("SKYSCANNER_PROFILE", "~/.cache/travel-hacking-toolkit/skyscanner-profile")
)

# market code -> (Skyscanner host, default currency). Unknown markets fall
# back to following Skyscanner's own redirect from skyscanner.net.
MARKETS = {
    "UK": ("www.skyscanner.net", "GBP"),
    "GB": ("www.skyscanner.net", "GBP"),
    "US": ("www.skyscanner.com", "USD"),
    "ES": ("www.skyscanner.es", "EUR"),
    "FR": ("www.skyscanner.fr", "EUR"),
    "DE": ("www.skyscanner.de", "EUR"),
    "IT": ("www.skyscanner.it", "EUR"),
    "PT": ("www.skyscanner.pt", "EUR"),
    "NL": ("www.skyscanner.nl", "EUR"),
    "IE": ("www.skyscanner.ie", "EUR"),
    "PL": ("www.skyscanner.pl", "PLN"),
    "RO": ("www.skyscanner.ro", "RON"),
    "TR": ("www.skyscanner.com.tr", "TRY"),
    "MY": ("www.skyscanner.com.my", "MYR"),
    "SG": ("www.skyscanner.com.sg", "SGD"),
    "TH": ("www.skyscanner.co.th", "THB"),
    "ID": ("www.skyscanner.co.id", "IDR"),
    "VN": ("www.skyscanner.com.vn", "VND"),
    "PH": ("www.skyscanner.com.ph", "PHP"),
    "HK": ("www.skyscanner.com.hk", "HKD"),
    "JP": ("www.skyscanner.jp", "JPY"),
    "KR": ("www.skyscanner.co.kr", "KRW"),
    "IN": ("www.skyscanner.co.in", "INR"),
    "AU": ("www.skyscanner.com.au", "AUD"),
    "NZ": ("www.skyscanner.co.nz", "NZD"),
    "CA": ("www.skyscanner.ca", "CAD"),
    "MX": ("www.skyscanner.com.mx", "MXN"),
    "BR": ("www.skyscanner.com.br", "BRL"),
    "AE": ("www.skyscanner.ae", "AED"),
    "ZA": ("www.skyscanner.co.za", "ZAR"),
}

CABINS = {"economy", "premiumeconomy", "business", "first"}
RESULT_SETTLE_MAX = 45  # seconds to wait for results to stop growing


def log(msg):
    print(f"[skyscanner] {msg}", file=sys.stderr, flush=True)


# --- browser ---------------------------------------------------------------

def culture_cookie(host, market, currency):
    return {
        "name": "ssculture",
        "value": f"locale:::en-GB&market:::{market}&currency:::{currency}",
        "url": f"https://{host}/",
    }


def is_captcha(page):
    if "/captcha" in page.url:
        return True
    try:
        return "Are you a person or a robot" in page.inner_text("body", timeout=3000)
    except Exception:
        return False


def wander(page, n=5):
    """A little mouse movement. PerimeterX scores behaviour, not just fingerprint."""
    for _ in range(n):
        page.mouse.move(random.randint(150, 900), random.randint(150, 650), steps=random.randint(8, 18))
        time.sleep(random.uniform(0.15, 0.4))


def wait_out_captcha(page, seconds):
    """Give the human at the keyboard a chance to press & hold. Never solve it ourselves."""
    if not is_captcha(page):
        return True
    if seconds <= 0:
        return False
    log(f"CAPTCHA shown. Press & hold the button in the Chrome window (waiting up to {seconds}s).")
    end = time.time() + seconds
    while time.time() < end:
        time.sleep(2)
        if not is_captcha(page):
            log("CAPTCHA cleared.")
            time.sleep(4)
            return True
    return False


class Browser:
    def __init__(self, market):
        self.market = (market or "UK").upper()
        self.host, self.currency = MARKETS.get(self.market, ("www.skyscanner.net", None))

    def __enter__(self):
        os.makedirs(PROFILE_DIR, exist_ok=True)
        self._pw = sync_playwright().start()
        self.ctx = self._pw.chromium.launch_persistent_context(
            PROFILE_DIR, headless=False, no_viewport=True
        )
        if self.currency:
            self.ctx.add_cookies([culture_cookie(self.host, self.market, self.currency)])
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        return self

    def __exit__(self, *exc):
        try:
            self.ctx.close()
        finally:
            self._pw.stop()

    def warmup(self):
        """Homepage first. Deep links without a warm session get challenged more often."""
        self.page.goto(f"https://{self.host}/", wait_until="domcontentloaded")
        time.sleep(4)
        if self.currency is None:
            # Unknown market: let Skyscanner redirect, then pin English on that host.
            from urllib.parse import urlparse
            self.host = urlparse(self.page.url).hostname
            cur = re.search(r"\b([A-Z]{3})\n", self.page.inner_text("body")[:600])
            self.currency = cur.group(1) if cur else "USD"
            self.ctx.add_cookies([culture_cookie(self.host, self.market, self.currency)])
            self.page.reload(wait_until="domcontentloaded")
            time.sleep(3)
        wander(self.page)

    def goto(self, path_or_url, captcha_wait=0):
        url = path_or_url if path_or_url.startswith("http") else f"https://{self.host}{path_or_url}"
        self.page.goto(url, wait_until="domcontentloaded")
        time.sleep(3)
        if not wait_out_captcha(self.page, captcha_wait):
            raise SystemExit(
                "BLOCKED: Skyscanner served a CAPTCHA. Retry in a few minutes, or rerun with "
                "--captcha-wait 120 and press & hold the button in the Chrome window."
            )
        return url


# --- search ----------------------------------------------------------------

def yymmdd(d):
    return datetime.strptime(d, "%Y-%m-%d").strftime("%y%m%d")


def search_path(a):
    o, d = a.origin.lower(), a.dest.lower()
    path = f"/transport/flights/{o}/{d}/{yymmdd(a.depart)}/"
    if a.return_date:
        path += f"{yymmdd(a.return_date)}/"
    q = [f"adultsv2={a.adults}", f"cabinclass={a.cabin}", f"rtn={1 if a.return_date else 0}"]
    if a.children:
        q.append("childrenv2=" + "|".join(x.strip() for x in a.children.split(",")))
    return path + "?" + "&".join(q)


LEG_RE = re.compile(
    r"(?:(Outbound|Inbound) flight|Flight) with (?P<airlines>[^.]+)\.\s*"
    r"Departing from (?P<from>.+?) at (?P<dep>\d{1,2}:\d{2}), arriving in (?P<to>.+?) at (?P<arr>\d{1,2}:\d{2})"
    r"(?:, (?P<later>one day|two days|\w+ days) later)?\.\s*"
    r"(?P<kind>Direct|Indirect) flight taking (?P<dur>[^.]+?)(?: with (?P<nstops>\d+) stops? in (?P<via>[^.]+))?\.",
    re.S,
)


def short_dur(s):
    h = re.search(r"(\d+) hours?", s)
    m = re.search(r"(\d+) minutes?", s)
    return f"{h.group(1) if h else 0}h {int(m.group(1)) if m else 0:02d}m"


def parse_option(text, href):
    m = re.search(r"Flight option (\d+): (.*?)Total cost ([^\n]+?)\.\n", text, re.S)
    if not m:
        return None
    pre = m.group(2)
    opt = {
        "option": int(m.group(1)),
        "sponsored": "Ad for" in pre or "Opens in a new window" in pre,
        "price": m.group(3).replace("\xa0", " ").strip(),
        "price_value": price_value(m.group(3)),
        "legs": [],
    }
    for lm in LEG_RE.finditer(text):
        later = lm.group("later")
        opt["legs"].append({
            "direction": (lm.group(1) or "outbound").lower(),
            "airlines": lm.group("airlines").strip(),
            "from": lm.group("from").strip(),
            "to": lm.group("to").strip(),
            "depart": lm.group("dep"),
            "arrive": lm.group("arr") + ("+1" if later == "one day" else ("+2" if later else "")),
            "stops": int(lm.group("nstops") or 0),
            "via": [v.strip() for v in (lm.group("via") or "").split(",") if v.strip()],
            "duration": short_dur(lm.group("dur")),
        })
    hm = re.search(r"Book with (.+?) from", text)
    if hm:
        opt["seller"] = hm.group(1).strip()  # sponsored airline ads name their seller
    dm = re.search(r"\n(\d+) deals?\b", text)
    opt["deals"] = int(dm.group(1)) if dm else None
    opt["self_transfer"] = "Self-transfer" in text or "self-transfer" in text
    opt["protected_transfer"] = "Protected" in text and "transfer" in text.lower()
    carrier = text.split("\n", 1)[0].strip()
    if "Operated by" in carrier or "•" in carrier:
        opt["marketing"] = carrier
    opt["deals_url"] = href
    return opt


def price_value(s):
    digits = re.sub(r"[^\d.,]", "", s)
    if not digits:
        return None
    # "1,234" / "1.234" / "1 234" -> 1234 ; "12,50" -> 12.5 (rare on Skyscanner, totals are whole)
    if re.search(r"[.,]\d{3}$", digits) or re.search(r"[.,]\d{3}[.,]", digits):
        digits = re.sub(r"[.,]", "", digits)
    else:
        digits = digits.replace(",", ".")
    try:
        return float(digits)
    except ValueError:
        return None


def wait_for_results(page):
    """Skyscanner streams in prices for ~10-30s. Wait until option count stops changing."""
    last, stable, start = -1, 0, time.time()
    while time.time() - start < RESULT_SETTLE_MAX:
        time.sleep(2)
        n = page.locator("a[href*='/config/']").count()
        body = page.inner_text("body")
        done = re.search(r"\d+ results sorted by", body) is not None
        stable = stable + 1 if n == last and n > 0 else 0
        last = n
        if stable >= 3 and done:
            break
    return last


def click_sort(page, sort):
    """Returns True if Skyscanner re-sorted the list itself."""
    if sort == "best":
        return True
    label = {"cheapest": "Cheapest", "fastest": "Fastest"}[sort]
    # A plain click times out (something overlays the tab), so click from inside the page.
    clicked = page.evaluate(
        """id => { const el = document.querySelector(`[data-testid="${id}"]`);
                   if (!el) return false; el.scrollIntoView({block: 'center'}); el.click(); return true; }""",
        f"FqsTab_{label.upper()}",
    )
    if clicked:
        time.sleep(3)
        wait_for_results(page)
        return True
    log(f"could not click '{label}' sort tab; sorting the loaded options locally")
    return False


def extract_summary(body):
    out = {}
    for label in ("Best", "Cheapest", "Fastest"):
        m = re.search(rf"\n{label}\n+([^\n]+)\n+(\d+ hours?(?: \d+ minutes?)?|\d+ minutes)", body)
        if m:
            out[label.lower()] = {"price": m.group(1).replace("\xa0", " ").strip(), "duration": short_dur(m.group(2))}
    m = re.search(r"(\d+) results sorted by", body)
    if m:
        out["total_results"] = int(m.group(1))
    return out


def extract_options(page):
    cards = page.eval_on_selector_all(
        "a[href*='/config/']",
        """els => els.map(a => {
            let el = a;
            for (let i = 0; i < 8 && el && !/Flight option \\d+:/.test(el.innerText || ''); i++) el = el.parentElement;
            return {href: a.href, text: el ? el.innerText : ''};
        })""",
    )
    seen, opts = set(), []
    for c in cards:
        key = c["href"].split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        o = parse_option(c["text"], key)
        if o:
            opts.append(o)
    # Ads link off-site (no /config/), so pick them up from the page text too.
    body = page.inner_text("body")
    for chunk in re.split(r"(?=Flight option \d+:)", body)[1:]:
        if "Opens in a new window" in chunk[:200] or "Ad for" in chunk[:200]:
            o = parse_option("x\n" + chunk, None)
            if o:
                o["sponsored"] = True
                opts.append(o)
    opts.sort(key=lambda o: o["option"])
    return opts, body


def cmd_search(a):
    with Browser(a.market) as b:
        b.warmup()
        url = b.goto(search_path(a), a.captcha_wait)
        wait_for_results(b.page)
        sorted_by_site = click_sort(b.page, a.sort)
        opts, body = extract_options(b.page)
        if not sorted_by_site and a.sort == "cheapest":
            opts.sort(key=lambda o: o["price_value"] or 1e12)
        result = {
            "source": "skyscanner",
            "market": b.market,
            "host": b.host,
            "url": url,
            "searched_at": datetime.now().isoformat(timespec="seconds"),
            "summary": extract_summary(body),
            "sort": a.sort,
            "options": [o for o in opts if not o["sponsored"]][: a.limit],
            "sponsored": [o for o in opts if o["sponsored"]],
        }
    emit(result, a.json, render_search)


def render_search(r):
    print(f"Skyscanner ({r['market']} market, {r['host']}) {r['url']}")
    s = r["summary"]
    if s:
        print("Summary: " + ", ".join(f"{k} {v['price']} ({v['duration']})" for k, v in s.items() if isinstance(v, dict))
              + (f", {s.get('total_results')} results" if s.get("total_results") else ""))
    for o in r["options"]:
        legs = " | ".join(
            f"{l['direction'][:3]} {l['depart']}-{l['arrive']} {l['duration']} "
            f"{'direct' if not l['stops'] else str(l['stops']) + ' stop via ' + '/'.join(l['via'])} ({l['airlines']})"
            for l in o["legs"]
        )
        flags = (" SELF-TRANSFER" if o["self_transfer"] else "")
        print(f"#{o['option']} {o['price']} [{o['deals']} deal{'' if o['deals'] == 1 else 's'}]{flags} :: {legs}")
        print(f"    deals: {o['deals_url']}")
    for o in r["sponsored"]:
        print(f"AD #{o['option']} {o['price']} {o.get('seller', '')} (sponsored, links to seller site)")


# --- month -----------------------------------------------------------------

def cmd_month(a):
    y, m = a.month.split("-")
    ym = y[2:] + m
    path = (f"/transport/flights/{a.origin.lower()}/{a.dest.lower()}/"
            f"?adultsv2={a.adults}&cabinclass={a.cabin}&rtn=0&oym={ym}&selectedoday=01")
    with Browser(a.market) as b:
        b.warmup()
        url = b.goto(path, a.captcha_wait)
        time.sleep(10)
        body = b.page.inner_text("body").replace("\u200b", "")
        month_name = date(int(y), int(m), 1).strftime("%B %Y")
        start = body.find(month_name + "\nM\t")
        grid = body[start:] if start >= 0 else body
        days = parse_month_grid(grid, y, m)
        result = {"source": "skyscanner", "market": b.market, "host": b.host, "url": url,
                  "month": a.month, "days": days}
        if days:
            result["cheapest"] = sorted(days, key=lambda x: x["price_value"])[:5]
    emit(result, a.json, render_month)


def parse_month_grid(grid, y, m):
    """The calendar is a run of lines: day numbers, each followed by its price if it has one.
    Leading days belong to the previous month, so start at the first "1" and stop when the
    day count wraps back to 1."""
    lines = [l.strip() for l in grid.split("\n") if l.strip()]
    is_day = lambda l: re.fullmatch(r"\d{1,2}", l) is not None
    days, started, expect = [], False, 1
    for i, line in enumerate(lines):
        if not is_day(line):
            continue
        d = int(line)
        if not started:
            if d != 1:
                continue
            started = True
        elif d == 1:
            break
        if d != expect:
            continue  # stray number elsewhere in the grid
        expect = d + 1
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if not is_day(nxt) and re.search(r"\d", nxt) and price_value(nxt) is not None:
            days.append({"day": d, "date": f"{y}-{m}-{d:02d}", "price": nxt.replace("\xa0", " "),
                         "price_value": price_value(nxt)})
    return days


def render_month(r):
    print(f"Skyscanner month view {r['month']} ({r['market']}) {r['url']}")
    for d in r["days"]:
        print(f"{d['date']}  {d['price']}")
    if r.get("cheapest"):
        print("Cheapest: " + ", ".join(f"{d['date']} {d['price']}" for d in r["cheapest"]))


# --- deals -----------------------------------------------------------------

def cmd_deals(a):
    with Browser(a.market) as b:
        b.warmup()
        b.goto(a.url, a.captcha_wait)
        log("deals page loaded, waiting for providers")
        for _ in range(10):
            time.sleep(2)
            if re.search(r"Option \d+: ", b.page.inner_text("body")):
                break
        time.sleep(4)  # late providers trickle in
        body = b.page.inner_text("body")
        raw_path = os.path.join(PROFILE_DIR, "last-deals.txt")
        with open(raw_path, "w") as f:
            f.write(body)
        cheapest = None
        deals = parse_deals(body)
        if deals:
            cheapest = min(deals, key=lambda d: d["price_value"] or 1e12)
        airline_deals = [d for d in deals if d["is_airline"]]
        result = {
            "source": "skyscanner",
            "market": b.market,
            "url": b.page.url.split("?")[0],
            "flights": parse_flight_numbers(body),
            "deals": deals,
            "cheapest": cheapest,
            "cheapest_airline_direct": min(airline_deals, key=lambda d: d["price_value"]) if airline_deals else None,
            "raw_text": raw_path,
        }
    emit(result, a.json, render_deals)


def parse_flight_numbers(body):
    return [
        {"airline": m.group(2).strip(), "flight": m.group(3)}
        for m in re.finditer(r"Leg (\d+) flight with (.+?)\. Flight number (\w+)\.", body)
    ]


def parse_deals(body):
    """Each provider block reads:
        Option N: <seller>
        [<seller> is an airline.]
        <rating>/5
        <review count>
        [Recommended provider]  (appears in the line just before "Option N")
        <feature lines...>
        Fare details | More fares
        <price> total.
    """
    out = []
    chunks = re.split(r"\n(?=Option \d+: )", body)
    for prev, chunk in zip(chunks, chunks[1:]):
        head = re.match(r"Option (\d+): (.+)", chunk)
        price = re.search(r"\n([^\n]+?) total\.", chunk)
        if not head or not price:
            continue
        block = chunk[: price.start()]
        seller = head.group(2).strip()
        rating = re.search(r"(\d(?:\.\d)?)/5\s*\n\s*([\d,.]+)", block)
        lines = [l.strip() for l in block.split("\n")[1:] if l.strip()]
        skip = {"Fare details", "More fares", "Airline", f"{seller} is an airline."}
        features = [
            l for l in lines
            if l not in skip and not re.fullmatch(r"[\d.,/ ]+(?:/5)?", l) and not l.endswith("/5")
        ]
        out.append({
            "option": int(head.group(1)),
            "seller": seller,
            "is_airline": f"{seller} is an airline." in block or prev.rstrip().endswith("Airline"),
            "recommended": "Recommended provider" in block,
            "rating": float(rating.group(1)) if rating else None,
            "reviews": int(re.sub(r"[^\d]", "", rating.group(2))) if rating else None,
            "price": price.group(1).strip(),
            "price_value": price_value(price.group(1)),
            "features": [f for f in features if f != "Recommended provider"],
        })
    return out


def render_deals(r):
    print(f"Skyscanner deals ({r['market']}) {r['url']}")
    if r["flights"]:
        print("Flights: " + ", ".join(f"{f['flight']} ({f['airline']})" for f in r["flights"]))
    for d in r["deals"]:
        kind = "AIRLINE" if d["is_airline"] else "agency"
        rating = f"{d['rating']}/5 ({d['reviews']:,})" if d["rating"] else "no rating"
        rec = " recommended" if d["recommended"] else ""
        print(f"{d['price']:>10}  {d['seller']:<22} {kind:<8} {rating}{rec}  {'; '.join(d['features'])}")
    if r["cheapest"] and r["cheapest_airline_direct"]:
        c, al = r["cheapest"], r["cheapest_airline_direct"]
        gap = (al["price_value"] or 0) - (c["price_value"] or 0)
        print(f"Cheapest: {c['seller']} {c['price']}. Airline direct: {al['seller']} {al['price']} (gap {gap:.0f}).")
    if not r["deals"]:
        print(f"No deal rows parsed. Raw page text saved to {r['raw_text']}.")


# --- main ------------------------------------------------------------------

def emit(result, as_json, renderer):
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        renderer(result)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--market", default="UK", help="Market country code (UK, US, ES, MY, TH...). Default UK.")
        sp.add_argument("--json", action="store_true")
        sp.add_argument("--timeout", type=int, default=180, help="Hard limit in seconds, excluding --captcha-wait")
        sp.add_argument("--captcha-wait", type=int, default=0,
                        help="Seconds to wait for a human to clear a CAPTCHA in the window (0 = fail fast)")

    s = sub.add_parser("search")
    common(s)
    s.add_argument("--origin", required=True)
    s.add_argument("--dest", required=True)
    s.add_argument("--depart", required=True, help="YYYY-MM-DD")
    s.add_argument("--return", dest="return_date", help="YYYY-MM-DD")
    s.add_argument("--adults", type=int, default=1)
    s.add_argument("--children", help="Comma-separated ages, e.g. 5,9")
    s.add_argument("--cabin", default="economy", choices=sorted(CABINS))
    s.add_argument("--sort", default="cheapest", choices=["best", "cheapest", "fastest"])
    s.add_argument("--limit", type=int, default=15)

    m = sub.add_parser("month")
    common(m)
    m.add_argument("--origin", required=True)
    m.add_argument("--dest", required=True)
    m.add_argument("--month", required=True, help="YYYY-MM")
    m.add_argument("--adults", type=int, default=1)
    m.add_argument("--cabin", default="economy", choices=sorted(CABINS))

    d = sub.add_parser("deals")
    common(d)
    d.add_argument("--url", required=True, help="deals_url from a search result")
    d.set_defaults(captcha_wait=120)

    a = p.parse_args()

    def on_timeout(*_):
        raise SystemExit(f"TIMEOUT: Skyscanner did not finish within {a.timeout}s. Retry later.")
    signal.signal(signal.SIGALRM, on_timeout)
    signal.alarm(a.timeout + max(a.captcha_wait, 0))
    {"search": cmd_search, "month": cmd_month, "deals": cmd_deals}[a.cmd](a)


if __name__ == "__main__":
    main()
