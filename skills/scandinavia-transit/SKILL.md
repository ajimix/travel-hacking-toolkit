---
name: scandinavia-transit
description: Search trains, buses, and ferries across Norway (Entur), Sweden (ResRobot), and Denmark (Rejseplanen) for intra-Scandinavia travel planning. Use when planning ground transport between cities within Scandinavia. Triggers on "train", "bus", "ferry", "Vy", "SJ", "DSB", "Oslo to Bergen", "Stockholm to", "Copenhagen to", "Entur", "ResRobot", "Rejseplanen", "how to get between", "ground transport", "rail", or any intra-Scandinavia routing question.
license: MIT
---

# Scandinavia Transit Skill

Search ground transport (trains, buses, ferries) within Norway, Sweden, and Denmark using their national transit APIs.

**Sources:**

- [Entur (Norway)](https://developer.entur.org) — Open GraphQL API for all Norwegian transit
- [ResRobot (Sweden)](https://www.trafiklab.se/api/trafiklab-apis/resrobot-v21/) — REST API via Trafiklab for all Swedish transit
- [Rejseplanen (Denmark)](https://labs.rejseplanen.dk) — Danish transit (pending API access)

## Norway: Entur (Journey Planner v3)

Open GraphQL API. No key needed (but a client name header is required). Covers ALL Norwegian transit: Vy trains, buses, ferries, trams, metro. 60+ operators.

### Trip Search (Oslo to Bergen example)

```bash
curl -s -X POST "https://api.entur.io/journey-planner/v3/graphql" \
  -H "Content-Type: application/json" \
  -H "ET-Client-Name: $ENTUR_CLIENT_NAME" \
  -d '{"query": "{ trip(from: {place: \"NSR:StopPlace:59872\"}, to: {place: \"NSR:StopPlace:548\"}, numTripPatterns: 5) { tripPatterns { startTime duration legs { mode expectedStartTime expectedEndTime fromPlace { name } toPlace { name } line { publicCode name authority { name } } } } } }"}' | jq '.data.trip.tripPatterns[] | {start: .startTime, duration_min: (.duration / 60), legs: [.legs[] | {mode: .mode, from: .fromPlace.name, to: .toPlace.name, line: .line.publicCode, operator: .line.authority.name, depart: .expectedStartTime, arrive: .expectedEndTime}]}'
```

### Find Stop IDs

Stop IDs use the format `NSR:StopPlace:XXXXX`. Find them via the Geocoder:

```bash
curl -s "https://api.entur.io/geocoder/v1/autocomplete?text=Oslo%20S&size=3" \
  -H "ET-Client-Name: $ENTUR_CLIENT_NAME" | jq '[.features[] | {name: .properties.name, id: .properties.id, type: .properties.layer}]'
```

### Key Stop IDs

| City      | Stop ID             | Name           |
| --------- | ------------------- | -------------- |
| Oslo S    | NSR:StopPlace:59872 | Oslo S         |
| Bergen    | NSR:StopPlace:548   | Bergen stasjon |
| Stavanger | NSR:StopPlace:4130  | Stavanger      |
| Trondheim | NSR:StopPlace:41742 | Trondheim S    |
| Bodo      | NSR:StopPlace:49484 | Bodo stasjon   |

Use the Geocoder to find any stop. Works for airports, ferry terminals, bus stops too.

### Departure Board

```bash
curl -s -X POST "https://api.entur.io/journey-planner/v3/graphql" \
  -H "Content-Type: application/json" \
  -H "ET-Client-Name: $ENTUR_CLIENT_NAME" \
  -d '{"query": "{ stopPlace(id: \"NSR:StopPlace:59872\") { name estimatedCalls(numberOfDepartures: 10) { expectedDepartureTime destinationDisplay { frontText } serviceJourney { journeyPattern { line { publicCode name transportMode } } } } } }"}' | jq '.data.stopPlace | {name: .name, departures: [.estimatedCalls[] | {time: .expectedDepartureTime, destination: .destinationDisplay.frontText, line: .serviceJourney.journeyPattern.line.publicCode, mode: .serviceJourney.journeyPattern.line.transportMode}]}'
```

### Notes

- GraphQL API. POST only. One endpoint: `https://api.entur.io/journey-planner/v3/graphql`
- Set `ET-Client-Name` header on all requests. Entur asks you to use a descriptive name like `yourname-tripplanner`.
- No rate limit key, but respectful usage expected. Don't hammer it.
- Explore the schema at: https://api.entur.io/graphql-explorer/journey-planner-v3
- Covers some cross-border routes into Sweden via Vy and SJ Nord.

## Sweden: ResRobot v2.1

REST API via Trafiklab. Covers ALL Swedish transit: SJ trains, regional buses, ferries, metro, commuter rail.

### Authentication

`RESROBOT_API_KEY` is set in `.env`. Use `accessId` query parameter.

Get a free key at [trafiklab.se](https://www.trafiklab.se) (sign up, create a project, add the ResRobot v2.1 API).

### Trip Search (Stockholm to Gothenburg)

```bash
curl -s "https://api.resrobot.se/v2.1/trip?originId=740000001&destId=740000002&format=json&accessId=$RESROBOT_API_KEY" | jq '[.Trip[] | {start: .LegList.Leg[0].Origin.time, date: .LegList.Leg[0].Origin.date, duration: .duration, legs: [.LegList.Leg[] | {mode: .type, name: .name, from: .Origin.name, to: .Destination.name, depart: .Origin.time, arrive: .Destination.time}]}] | .[0:5]'
```

### Find Stop IDs

```bash
curl -s "https://api.resrobot.se/v2.1/location.name?input=Stockholm&format=json&accessId=$RESROBOT_API_KEY" | jq '[.stopLocationOrCoordLocation[] | .StopLocation | {name: .name, id: .extId}] | .[0:5]'
```

### Key Stop IDs

| City         | Stop ID   | Name                     |
| ------------ | --------- | ------------------------ |
| Stockholm C  | 740000001 | Stockholm Centralstation |
| Gothenburg C | 740000002 | Goteborg Centralstation  |
| Malmo C      | 740000003 | Malmo Centralstation     |
| Uppsala      | 740000025 | Uppsala Centralstation   |
| Linkoping    | 740000009 | Linkoping Centralstation |

### Parameters

| Param      | Required | Description                   |
| ---------- | -------- | ----------------------------- |
| `originId` | Yes      | Departure stop ID             |
| `destId`   | Yes      | Arrival stop ID               |
| `date`     | No       | YYYY-MM-DD (default today)    |
| `time`     | No       | HH:MM (default now)           |
| `format`   | No       | `json` or `xml`               |
| `numTrips` | No       | Number of results (default 5) |
| `products` | No       | Bitmask for transport types   |

### Notes

- REST API. Base: `https://api.resrobot.se/v2.1/`
- 30,000 calls/month on free tier. Plenty for trip planning.
- Includes cross-border Oresund trains to Copenhagen.
- No pricing data. Schedule/route only.

## Denmark: Rejseplanen

Access requires human review. Apply at: https://labs.rejseplanen.dk

Once approved, it covers all Danish transit including DSB trains, buses, metro, ferries. Unique feature: includes fare/zone pricing data.

Until approved, use SerpAPI Google Flights for Copenhagen connections, or Entur/ResRobot for cross-border routes (Oresund trains from Malmo to CPH).

## Cross-Border Routes

| Route                | Covered By       | Notes                      |
| -------------------- | ---------------- | -------------------------- |
| Oslo-Stockholm       | Entur + ResRobot | SJ trains, ~6 hours        |
| Malmo-Copenhagen     | ResRobot         | Oresund trains, 35 min     |
| Gothenburg-Oslo      | Entur + ResRobot | Vy/SJ, ~4 hours            |
| Stockholm-Copenhagen | ResRobot         | SJ/DSB, ~5 hours via Malmo |

## When to Use

Load this skill when:

- Planning train/bus/ferry routes between Scandinavian cities
- Checking schedules and durations for ground transport
- Finding stop IDs for trip planning
- Comparing train vs flight for intra-Scandinavia legs

Do not:

- Use for booking (these APIs are search/schedule only)
- Use for flights (use SerpAPI, Duffel, or other flight search tools instead)
- Expect pricing from Entur or ResRobot (schedule data only, except Rejseplanen when approved)
