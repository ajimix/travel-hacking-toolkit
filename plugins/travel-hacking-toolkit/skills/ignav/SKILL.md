---
name: ignav
description: Search for flights using the Ignav flights API. Use this skill whenever the user wants to find flights, compare flight prices, check flight availability, or search for airline routes. Triggers on any flight-related search request including "find me a flight", "how much to fly to X", "cheapest flights from A to B", "flights next weekend", or similar. This skill uses a fast API instead of browser automation, so prefer it over browser-based alternatives. **Always include in every flight search** — runs in parallel with other sources.
category: flights
summary: Fast REST API flight search. Cash prices and booking links.
api_key: Ignav (1,000 free)
allowed-tools: Bash(curl *)
---

# Flight Search via Ignav API

This skill searches for flights using the Ignav REST API at `https://ignav.com`. It's faster and more reliable than browser-based scraping — just HTTP requests with `curl`.

## Authentication

All requests require the `X-Api-Key` header. The `$IGNAV_API_KEY` environment variable is pre-loaded via `.claude/settings.local.json` — available in every Bash call automatically, no sourcing needed.

## Workflow

1. **Parse the user's request** — extract origin, destination, dates, trip type, passengers, cabin class
2. **Look up airport codes** if the user gave city names
3. **Search flights** (one-way or round-trip)
4. **Present results** clearly
5. **Get booking links** if the user wants to book a specific flight

## Endpoints

### 1. Search Airports

Use this when the user provides city names instead of airport codes (e.g., "Barcelona" instead of "BCN").

```bash
curl -s "https://ignav.com/api/airports?q=Barcelona&limit=5" \
  -H "X-Api-Key: $IGNAV_API_KEY"
```

Returns an array of airports with `code`, `name`, `city`, and `country`. Use the `code` for flight searches.

If the query is ambiguous (e.g., "London" has multiple airports), show the options and ask the user which one, or search for all of them.

### 2. Search One-Way Flights

```bash
curl -s -X POST "https://ignav.com/api/fares/one-way" \
  -H "X-Api-Key: $IGNAV_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "BCN",
    "destination": "LHR",
    "departure_date": "2026-05-15",
    "adults": 1,
    "cabin_class": "economy"
  }'
```

### 3. Search Round-Trip Flights

```bash
curl -s -X POST "https://ignav.com/api/fares/round-trip" \
  -H "X-Api-Key: $IGNAV_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "BCN",
    "destination": "LHR",
    "departure_date": "2026-05-15",
    "return_date": "2026-05-20",
    "adults": 1,
    "cabin_class": "economy"
  }'
```

### 4. Get Booking Links

Once the user picks a flight, use its `ignav_id` to get booking links:

```bash
curl -s -X POST "https://ignav.com/api/fares/booking-links" \
  -H "X-Api-Key: $IGNAV_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "ignav_id": "the_itinerary_id",
    "adults": 1
  }'
```

Returns booking options with provider name, type (airline or third_party), price, and direct booking URL.

## Full Parameter Reference

Both one-way and round-trip endpoints accept these optional parameters beyond the basics:

| Parameter                | Type    | Description                                                                                                                                                                                                                         |
| ------------------------ | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `adults`                 | integer | Number of adults (default: 1)                                                                                                                                                                                                       |
| `children`               | integer | Number of children (default: 0)                                                                                                                                                                                                     |
| `infants_in_seat`        | integer | Infants with own seat (default: 0)                                                                                                                                                                                                  |
| `infants_on_lap`         | integer | Lap infants (default: 0)                                                                                                                                                                                                            |
| `cabin_class`            | string  | `economy`, `premium_economy`, `business`, `first`                                                                                                                                                                                   |
| `max_stops`              | integer | 0 (direct only), 1, or 2                                                                                                                                                                                                            |
| `max_price`              | integer | Maximum price filter                                                                                                                                                                                                                |
| `min_carry_on_bags`      | integer | Minimum carry-on bags included                                                                                                                                                                                                      |
| `min_checked_bags`       | integer | Minimum checked bags included                                                                                                                                                                                                       |
| `departure_time_range`   | object  | `{"earliest_hour": 8, "latest_hour": 20}`                                                                                                                                                                                           |
| `return_time_range`      | object  | Same as above, for return leg (round-trip only)                                                                                                                                                                                     |
| `airlines_include`       | array   | Only these airline codes                                                                                                                                                                                                            |
| `airlines_exclude`       | array   | Exclude these airline codes                                                                                                                                                                                                         |
| `allow_separate_tickets` | boolean | Allow separate tickets per leg (default: true)                                                                                                                                                                                      |
| `market`                 | string  | Country code for pricing locale (default: "US"). Use ISO 3166-1 alpha-2 codes: `US`, `TH`, `JP`, `ES`, `GB`, etc. Different markets return different prices for the same route. Set per the Market Selection Strategy in CLAUDE.md. |

## Understanding the Response

The search endpoints return a `FareSearchResponse` containing an `itineraries` array. Each itinerary has:

- **`price`**: `{ "amount": 125.50, "currency": "EUR" }`
- **`outbound`**: A leg with `carrier`, `duration_minutes`, and `segments` array
- **`inbound`**: Same structure (null for one-way)
- **`cabin_class`**: The cabin class
- **`bags`**: `{ "carry_on": 1, "checked": 0 }` — baggage allowance
- **`ignav_id`**: Unique ID for booking links

Each **segment** within a leg represents one flight:

- `marketing_carrier_code` + `flight_number` (e.g., "VY" + "1234")
- `operating_carrier_name` (the airline actually operating)
- `departure_airport`, `departure_time_local`, `departure_timezone`
- `arrival_airport`, `arrival_time_local`, `arrival_timezone`
- `duration_minutes`
- `aircraft`

A leg with multiple segments means there's a connection. The layover time is the gap between one segment's arrival and the next segment's departure.

## Presenting Results

**Always use markdown tables** for flight results. Tables make it easy to scan and compare options at a glance.

### One-way or single cabin

| #   | Airline | Stops        | Duration | Depart   | Arrive   | Price | Bags                  |
| --- | ------- | ------------ | -------- | -------- | -------- | ----- | --------------------- |
| 1   | Vueling | Nonstop      | 2h 15m   | 8:30 AM  | 10:45 AM | €125  | 1 carry-on            |
| 2   | Ryanair | Nonstop      | 2h 20m   | 6:15 AM  | 8:35 AM  | €89   | 1 carry-on            |
| 3   | BA      | 1 stop · MAD | 5h 40m   | 11:00 AM | 4:40 PM  | €210  | 1 carry-on, 1 checked |

### Round-trip

| #   | Airline | Stops        | Duration | Outbound           | Return            | Price | Bags                  |
| --- | ------- | ------------ | -------- | ------------------ | ----------------- | ----- | --------------------- |
| 1   | Vueling | Nonstop      | 2h 15m   | 8:30 AM → 10:45 AM | 6:00 PM → 8:10 PM | €245  | 1 carry-on            |
| 2   | BA      | 1 stop · MAD | 5h 40m   | 11:00 AM → 4:40 PM | 3:15 PM → 8:50 PM | €398  | 1 carry-on, 1 checked |

### Format rules

- Use markdown table with one row per itinerary
- Columns: #, Airline, Stops, Duration, time columns, Price, Bags
- For connections, show stop cities in the Stops column (e.g., "1 stop · MAD")
- Include Bags column when baggage allowances differ between options; omit if all are identical
- No code blocks around the table — render as actual markdown

### After the table

- **Highlight** the cheapest, fastest, and best-value options
- **Call out tradeoffs** — e.g., "40€ cheaper but adds a 4-hour layover in Rome"
- **Offer booking links** — ask if they want booking links for any specific flight

## Tips

- If the user doesn't specify dates, ask — dates are required for all searches.
- Default to round-trip if the user doesn't specify trip type.
- Default to economy class and 1 adult if not specified.
- Use the airport search endpoint liberally — it's fast and avoids guessing codes wrong.
- When the user says "direct flights only", set `max_stops: 0`.
- When the user mentions time preferences like "morning flight", use `departure_time_range` (e.g., `{"earliest_hour": 6, "latest_hour": 12}`).
- **Market affects prices.** The same route can cost significantly less when searched from a different market. Follow the Market Selection Strategy in CLAUDE.md: try departure country, then destination country, then ask the user before trying more.
