---
name: travelpayouts
description: Cheapest-fare discovery from the Travelpayouts (Aviasales) Data API — CACHED prices from recent user searches, not live inventory. Use for flexible-date and "cheapest month/day to fly" questions, price calendars, "where can I fly cheaply from X" (anywhere) searches, and as an extra price reference alongside live sources in any flight search. Triggers on "when is it cheapest to fly", "cheapest dates in November", "I'm flexible", "cheap flights from BCN anywhere", "price calendar", or any flight search where a cheap-date hint would help. Never present its prices as bookable quotes without confirming on a live source.
category: flights
summary: Cached Aviasales fare data. Cheapest-date calendars, flexible-month and anywhere searches.
api_key: Travelpayouts (free)
allowed-tools: Bash(curl *)
---

# Travelpayouts (Aviasales Data API)

## ⚠️ These prices are cached, not live

Everything this API returns comes from a **cache of searches Aviasales users ran in the last few days** (typically 1–7 days old). It's not a live query against airline inventory. That means:

- A fare may have **sold out or gone up** since it was cached. Always show the user how old each price is:
  - **v3 endpoints** (`prices_for_dates`, `grouped_prices`): there's no top-level date field. The age is the `search_date=DDMMYYYY` parameter inside `link` (e.g. `search_date=12102026` = 12 Oct 2026). Extract it with jq: `.link | capture("search_date=(?<d>[0-9]{8})").d`
  - **v2 endpoints**: `found_at` (ISO timestamp).
  - **`city-directions`**: `expires_at` only, so you can't get an exact age. Just say it's cached.
- Coverage is uneven. Popular routes have lots of data. Obscure routes or dates may come back empty (`"data": []`) even when flights exist. **Empty does not mean there's no service.** Re-querying a missing date one day at a time won't help: if a day isn't in the month-level results, it isn't in the cache. Fill the gaps with a live source (Ignav, google-flights, Skiplagged flex calendar), or use `wikipedia-airports` to check whether the route exists.
- **Never present a Travelpayouts price as "the price".** Label it "cached, seen N days ago" and confirm it on a live source (Duffel, Ignav, google-flights) before recommending a booking.

So what's it for? **Discovery.** It's great at answering "which day/month is cheapest?" and "where can I go cheaply?" in a single call, which the live sources can't do without dozens of searches. Find the cheap date here, then price that date live.

## Authentication

Send the token in the `X-Access-Token` header. `$TRAVELPAYOUTS_TOKEN` is pre-loaded via `.claude/settings.local.json`, so it's available in every Bash call with no sourcing needed. A bad or missing token returns the plain-text body `Unauthorized`.

Optional: `$TRAVELPAYOUTS_MARKER` (affiliate ID) can be appended to booking links as `&marker=...` to earn commission. If it's unset, skip it.

## Always pass `currency`

**The default currency is RUB.** Always pass `currency=eur` or `currency=usd` (lowercase), matching the user's currency or the origin market.

## Endpoints

Base URL: `https://api.travelpayouts.com`. City codes (`LON`, `NYC`, `TYO`, `MIL`) work and cover all of a city's airports. Results include the actual `origin_airport` / `destination_airport`.

### 1. Cheapest fares for a date or month: `prices_for_dates` (main workhorse)

```bash
curl -s -H "X-Access-Token: $TRAVELPAYOUTS_TOKEN" \
  "https://api.travelpayouts.com/aviasales/v3/prices_for_dates?origin=BCN&destination=LON&departure_at=2026-11&one_way=true&currency=eur&sorting=price&limit=10"
```

| Param                       | Notes                                                                                                                                                 |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `origin`, `destination`     | IATA airport or city code. **Leave out `destination` for an "anywhere" search** (cheapest destinations from the origin).                              |
| `departure_at`, `return_at` | `YYYY-MM-DD` or `YYYY-MM` (whole month). Add `return_at` + `one_way=false` for round trips.                                                           |
| `one_way`                   | `true` for one-way. For round trips, set `false` and pass `return_at`.                                                                                |
| `direct`                    | `true` = nonstop only.                                                                                                                                |
| `market`                    | Lowercase country code (`es`, `us`, `th`…). Defaults to `ru` when omitted, so **always set it explicitly** to the departure country first, per the Market Selection Strategy in CLAUDE.md. Differences between markets are usually small (a different cached seller), much smaller than on live sources. |
| `sorting`                   | `price` (default) or `route`.                                                                                                                         |
| `limit`, `page`             | Up to 1000 per page.                                                                                                                                  |
| `currency`                  | **Always set it.** See above.                                                                                                                         |

Response: `data[]` with `price`, `airline`, `flight_number`, `origin_airport`, `destination_airport`, `departure_at` (local time with offset), `return_at`, `transfers`, `return_transfers`, `duration` (total), `duration_to`, `duration_back` (minutes), `gate` (the seller: Kiwi.com, Trip.com, easyJet…; sometimes Cyrillic, e.g. "Авиасейлс" = Aviasales), and `link`. Times carry their local offset, so UK and Portugal show `Z` in winter. That's correct.

**The same itinerary repeats once per seller** at different prices. Before presenting, de-duplicate: group by flight (or by `destination_airport` for anywhere searches) and keep the cheapest. Otherwise a `limit=50` fills up with copies.

**There's no time-of-day filter.** The cheapest round trips often return at 06:00–07:00, which effectively costs a day. Filter on `departure_at`/`return_at` yourself whenever the user cares about time on the ground (weekends especially), and flag early returns.

### 2. Cheapest per day or per month: `grouped_prices` (price calendar)

```bash
# Cheapest fare for each day of November
curl -s -H "X-Access-Token: $TRAVELPAYOUTS_TOKEN" \
  "https://api.travelpayouts.com/aviasales/v3/grouped_prices?origin=BCN&destination=LON&departure_at=2026-11&group_by=departure_at&currency=eur"

# Cheapest fare for each upcoming month (leave out departure_at)
curl -s -H "X-Access-Token: $TRAVELPAYOUTS_TOKEN" \
  "https://api.travelpayouts.com/aviasales/v3/grouped_prices?origin=MAD&destination=NYC&group_by=month&currency=eur"
```

`data` is an object keyed by date (`"2026-11-05"`) or month (`"2026-11"`). Each value has the same shape as a `prices_for_dates` item. Days with no cached search are simply missing. Say so, and don't read a missing day as "no flights".

**One-way by default.** `grouped_prices` returns one-way fares unless you add `one_way=false`, which switches the values to round trips (with `return_at` and `duration_back` filled in). It accepts the same `direct`, `market` and `currency` params as `prices_for_dates`.

**No date-range filter.** For "second half of November", fetch the month (`departure_at=2026-11`) and filter the keys yourself. For ranges that span two months, make one call per month.

### 3. Popular cheap destinations from a city: `city-directions`

```bash
curl -s -H "X-Access-Token: $TRAVELPAYOUTS_TOKEN" \
  "https://api.travelpayouts.com/v1/city-directions?origin=BCN&currency=eur"
```

Returns round-trip fares keyed by destination city code, on arbitrary dates, with stops allowed. You can't filter by month or nonstop. Only use it for completely open-ended "where should I go?" questions. **If the user gave any dates, use `prices_for_dates` without `destination` instead.**

### 4. City and airport lookup (no token needed)

```bash
curl -s "https://autocomplete.travelpayouts.com/places2?term=Barcelona&locale=en&types[]=city&types[]=airport"
```

Returns `code`, `name`, `country_code`, `type`. Watch for duplicates: "Barcelona" also matches BLA in Venezuela. Pick by `country_code` and `weight`.

## Booking links

`link` is relative (`/search/BCN2011LON1?t=...`). Prefix it with `https://www.aviasales.com` to get an Aviasales search page for that itinerary. Treat it as a "check current price" link, not a guaranteed fare.

## Presenting results

Use a markdown table and **always include how old each price is**:

| #   | Date      | Airline | Route   | Stops   | Duration | Price (cached) | Seen       |
| --- | --------- | ------- | ------- | ------- | -------- | -------------- | ---------- |
| 1   | Fri Nov 6 | easyJet | BCN→LTN | Nonstop | 2h 25m   | €19            | 2 days ago |
| 2   | Sat Nov 7 | Ryanair | BCN→STN | Nonstop | 2h 25m   | €16            | 1 day ago  |

Then:

- Lead with the takeaway ("Nov 5–8 are the cheapest days, ~€16–23 nonstop. Avoid Nov 1, which is €99").
- Say clearly that these are cached prices to verify, and **verify the best date or dates on a live source** (Ignav/Duffel/google-flights) as part of the same answer. Don't leave it as a suggestion.
- When combining with live sources in one table, label the source column "Travelpayouts (cached)" so it's never mixed up with a live quote.

## Where it fits in the source hierarchy

Below all live sources for price accuracy: **Duffel > Airline > Ignav > google-flights > SerpAPI > Skiplagged/Kiwi > Travelpayouts (cached)**. Use it to choose _when_ or _where_ to search, then let the live sources set the price.

## Tips

- When the user is flexible, run `grouped_prices` with `group_by=departure_at` first, then live-search the 2–3 cheapest days.
- For "cheapest month this year", use `grouped_prices` with `group_by=month`.
- For "anywhere cheap from X in <month>", use `prices_for_dates` without `destination`, sorted by price.
- **For weekend trips, use exact dates.** Month-level `departure_at`/`return_at` returns trips of any length (4–20 days), which is useless for a weekend. Query exact Fri→Sun dates (`departure_at=2026-12-11&return_at=2026-12-13&one_way=false`) for 2–3 candidate weekends, and compare. Watch for holidays and long weekends that push prices up, like Spanish *puentes*, and suggest the next weekend if one is inflated.
- Sparse results (`success: true` with only 1–3 items) are more common than fully empty ones, and the same caveat applies: they show low search volume, not low availability.
- **Run shell loops under `bash -c '...'`.** The user's shell may be fish, where bash loop syntax fails silently.
- A suspiciously low fare (e.g. €15) is usually a real ULCC promo, but it's the most likely to have sold out. Verify it.
- The `static_fare_key` in `link` contains `H0`/`H1`, a rough hint for no checked bag / checked bag included. Don't rely on it for bag pricing.
