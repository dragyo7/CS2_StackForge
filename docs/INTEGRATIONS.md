# External Integrations Registry

This is the source-of-truth inventory for third-party data, software and services. Update this file whenever an integration is added, removed or its terms/access change.

## Integration Source Registry

| Provider | Classification | Official URL | API access | Key required | Available fields | Refresh policy | Attribution | Implementation status |
|---|---|---|---|---|---|---|---|---|
| **Google Sheets (CSV Export)** | Official (Read-only public link) | https://docs.google.com/spreadsheets/ | Public CSV export (`/export?format=csv`) | No (if link-readable) | Community spreadsheet columns (`Name`, `Url`, `IGN`, optional rating/role) | Manual Preview / Sync Now | Source URL stored in `spreadsheet_imports` | **Implemented & Live-Tested** |
| **Steam Web API** | Official | https://partner.steamgames.com/doc/webapi/ISteamUser | REST (`GetPlayerSummaries`, `GetPlayerBans`, `ResolveVanityURL`) + public `?xml=1` fallback | Optional for summaries/vanity; Required (`STEAM_API_KEY`) for `GetPlayerBans` | Persona name, avatar, visibility, VAC/game/community/economy ban counts | Individual/Auto TTL (`900s`), single-flight | Link to `steamcommunity.com/profiles/{id}` | **Partial (`?xml=1` Live-Tested; `GetPlayerBans` `NOT_CONFIGURED`)** |
| **Leetify Public CS API** | Third-party | https://api-public-docs.cs-prod.leetify.com/ | REST `/v3/profile`, `/v3/profile/matches` | Optional (`LEETIFY_API_KEY`) | `ranks` (`premier`, `leetify`, `faceit`, `faceit_elo`), `rating` (`aim`, `utility`, `positioning`, `clutch`), `stats` (`preaim`, `reaction_time_ms`, `accuracy_enemy_spotted`, `accuracy_head`, `spray_accuracy`, `counter_strafing_good_shots_ratio`, opening duels, trade kills, HE dmg, flashes), recent matches | Individual/Auto TTL (`1800s`), 429 `Retry-After` + backoff (`PARTIAL` if matches fail) | Link to `leetify.com/app/profile/{id}`; `kast` unavailable | **Implemented & Live-Tested (V2 fields)** |
| **FACEIT Data API v4** | Official (Third-party platform) | https://docs.faceit.com/docs/data-api/ | REST `/players`, `/players/{id}/stats/cs2` | Yes (`FACEIT_API_KEY`) | FACEIT ID, nickname, ELO, skill level, CS2 lifetime matches/win%/KD/HS%/ADR | Manual/TTL cached | Link to `faceit.com` profile | **Implemented** (`NOT_CONFIGURED` fallback tested; live calls untested pending key) |
| **CSWatch Public JSON API** | Third-party | https://cswatch.gg/ | REST `/api/public/player/{steamId}` | No (fair use <= 30 req/min/IP) | Persona name, avatar, reputation score, risk level, ban summary, breakdown, factors | On-demand Trust Check / Refresh (25/min limiter) | Required link to `cswatch.gg/player/{id}`; not Valve verdict | **Implemented & Live-Tested** |
| **CSStats.gg** | Unsupported API (Link-only) | https://csstats.gg/ | No documented public API (Cloudflare-gated) | N/A | Canonical `SteamID64` extracted from `/player/{steamid64}` URL; manual/CSV import only | N/A (no scraping) | Direct profile link only | **URL extraction & link only** (no scraping) |
| **CS2SUS / Cheatscanner / CS2Track** | Reference-only | See below | None confirmed | N/A | Methodology reference only | N/A | N/A | **Reference only** |

## Read-Only Anti-Cheat Safety Model
StackForge never injects into CS2, reads/writes game memory, modifies game files, simulates player input, automates Valve matchmaking queues, or scrapes Cloudflare-gated websites. All integrations are strictly read-only external HTTP requests or offline spreadsheet/demo inputs.

## Status definitions
- **Core planned:** expected in product, not necessarily implemented.
- **Candidate:** evaluate license, maintenance, API and compatibility before adoption.
- **Reference only:** learn from public product/methodology; do not scrape or ingest its data.
- **Blocked:** requires provider approval/key/terms verification.
- **Implemented:** only mark after code, tests and operational verification.

## Registry

### Valve / Steam
- **Product:** Steam Web API.
- **Endpoints:** `ISteamUser/ResolveVanityURL/v1`, `ISteamUser/GetPlayerSummaries/v2`, `ISteamUser/GetPlayerBans/v1`.
- **Use:** Resolve vanity URLs to canonical SteamID64; refresh public persona name/avatar and record alias changes in `player_aliases`; check VAC/game/community/economy ban response.
- **Auth:** Server-side `STEAM_API_KEY` env var (`ISteamUser/*`); falls back cleanly to public `https://steamcommunity.com/id/{vanity}/?xml=1` and `/profiles/{sid}/?xml=1` when keyless. Steam OpenID identity login remains deferred.
- **Limits/caveats:** Public profile fields only; API access and key terms apply. `GetPlayerBans` returns ban counts/status and may include app-related details; never infer CS2 cheating from a generic count alone. Steam's CS2 game-ban policy includes cheating, matchmaking rank manipulation, botting/automation and interference with game systems.
- **Docs:** https://partner.steamgames.com/doc/webapi/ISteamUser
- **Policy:** https://help.steampowered.com/en/faqs/view/4E54-0B96-D0A4-1557
- **Status:** Adapter implemented (`backend/app/providers/steam.py`); `?xml=1` profile/vanity resolution is active and live-tested keyless, while official `GetPlayerBans` stays `NOT_CONFIGURED` until `STEAM_API_KEY` is provided.

### FACEIT
- **Product:** FACEIT Data API v4.
- **Endpoints:** `GET /players?game=cs2&game_player_id={steamid64}`, `GET /players/{player_id}/stats/cs2`.
- **Use:** Fetch ELO/level plus lifetime CS2 combat stats (`Matches`, `Win Rate %`, `Average K/D Ratio`, `Average Headshots %`, `ADR`) stored in `player_stat_snapshots`.
- **Auth:** Server-side `FACEIT_API_KEY` env var.
- **Limits/caveats:** Publicly available data only, API rate limits and HTTP 401/403/404/429/503 handling. Verify developer terms before public/commercial launch.
- **Docs:** https://docs.faceit.com/docs/data-api/
- **Player docs:** https://docs.faceit.com/docs/data-api/data/
- **Status:** Adapter implemented (`backend/app/providers/external.py`) with `NOT_CONFIGURED`/`UNAVAILABLE` fallback; live API calls untested pending `FACEIT_API_KEY` (Steam-linked FACEIT level/ELO still arrives via Leetify `ranks` when exposed).

### Leetify
- **Product:** Leetify Public CS API v3.
- **Endpoints:** `GET /v3/profile?steam64_id={steam64_id}` and `GET /v3/profile/matches?steam64_id={steam64_id}`.
- **Use:** Fetch Leetify rating, Premier CSR, FACEIT ELO/level (when linked), sub-ratings (`aim`, `utility`, `positioning`, `clutch`), mechanics (`preaim`, `reaction_time_ms`, `accuracy_enemy_spotted`, `spray_accuracy`, `counter_strafing_good_shots_ratio`), opening duels, trades, utility dmg, flash stats, recent-10/30 aggregates, recent match history (`<=15`), and private per-map deltas (`PARTIAL` if profile succeeds while matches fail).
- **Auth:** Optional server-side `LEETIFY_API_KEY` env var (`_leetify_key` header); works keyless in read-only mode with 3-attempt `Retry-After`/exponential backoff on HTTP 429.
- **Limits/caveats:** Keyless mode incurs stricter throttling (`429 RATE_LIMITED`). `kast` is not returned on public v3 endpoints and remains `Unavailable`. Follow developer guidelines and attribution; do not scrape private data.
- **Docs:** https://api-public-docs.cs-prod.leetify.com/
- **Developer guidelines:** https://leetify.com/app/developer (check current in-product terms)
- **Status:** Implemented & Live-Tested (`backend/app/providers/external.py`).

### Premier rating / history sources
- **Valve public API:** No dependable supported public endpoint for complete Premier rating/history is assumed by this project.
- **Leetify:** Use Premier fields only if returned for the player and source/period are clear.
- **Third-party trackers:** Evaluate only if they provide a documented, authorized API and terms permitting display/storage.
- **Local CS2 Game State Integration:** Optional companion can capture local opted-in user's future game-state events; does not backfill all players or provide global Premier history.
- **Reference project:** https://github.com/pkia/cs2-tracker
- **Status:** Provider evaluation; no scraping.

### CSWatch
- **Product:** CSWatch public JSON API and embeds.
- **Use:** Separated third-party reputation/risk signal (`THIRD_PARTY_REPUTATION`) with source attribution and direct profile link; stored with observation timestamp independently of Steam enforcement.
- **API:** https://www.cswatch.gg/developers
- **Endpoint documented:** `GET https://cswatch.gg/api/public/player/{steamId}`
- **Published fair-use statement:** up to 30 player requests/minute/IP (StackForge enforces a 25/min sliding window cap); attribution link required. Keyed API available on request.
- **Caveats:** Third-party reputation, not Valve truth. Review methodology and privacy/terms before commercial launch or public/commercial redistribution.
- **Status:** Implemented & Live-Tested (`backend/app/providers/cswatch.py`).

### CS2SUS
- **Product:** Website for CS2 stats and demo-derived suspiciousness signals.
- **Use:** Research reference for combined Steam/FACEIT/Leetify data and demo-analysis methodology.
- **Website:** https://cs2sus.com/
- **Caveats:** Its FAQ says the score is an anomaly measure, not proof of cheating; no documented public API was confirmed in this review. Do not scrape or ingest scores without permission.
- **Status:** Reference only.

### Cheatscanner.eu
- **Product:** CS2 demo evidence analysis website.
- **Use:** Research reference for evidence-oriented demo analysis and signal explanations.
- **Website:** https://cheatscanner.eu/
- **Caveats:** No public integration API/redistribution permission confirmed. Do not scrape. Prefer our own user-submitted demos and open-source parser.
- **Status:** Reference only.

### CS2Track
- **Product:** CS2 stats tracker and cheater watchlist.
- **Use:** UX reference for watchlists, ban change monitoring and multi-source player profiles.
- **Website:** https://cs2track.com/
- **Caveats:** No authorized public API contract confirmed during this review.
- **Status:** Reference only.

### VACWatch
- **Product:** Steam ban monitoring reference.
- **Website:** https://vac.watch/
- **Use:** Study watchlist/ban-history UX.
- **Caveats:** Verify current API access and terms before any integration.
- **Status:** Reference only.

### CS.Ninja
- **Product:** Player trust/stat checker.
- **Website:** https://cs.ninja/
- **Use:** UI/reference for multi-signal trust explanation.
- **Caveats:** A third-party trust estimate is not Valve Trust Factor.
- **Status:** Reference only.

### Awpy
- **Repository:** https://github.com/pnxenopoulos/awpy
- **Docs:** https://awpy.readthedocs.io/en/latest/
- **Use:** Parse CS2 `.dem` files; rounds, kills, damages, shots, player state, stats, line of sight/navigation where supported.
- **License:** MIT per repository; retain license/notice.
- **Requirements noted in docs:** Python 3.11+, Polars 2.x; verify pinned release compatibility at implementation time.
- **Caveats:** Demo parsing is asynchronous; map assets extracted from game files have separate Valve IP/licensing considerations.
- **Status:** Preferred parser candidate.

### demoparser2
- **Repository:** https://github.com/LaihoE/demoparser
- **Use:** Alternative Rust-backed CS2 demo parser with Python/JavaScript integration.
- **License:** Verify current repository LICENSE before adding; pin version and preserve notices.
- **Status:** Alternative candidate.

### Discord
- **Docs:** https://discord.com/developers/docs
- **Use:** Later slash commands, room links, approvals and notifications.
- **Caveats:** OAuth scopes, bot permissions, rate limits and Discord policy.
- **Status:** Later release.

### Official API Key Acquisition & Keyless Operation
- **Keyless mode works out of the box** via Steam Community XML (`?xml=1`), Leetify Public CS API v3, CSWatch Public API, Google Sheets CSV, and host-recorded match outcomes.
- Optional keys (`STEAM_API_KEY`, `FACEIT_API_KEY`, `LEETIFY_API_KEY`) can be entered in the **Ops & Keys** tab (`PUT /api/settings/credentials/{provider}`) where they are encrypted server-side via **Windows DPAPI** (`CryptProtectData`, stored outside SQLite and never returned to the browser) or placed in `backend/.env`:
  - **Steam Web API (`STEAM_API_KEY`):** Obtain via `https://steamcommunity.com/dev/apikey` (required only for official `GetPlayerBans` & keyed `GetPlayerSummaries`).
  - **FACEIT Data API (`FACEIT_API_KEY`):** Create an app & server-side API key at `https://developers.faceit.com/`.
  - **Leetify Developer Key (`LEETIFY_API_KEY`):** Create an optional developer key at `https://leetify.com/app/developer` for higher throughput.

## Integration acceptance checklist
Before implementation:
- [ ] Current docs read.
- [ ] API key/access confirmed.
- [ ] Terms and commercial use checked.
- [ ] Rate limits recorded.
- [ ] Privacy/visibility behaviour tested.
- [ ] Data fields and provenance mapped.
- [ ] Error responses and retry rules implemented.
- [ ] Attribution requirements met.
- [ ] No scraping unless explicitly permitted.
- [ ] Provider adapter tests and fixture snapshots added.
