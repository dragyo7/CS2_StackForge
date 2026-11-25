# External Integrations Registry

This is the source-of-truth inventory for third-party data, software and services. Update this file whenever an integration is added, removed or its terms/access change.

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
- **Auth:** Server-side `STEAM_API_KEY` env var. Steam OpenID identity login remains deferred.
- **Limits/caveats:** Public profile fields only; API access and key terms apply. `GetPlayerBans` returns ban counts/status and may include app-related details; never infer CS2 cheating from a generic count alone. Steam's CS2 game-ban policy includes cheating, matchmaking rank manipulation, botting/automation and interference with game systems.
- **Docs:** https://partner.steamgames.com/doc/webapi/ISteamUser
- **Policy:** https://help.steampowered.com/en/faqs/view/4E54-0B96-D0A4-1557
- **Status:** Adapter implemented (`backend/app/providers/steam.py`) with bounded timeouts and `NOT_CONFIGURED`/`UNAVAILABLE` fallback; live API calls untested pending `STEAM_API_KEY`.

### FACEIT
- **Product:** FACEIT Data API v4.
- **Endpoints:** `GET /players?game=cs2&game_player_id={steamid64}`, `GET /players/{player_id}/stats/cs2`.
- **Use:** Fetch ELO/level plus lifetime CS2 combat stats (`Matches`, `Win Rate %`, `Average K/D Ratio`, `Average Headshots %`, `ADR`) stored in `player_stat_snapshots`.
- **Auth:** Server-side `FACEIT_API_KEY` env var.
- **Limits/caveats:** Publicly available data only, API rate limits and HTTP 401/403/404/429/503 handling. Verify developer terms before public/commercial launch.
- **Docs:** https://docs.faceit.com/docs/data-api/
- **Player docs:** https://docs.faceit.com/docs/data-api/data/
- **Status:** Adapter implemented (`backend/app/providers/external.py`) with `NOT_CONFIGURED`/`UNAVAILABLE` fallback; live API calls untested pending `FACEIT_API_KEY`.

### Leetify
- **Product:** Leetify Public CS API.
- **Endpoint:** `GET /v3/profile?steam64_id={steam64_id}`.
- **Use:** Fetch Leetify rating, Premier rank where exposed, and CS2 stats (`total_matches`, `winrate`, `kd_ratio`, `dpr`/`adr`, `kast`, `hs_pct`, `opening_duel_success_pct`, `he_foes_damage_avg`, `flash_assist`, `clutch_win_pct`) stored in `player_stat_snapshots`.
- **Auth:** Server-side `LEETIFY_API_KEY` env var (`_leetify_key` header); public API aligns with Leetify privacy settings.
- **Limits/caveats:** Follow developer guidelines and attribution. Do not imply affiliation or sponsorship. Do not scrape private data.
- **Docs:** https://api-public-docs.cs-prod.leetify.com/
- **Developer guidelines:** https://leetify.com/app/developer (check current in-product terms)
- **Status:** Adapter implemented (`backend/app/providers/external.py`) with `NOT_CONFIGURED`/`UNAVAILABLE` fallback; live API calls untested pending `LEETIFY_API_KEY`.

### Premier rating / history sources
- **Valve public API:** No dependable supported public endpoint for complete Premier rating/history is assumed by this project.
- **Leetify:** Use Premier fields only if returned for the player and source/period are clear.
- **Third-party trackers:** Evaluate only if they provide a documented, authorized API and terms permitting display/storage.
- **Local CS2 Game State Integration:** Optional companion can capture local opted-in user's future game-state events; does not backfill all players or provide global Premier history.
- **Reference project:** https://github.com/pkia/cs2-tracker
- **Status:** Provider evaluation; no scraping.

### CSWatch
- **Product:** CSWatch public JSON API and embeds.
- **Use:** Optional external reputation/conviction signal; display source attribution and direct profile link; store response timestamp and provider label separately from Steam enforcement.
- **API:** https://www.cswatch.gg/developers
- **Endpoint documented:** `GET https://cswatch.gg/api/public/player/{steamId}`
- **Published fair-use statement:** up to 30 player requests/minute/IP; attribution link required. Keyed API available on request.
- **Caveats:** Third-party reputation, not Valve truth. Review methodology and privacy/terms before commercial use. Do not mirror public accusations without policy/legal review.
- **Status:** Optional adapter, pending legal/product review.

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
