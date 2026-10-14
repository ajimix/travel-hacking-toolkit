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

1. **Bot protection (PerimeterX).** agent-browser and plain Playwright get a "Press & Hold" CAPTCHA on every page. Patchright in headed mode gets through for results and month pages most of the time. The per-itinerary deals page is guarded harder and usually needs the user to press & hold once; after that the clearance is stored in the browser profile and later runs pass, including deals pages. **Clearance is per domain**: each market has its own site (`--market US` is skyscanner.com, `UK` is skyscanner.net, `ES` is skyscanner.es), so the first search in a new market may need its own press & hold. Repeated searches from one IP in a short time also trigger the CAPTCHA.
2. **The headline price often comes from one small agency, not the airline.** In testing, an Alaska Airlines LAX-HNL nonstop round trip had 10 sellers. The $683 headline was Wizfair alone; the next cheapest was Expedia at $807. The only airline in the list was GOL (2.0/5), a partner reselling Alaska's flights at $927, and Alaska itself didn't sell the itinerary on Skyscanner at all. On JFK-LAX, by contrast, every American Airlines fare had a single seller, so Skyscanner added nothing over the airline-direct sources. That's why the deals step exists: always say who is selling before recommending a Skyscanner fare.

## Setup

Patchright lives in a shared virtualenv outside the repo. Homebrew's Python refuses a plain `pip install`, so don't use one. Create it once:

```bash
python3 -m venv ~/.cache/travel-hacking-toolkit/venv
~/.cache/travel-hacking-toolkit/venv/bin/pip install patchright
~/.cache/travel-hacking-toolkit/venv/bin/patchright install chromium
```

Run every command with that interpreter (`$PY` below). If `$PY` doesn't exist, create the venv first rather than falling back to system `python3`, where the import will fail.

The script runs headed (headless gets blocked), but it doesn't get in the user's way: the first run starts one Chrome in the background without taking focus, and every run after that, parallel runs included, opens its own background tab in that same browser and closes it when done. Chrome stays open between searches and only comes to the front when a CAPTCHA needs the user. It uses a persistent profile at `~/.cache/travel-hacking-toolkit/skyscanner-profile` (override with `SKYSCANNER_PROFILE`) so that a CAPTCHA cleared once keeps working for later runs. The browser is controlled through a DevTools port on 127.0.0.1:9337 (override with `SKYSCANNER_CDP_PORT`). Quit it with `$PY $S close` when the user is done with flight searching. `SKYSCANNER_SHARED_BROWSER=0` restores the old behaviour: a fresh foreground window per run.

## Commands

All commands accept `--market XX` (default `UK`), `--json`, and `--captcha-wait N` (default 0: fail fast with exit code 3 if a CAPTCHA appears; see [When Skyscanner blocks you](#when-skyscanner-blocks-you)).

```bash
PY=~/.cache/travel-hacking-toolkit/venv/bin/python
S=skills/skyscanner/scripts/skyscanner.py

# Results list (one-way or round trip), cheapest first
$PY $S search --origin LAX --dest HNL --depart 2026-11-20 --return 2026-11-27 --market US --json

# Multi-city / open-jaw: repeat --leg FROM TO DATE, 2-6 legs, instead of --origin/--dest/--depart/--return
$PY $S search --leg JFK LAX 2026-11-20 --leg SFO JFK 2026-11-27 --adults 2 --market US --json

# Options: --adults 2 --children 5,9 --cabin economy|premiumeconomy|business|first
#          --sort cheapest|best|fastest --limit 15

# Cheapest day in a month (one-way, outbound)
$PY $S month --origin LAX --dest HNL --month 2026-11 --market US --json

# Who sells a specific itinerary (deals_url comes from the search output)
$PY $S deals --url "<deals_url>" --market US --json

# Quit the shared background Chrome
$PY $S close
```

### What `search` returns

- `summary`: Skyscanner's Best / Cheapest / Fastest headline prices and the total result count. The Cheapest headline often belongs to a long self-transfer itinerary further down the list, so check it before quoting.
- `options[]`: per itinerary, the total price (for all travelers; `per_passenger` too when there are 2+), legs (`direction` is `outbound`/`inbound` for one-way, round trips and 2-leg multi-city, `leg 1`, `leg 2`... for 3+ legs; `from`/`to` airport names, times, `+1` for next-day arrival, stops, via-airports, duration, airlines), `deals` (how many sellers price it), `self_transfer`, and `deals_url`.
- `sponsored[]`: airline ads pinned to the top. They are not ranked results. Leave them out of the comparison unless they happen to be the cheapest real option.

Results stream in for 10-30 seconds; the script waits for the list to stop growing. A search takes about 40-60 seconds.

### What `deals` returns

Every seller for that itinerary, cheapest first: `seller`, `price`, `seller_type` (`airline` when it's the carrier actually flying the ticket, `partner airline` when another airline resells it, otherwise `agency`), `rating` and `reviews` (Skyscanner's 1-5 provider score and review count), `recommended`, `per_person` (with 2+ travelers), and `features`: the provider's selling points and warnings, e.g. "Change booking for a fee", "Upgrade to make booking changes", "Self-transfer", "Transfer protection included", "Buy now, pay later". It also returns the flight numbers, `cheapest`, and `cheapest_airline_direct` (null when the operating airline doesn't sell the itinerary on Skyscanner; then get the airline's own price from Duffel, Ignav or Google Flights). The deals page is guarded harder than search and often blocks the first time on a domain; handle it as in [When Skyscanner blocks you](#when-skyscanner-blocks-you).

Run `deals` for the 1-3 itineraries you're actually going to recommend, not for every row. Each one costs a page load and raises the CAPTCHA risk.

## When Skyscanner blocks you

The user cannot see anything you print while a command is running, and they cannot see the script's stderr at all. A long `--captcha-wait` started without warning them just sits there until it times out. So never wait for a CAPTCHA silently, and never give up on Skyscanner because nobody pressed the button. Ask first, then wait.

When a command exits with code 3 / `BLOCKED: Skyscanner served a CAPTCHA on <host>`:

1. **Stop and ask the user, right away.** Don't end your turn with a summary and a "reply go when ready". Use your ask-the-user tool (`AskUserQuestion` in Claude Code; in other agents, a direct question as the last line of your turn), e.g.:
   > Skyscanner is showing a "Press & Hold" CAPTCHA on skyscanner.com.my. When you pick **Ready**, I'll reopen Chrome and wait up to 5 minutes. The window comes to the front and you'll get a notification: press and hold the button until it turns green.
   >
   > Options: **Ready, open it** / **Skip Skyscanner for this search**
2. **On "Ready", rerun the exact same command with `--captcha-wait 300`** and set the shell tool's timeout to cover it: `--timeout` (180) + `--captcha-wait` (300) + ~30 s, i.e. about 510 000 ms in Claude Code's Bash tool (its default of 120 s would kill the run mid-wait).
3. **If it blocks again**, ask once more ("It's still showing the challenge. Try again?"). After two failed rounds, or if the user picks Skip, drop Skyscanner for this search, say so, and fall back to Kiwi.com for agency-style fares.
4. **Then carry on with the rest of the queue without asking again.** Clearance is stored per domain in the profile, so later searches on the same market usually pass. A new market (a new domain) may block once more: ask again for that one.

Planning several markets? Mention it in the first ask ("this may come up once per country site: MY, TH, SG, ES") so the user stays at the machine. Don't ask before trying: many runs pass without a challenge.

## Market selection

`--market` sets Skyscanner's market and currency while keeping the page in English (via the `ssculture` cookie on the market's own domain, e.g. `www.skyscanner.com` for US). Follow the toolkit's market playbook: origin country first, then destination country. Skyscanner prices genuinely differ by market, because some OTAs only sell in some markets. Supported codes are listed in `MARKETS` in the script. Unknown codes fall back to Skyscanner's own geo-redirect.

Prices come back in the market's currency (`$`, `£`, `€`...). Convert to the user's currency when comparing against other sources.

## How to present results

Fold Skyscanner rows into the same comparison table as the other sources, with a **Sold by** column so OTA fares can't hide among airline fares:

| #   | Airline | Stops  | Out (LAX-HNL) | Back (HNL-LAX) | Price | Sold by                         | Source        |
| --- | ------- | ------ | ------------- | -------------- | ----- | ------------------------------- | ------------- |
| 1   | Alaska  | Direct | 07:00-11:04   | 08:05-15:28    | $683  | Wizfair (agency, 4.7/5)         | Skyscanner US |
| 2   | Alaska  | Direct | 07:00-11:04   | 08:05-15:28    | $807  | Expedia (agency, 4.8/5)         | Skyscanner US |
| 3   | Alaska  | Direct | 07:00-11:04   | 08:05-15:28    | $927  | GOL (partner airline, 2.0/5)    | Skyscanner US |

Then say plainly what the agency discount buys and what it costs:

- **Agency vs airline gap.** Compare the cheapest seller with the operating airline's own price, from the deals list or, when the airline isn't listed, from Duffel, Ignav or Google Flights. Say it in one line, e.g. "The $683 is Wizfair, not Alaska. Changes and refunds would go through Wizfair."
- **Lone outlier.** When one seller is far below everyone else (Wizfair $683 vs Expedia $807 above, 15% lower), say so. Such prices sometimes disappear or grow at the agency's checkout. Quote the next seller as the realistic fallback.
- **Partner airline sellers.** An airline selling another airline's flights (GOL selling Alaska) is not "booking direct". Changes go through the reseller.
- **Small or weak agency.** Use the `rating` and `reviews` fields: under ~4.0/5, or only a few hundred reviews, deserves a warning. Also flag features like "Upgrade to make booking changes" (changes need a paid add-on). Be extra careful on long-haul or expensive fares where a schedule change is likely. As a rule of thumb, an agency saving under ~10% is rarely worth it; above ~20% it's worth considering for simple, non-refundable trips.
- **Self-transfer.** Itineraries marked `self_transfer` are separate tickets. A missed connection is the traveler's problem, and they may need to re-check bags and go through security (or immigration) again. Say so.
- **Only seen without seller.** If you couldn't run `deals` (CAPTCHA not cleared), write "Sold by: unknown, N deals" and don't present the price as an airline fare.

## Failure modes

| Symptom                                                | What to do                                                                                                                                                        |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `BLOCKED: Skyscanner served a CAPTCHA` (exit code 3)  | Follow [When Skyscanner blocks you](#when-skyscanner-blocks-you): ask the user first, then rerun with `--captcha-wait 300`. Skip Skyscanner only if the user says so or two rounds fail. |
| Sort tab click fails (stderr note)                     | Harmless. The script sorts the loaded options by price itself, but the very cheapest fare may not be among them. Compare against `summary.cheapest`.              |
| `deals` parses no rows                                 | The layout probably changed. Read the raw text path in the output and extract sellers manually.                                                                   |
| Wrong currency / language                              | A stale `ssculture` cookie in the profile. Delete the profile directory and rerun.                                                                                |
| `Shared Chrome did not open port ... within 15s`      | Rare (startup normally takes ~2s). Run `close` and retry once; if it fails again, rerun with `SKYSCANNER_SHARED_BROWSER=0`.                                        |
| `TIMEOUT`                                              | The script has a hard limit (`--timeout`, default 180s, plus `--captcha-wait`). Retry once; if it times out again, skip Skyscanner for this search.               |

## Limits

- No booking. Search only.
- Multi-city has no month view. To compare dates on an open-jaw, run one `search` per date pair.
- The month view is one-way outbound only.
- Skyscanner prices are meta-search quotes. The OTA's checkout can come out higher (bags, seats, "service fees"). Treat the deals-page price as the floor.
