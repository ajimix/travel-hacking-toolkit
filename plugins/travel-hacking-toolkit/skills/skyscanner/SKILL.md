---
name: skyscanner
description: Search Skyscanner for flight prices via Patchright browser automation, including online travel agency (OTA) fares from Mytrip, Gotogate, Trip.com, eDreams, Kiwi and others that are often 10-25% below the airline's own price. Also has a cheapest-day month calendar and a per-itinerary seller breakdown that flags who actually sells the ticket. Use in any flight search where agency or budget-airline prices could beat the airline-direct fares from Duffel, Ignav or Google Flights, when the user asks "is there anything cheaper", mentions Skyscanner, or wants to know whether a cheap fare comes from the airline or an agency.
category: flights
summary: Browser-automated Skyscanner. OTA fares (Trip.com, Mytrip, eDreams, Kiwi) vs airline-direct with seller ratings, month calendar.
api_key: None (requires Patchright)
---

# Skyscanner

Skyscanner adds what the other sources in this toolkit mostly lack: **OTA prices**. Duffel, Ignav and Google Flights mostly show airline-direct fares. Skyscanner shows those plus small agencies (Mytrip, Gotogate, Trip.com, eDreams, Kiwi, Budgetair, Lastminute...) that frequently undercut the airline. It also has strong low-cost carrier coverage and a cheapest-day month calendar.

The catch is twofold, and both shape how you use it:

1. **Bot protection (PerimeterX).** agent-browser and plain Playwright get a "Press & Hold" CAPTCHA on every page. Patchright in headed mode gets through for results and month pages most of the time. The per-itinerary deals page is guarded harder and usually needs the user to press & hold once; after that the clearance is stored in the browser profile and later runs pass, including deals pages. Repeated searches from one IP in a short time also trigger the CAPTCHA.
2. **The cheapest price is often a small agency with poor service.** In testing, the cheapest seller on a Vueling BCN-LHR return was Trip.com at £180, with Vueling itself 7th at £194 and Worldairfares last at £345. The cheapest PEN-BCN fare (RM 1,644) was a 53-hour, 3-stop self-transfer on Scoot + Lauda + Wizz sold by a single agency. That's why the deals step exists: always say who is selling before recommending a Skyscanner fare.

## Setup

```bash
pip install patchright && patchright install chromium
```

The script runs headed (a Chrome window appears while it works; this is required, as headless gets blocked). It keeps a persistent browser profile at `~/.cache/travel-hacking-toolkit/skyscanner-profile` (override with `SKYSCANNER_PROFILE`) so that a CAPTCHA cleared once keeps working for later runs.

## Commands

All commands accept `--market XX` (default `UK`), `--json`, and `--captcha-wait N`.

```bash
S=skills/skyscanner/scripts/skyscanner.py

# Results list (one-way or round trip), cheapest first
python3 $S search --origin BCN --dest LHR --depart 2026-11-20 --return 2026-11-27 --market ES --json

# Options: --adults 2 --children 5,9 --cabin economy|premiumeconomy|business|first
#          --sort cheapest|best|fastest --limit 15

# Cheapest day in a month (one-way, outbound)
python3 $S month --origin BCN --dest LHR --month 2026-11 --market ES --json

# Who sells a specific itinerary (deals_url comes from the search output)
python3 $S deals --url "<deals_url>" --market ES --json
```

### What `search` returns

- `summary`: Skyscanner's Best / Cheapest / Fastest headline prices and the total result count. The Cheapest headline often belongs to a long self-transfer itinerary further down the list, so check it before quoting.
- `options[]`: per itinerary, the total price, legs (times, `+1` for next-day arrival, stops, via-airports, duration, airlines), `deals` (how many sellers price it), `self_transfer`, and `deals_url`.
- `sponsored[]`: airline ads pinned to the top. They are not ranked results. Leave them out of the comparison unless they happen to be the cheapest real option.

Results stream in for 10-30 seconds; the script waits for the list to stop growing. A search takes about 40-60 seconds.

### What `deals` returns

Every seller for that itinerary, cheapest first: `seller`, `price`, `is_airline` (Skyscanner's own "Airline" tag), `rating` and `reviews` (Skyscanner's 1-5 provider score and review count), `recommended`, and `features`: the provider's selling points and warnings, e.g. "Change booking for a fee", "Upgrade to make booking changes", "Self-transfer", "Transfer protection included", "Buy now, pay later". It also returns the flight numbers, `cheapest`, and `cheapest_airline_direct`, so the agency-vs-airline gap is one subtraction. The deals page defaults to `--captcha-wait 120`: if the CAPTCHA appears, tell the user **"A Chrome window opened on Skyscanner. Press and hold the button until it clears."** and let the command run. Do not attempt to solve CAPTCHAs programmatically.

Run `deals` for the 1-3 itineraries you're actually going to recommend, not for every row. Each one costs a page load and raises the CAPTCHA risk.

## Market selection

`--market` sets Skyscanner's market and currency while keeping the page in English (via the `ssculture` cookie on the market's own domain, e.g. `www.skyscanner.es`). Follow the toolkit's market playbook: origin country first, then destination country. Skyscanner prices genuinely differ by market, because some OTAs only sell in some markets. Supported codes are listed in `MARKETS` in the script. Unknown codes fall back to Skyscanner's own geo-redirect.

Prices come back in the market's currency (`£`, `€`, `RM`...). Convert to the user's currency when comparing against other sources.

## How to present results

Fold Skyscanner rows into the same comparison table as the other sources, with a **Sold by** column so OTA fares can't hide among airline fares:

| #   | Airline | Stops  | Duration | Depart | Arrive | Price | Sold by                   | Source         |
| --- | ------- | ------ | -------- | ------ | ------ | ----- | ------------------------- | -------------- |
| 1   | Vueling | Direct | 2h 40m   | 07:30  | 09:10  | £180  | Trip.com (agency, 4.8/5)  | Skyscanner UK  |
| 2   | Vueling | Direct | 2h 40m   | 07:30  | 09:10  | £194  | Vueling (airline)         | Skyscanner UK  |
| 3   | BA      | Direct | 2h 40m   | 06:35  | 08:15  | £233  | British Airways (airline) | Google Flights |

Then say plainly what the agency discount buys and what it costs:

- **Agency vs airline gap.** "The £180 is Trip.com (4.8/5, changes for a fee). Vueling direct is £194 on the same flights. That's £14 (7%) saved, against changes and refunds going through Trip.com instead of Vueling."
- **Small or weak agency.** Use the `rating` and `reviews` fields: under ~4.0/5, or only a few hundred reviews, deserves a warning. Also flag features like "Upgrade to make booking changes" (changes need a paid add-on). Be extra careful on long-haul or expensive fares where a schedule change is likely. As a rule of thumb, an agency saving under ~10% is rarely worth it; above ~20% it's worth considering for simple, non-refundable trips.
- **Self-transfer.** Itineraries marked `self_transfer` are separate tickets. A missed connection is the traveller's problem, and they may need to re-check bags and pass through immigration. Say so.
- **Only seen without seller.** If you couldn't run `deals` (CAPTCHA not cleared), write "Sold by: unknown, N deals" and don't present the price as an airline fare.

## Failure modes

| Symptom                                                | What to do                                                                                                                                                        |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `BLOCKED: Skyscanner served a CAPTCHA` on search/month | Rerun once with `--captcha-wait 120` and ask the user to press & hold. If they're not around, skip Skyscanner, say it was blocked, and rely on the other sources. |
| Sort tab click fails (stderr note)                     | Harmless. The script sorts the loaded options by price itself, but the very cheapest fare may not be among them. Compare against `summary.cheapest`.              |
| `deals` parses no rows                                 | The layout probably changed. Read the raw text path in the output and extract sellers manually.                                                                   |
| Wrong currency / language                              | A stale `ssculture` cookie in the profile. Delete the profile directory and rerun.                                                                                |
| `TIMEOUT`                                              | The script has a hard limit (`--timeout`, default 180s, plus `--captcha-wait`). Retry once; if it times out again, skip Skyscanner for this search.               |

## Limits

- No booking. Search only.
- Multi-city isn't supported by the script. Use google-flights for that.
- The month view is one-way outbound only.
- Skyscanner prices are meta-search quotes. The OTA's checkout can come out higher (bags, seats, "service fees"). Treat the deals-page price as the floor.
