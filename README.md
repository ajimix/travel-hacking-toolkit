# Travel Hacking Toolkit

AI-powered travel hacking — find the cheapest flights and hotels across every source. Drop-in skills and MCP servers for [OpenCode](https://opencode.ai) and [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

Ask your AI to find you a cheap business class flight to Tokyo. It'll search cash prices across multiple sources, compare routings, and tell you the cheapest way to book.

## Quick Start

```bash
git clone https://github.com/borski/travel-hacking-toolkit.git
cd travel-hacking-toolkit
./scripts/setup.sh
```

The setup script walks you through everything: picks your tool (OpenCode, Claude Code, or both), creates your API key config files, installs dependencies, and optionally installs skills system-wide.

The 5 free MCP servers (Skiplagged, Kiwi, Trivago, Ferryhopper, Airbnb) work immediately with zero API keys. For the full experience, add at minimum:

| Key               | Why                     | Free Tier             |
| ----------------- | ----------------------- | --------------------- |
| `SERPAPI_API_KEY` | Flight and hotel search | Yes (100 searches/mo) |

Then launch your tool:

```bash
# OpenCode
opencode

# Claude Code
claude --strict-mcp-config --mcp-config .mcp.json
```

The `--strict-mcp-config` flag tells Claude Code to load MCP servers from the config file directly. This is more reliable than auto-discovery ([known issue](https://github.com/anthropics/claude-code/issues/5037)).

## What's Included

### MCP Servers (real-time tools)

| Server                                                | What It Does                                                                                            | API Key                           |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | --------------------------------- |
| [Skiplagged](https://skiplagged.com)                  | Flight search with hidden city fares                                                                    | None (free)                       |
| [Kiwi.com](https://www.kiwi.com)                      | Flights with virtual interlining (creative cross-airline routing)                                       | None (free)                       |
| [Trivago](https://mcp.trivago.com/docs)               | Hotel metasearch across booking sites                                                                   | None (free)                       |
| [Ferryhopper](https://ferryhopper.github.io/fh-mcp/)  | Ferry routes across 33 countries, 190+ operators                                                        | None (free)                       |
| [Airbnb](https://github.com/borski/mcp-server-airbnb) | Search Airbnb listings, property details, pricing. Patched with geocoding fix and property type filter. | None (free)                       |
| [LiteAPI](https://mcp.liteapi.travel)                 | Hotel search with live rates and booking                                                                | [LiteAPI](https://liteapi.travel) |

### Skills (API knowledge for your AI)

| Skill                   | What It Does                                              | API Key                                                                      |
| ----------------------- | --------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **duffel**              | Real-time flight search across airlines via Duffel API    | [Duffel](https://duffel.com)                                                 |
| **serpapi**             | Google Flights cash prices, hotels, destination discovery | [SerpAPI](https://serpapi.com)                                               |
| **rapidapi**            | Secondary prices via Google Flights Live + Booking.com    | [RapidAPI](https://rapidapi.com)                                             |
| **atlas-obscura**       | Hidden gems near any destination                          | None (free)                                                                  |
| **scandinavia-transit** | Trains, buses, ferries in Norway/Sweden/Denmark           | [Entur](https://developer.entur.org) + [Trafiklab](https://www.trafiklab.se) |

## How It Works

### Skills

Skills are markdown files that teach your AI how to call travel APIs. They contain endpoint documentation, curl examples, useful jq filters, and workflow guidance. Both OpenCode and Claude Code support skills natively.

The `skills/` directory is the canonical source. The setup script either:

- Copies them to your tool's global skills directory (`~/.config/opencode/skills/` or `~/.claude/skills/`)
- Or creates project-level symlinks so they load when you work from this directory

### MCP Servers

MCP (Model Context Protocol) servers give your AI real-time tools it can call directly. The configs are in:

- `opencode.json` for OpenCode
- `.mcp.json` for Claude Code

Skiplagged, Kiwi.com, Trivago, Ferryhopper, and Airbnb need no setup at all. LiteAPI is also a remote server but needs an API key configured in your settings.

## The Travel Hacking Workflow

1. **Search cash prices** across sources — google-flights, Ignav, SerpAPI, Duffel, Skiplagged, Kiwi
2. **Compare prices and routings** — different sources return different fares for the same flight
3. **Exploit market arbitrage** — searching from a different country's market can unlock cheaper fares
4. **Try creative routings** — hidden city fares (Skiplagged), virtual interlining (Kiwi), open jaw
5. **Book the cheapest option** — use booking links from search results or book direct with the airline

### Example Prompts

```
"Find me the cheapest business class flight from SFO to Tokyo in August"
"Search hotels in Lisbon under $150/night for next March"
"Find hidden gems near Lisbon"
"How do I get from Oslo to Bergen by train?"
```

## Project Structure

```
travel-hacking-toolkit/
├── AGENTS.md -> CLAUDE.md          # OpenCode project instructions (symlink)
├── CLAUDE.md                       # Project instructions and workflow guidance
├── opencode.json                   # OpenCode MCP server config
├── .mcp.json                       # Claude Code MCP server config
├── .env.example                    # API key template (OpenCode)
├── .claude/
│   ├── settings.local.json.example # API key template (Claude Code)
│   └── skills -> ../skills         # Symlink to skills
├── .opencode/
│   └── skills -> ../skills         # Symlink to skills
├── skills/
│   ├── duffel/SKILL.md             # Real-time flight search
│   ├── google-flights/SKILL.md     # Browser-automated Google Flights
│   ├── ignav/SKILL.md              # Fast flight search API
│   ├── serpapi/SKILL.md            # Cash prices + hotels
│   ├── rapidapi/SKILL.md           # Secondary price source
│   ├── atlas-obscura/              # Hidden gems (+ Node.js scraper)
│   │   ├── SKILL.md
│   │   ├── ao.mjs
│   │   └── package.json
│   └── scandinavia-transit/        # Nordic trains/buses/ferries
│       └── SKILL.md
├── scripts/
│   └── setup.sh                    # Interactive installer
└── LICENSE                         # MIT
```

## Credits

Built on these excellent projects:

- [Duffel](https://duffel.com) — Real-time flight search and booking
- [SerpAPI](https://serpapi.com) — Google search result APIs
- [RapidAPI](https://rapidapi.com) — API marketplace
- [atlas-obscura-api](https://github.com/bartholomej/atlas-obscura-api) by [@bartholomej](https://github.com/bartholomej) — Atlas Obscura scraper
- [Skiplagged MCP](https://mcp.skiplagged.com) — Flight search with hidden city fares
- [Kiwi.com MCP](https://www.kiwi.com/stories/kiwi-mcp-connector/) — Flight search with virtual interlining
- [Trivago MCP](https://mcp.trivago.com/docs) — Hotel metasearch
- [Ferryhopper MCP](https://ferryhopper.github.io/fh-mcp/) by [Ferryhopper](https://ferryhopper.com) — Ferry routes across 33 countries
- [mcp-server-airbnb](https://github.com/openbnb-org/mcp-server-airbnb) by [OpenBnB](https://github.com/openbnb-org) — Airbnb search and listing details
- [LiteAPI MCP](https://mcp.liteapi.travel) by [LiteAPI](https://liteapi.travel) — Hotel booking
- [Entur](https://developer.entur.org) — Norwegian transit API
- [Trafiklab / ResRobot](https://www.trafiklab.se) — Swedish transit API
- [Rejseplanen](https://labs.rejseplanen.dk) — Danish transit API

## License

MIT
