# CS2 Ecosystem Research, Provider Intelligence & Trust Governance

**Research Date:** 2026-11-26  
**Baseline Commit Reviewed:** `97e2fff` (with CSWatch `storedAt`/`stale`/`convictionCount`/`isCheater` hardening)  
**Policy Rule:** StackForge never claims affiliation with Valve or access to proprietary CS2 internals, never scrapes protected pages, and never infers Valve Trust Factor or cheat guilt from raw stats or incomplete external signals.

---

## 1. Provider Status Matrix (Code-Verified as of 2026-11-26)

| Category | Providers / Modules | Code Evidence | Notes |
|---|---|---|---|
| **Implemented and Working (Keyless)** | Steam Community XML (`?xml=1`), Leetify Public CS API v3 (`ranks`, `rating`, `stats`, `/matches`), CSWatch Public JSON API (`/api/public/player/{steamId}`), Google Sheets CSV / local `.csv` & `.xlsx` | [steam.py](file:///d:/CS2_StackForge/backend/app/providers/steam.py), [external.py](file:///d:/CS2_StackForge/backend/app/providers/external.py), [cswatch.py](file:///d:/CS2_StackForge/backend/app/providers/cswatch.py), [import_service.py](file:///d:/CS2_StackForge/backend/app/services/import_service.py) | Active out-of-the-box without user credentials; bounded by fair-use caps & per-provider TTLs. |
| **Implemented but Limited** | **Leetify v3** (`kast` unavailable; private/unlinked profiles; stricter keyless HTTP 429 throttling); **CSWatch** (500 req/day & 30/min fair-use cap; >24h cache flagged `STALE`; unindexed returned `UNKNOWN`); **CSStats.gg** (`SteamID64` URL extraction & link-out only — Cloudflare-gated, never scraped) | [external.py](file:///d:/CS2_StackForge/backend/app/providers/external.py), [cswatch.py](file:///d:/CS2_StackForge/backend/app/providers/cswatch.py), [steam_parser.py](file:///d:/CS2_StackForge/backend/app/services/steam_parser.py) | Missing/private/stale values always remain explicit (`None` / `UNKNOWN` / `STALE`), never zero-filled or converted into clean verdicts. |
| **Requires Credentials (`NOT_CONFIGURED` until key supplied)** | **Steam Web API (`GetPlayerSummaries/v2`, `GetPlayerBans/v1`, `ResolveVanityURL/v1`)** (`STEAM_API_KEY`); **FACEIT Data API v4** (`FACEIT_API_KEY`); optional **Leetify Developer Key** (`LEETIFY_API_KEY`) | [secrets_service.py](file:///d:/CS2_StackForge/backend/app/services/secrets_service.py), [steam.py](file:///d:/CS2_StackForge/backend/app/providers/steam.py), [external.py](file:///d:/CS2_StackForge/backend/app/providers/external.py) | Stored encrypted server-side via Windows DPAPI vault (`*.dpapi.json`) or backend `.env`. App runs core workflows cleanly without them. |
| **Research Only** | `Scope.gg`, `CSST.at`, `HLTV`, `BO3.gg`, `CStrike.gg Trust`, `Suspect.gg` / `CSRep.gg`, `CS.Ninja`, `Awpy`, `demoparser2`, `TimAnthonyAlexander/demo-anticheat` | [DEMO_PIPELINE.md](file:///d:/CS2_StackForge/docs/DEMO_PIPELINE.md) | Documented for methodology, parser selection (`Awpy` recommended for async P3 pipeline), or future opt-in evaluation. |
| **Unsupported / Not Recommended** | `Tracker.gg` (CS:GO API deprecated; CS2 integration gated/scraping prohibited), `CSMeta.gg` (no public developer API), `Mercurial.gg` (TOS prohibits scraping/systematic dataset storage), HLTV/CSStats scraping | N/A (`0` integration code) | Rejected for automated ingestion to respect platform TOS, anti-bot protections, and reliability. |

---

## 2. Ecosystem Evaluation Matrix

### A. Statistics & Performance Platforms

| Source | Purpose & Useful Features | Available Signals / Stats | Public API & Auth | Rate Limits & Freshness | Pricing / Access | TOS, Attribution & Scraping | Suitable? | Integrated? | Action |
|---|---|---|---|---|---|---|---|---|---|
| **Leetify**<br>https://leetify.com/<br>https://api-public-docs.cs-prod.leetify.com/ | Detailed CS2 skill analytics, aim/utility/positioning mechanics, recent match history | `ranks.premier`, `ranks.leetify`, linked `faceit`/`faceit_elo`, `rating.{aim,utility,positioning,clutch}`, preaim, time-to-damage, spotted/spray accuracy, counter-strafe %, opening duels, trade kills/deaths, HE dmg, flash assists, enemies flashed. **No KAST on v3.** | **Yes (official):** `GET /v3/profile`, `/v3/profile/matches`, `/v2/matches/{id}`, `/api-key/validate`. Key optional (`_leetify_key` / `Bearer`). | Keyless allowed but incurs **stricter dynamic HTTP 429 throttling**; private profiles return `privacy_mode: "private"`. StackForge TTL `1800s`. | Free developer key at `leetify.com/app/developer`; privacy-aligned public access. | Respect privacy flags, attribution & developer guidelines; never scrape private accounts. | **Yes (core)** | **Yes (Active)** | **USE** |
| **FACEIT**<br>https://www.faceit.com/<br>https://developers.faceit.com/ | Competitive 5v5 ladder ELO, skill levels (1–10), match history | `games.cs2.{faceit_elo, skill_level}`, player nickname/ID, CS2 lifetime `Matches`, `Win Rate %`, `Average K/D Ratio`, `Average Headshots %`, `ADR` | **Yes (official Data API v4):** `Authorization: Bearer <server_key>` at `open.faceit.com/data/v4`. | Platform rate limits enforced (`429` on excess); authenticated server keys required. StackForge TTL `1800s`. | Free developer portal (`developers.faceit.com`) subject to TOS. | Server-side key only; never bundle key in frontend; obey FACEIT TOS. | **Yes** | **Yes (adapter ready; `NOT_CONFIGURED` keyless)** | **USE (Optional Key)** |
| **CSStats.gg**<br>https://csstats.gg/ | Match history tracker, rating progression, scoreboard/demo stats | Web UI shows ADR, HLTV rating, K/D, clutches, maps, banned-player history | **No documented open public REST API** confirmed. | Cloudflare-protected web pages. | Free web UI (subscription perks on site). | **Cloudflare-gated; scraping prohibited.** Use URL `/player/{steamid64}` extraction & outbound links only. | Link-out only | **URL ID extract + link only** | **MONITOR** (link-only) |
| **Scope.gg**<br>https://scope.gg/ | Match dashboard, AI coach, heatmaps, demo utility analysis | Web/app shows grenade lineups, misteps, clutches, rating | **No self-serve public developer API or docs.** | Consumer demo upload / desktop app model. | Freemium / paid consumer plans. | No automated third-party REST contract; do not scrape. | No (feature inspiration only) | **No** | **RESEARCH ONLY** |
| **CSMeta**<br>https://csmeta.gg/ | Web aggregator combining FACEIT, Leetify, Premier stats | Aggregated profile summaries on web frontend | **No public developer API or documentation found.** | N/A | Web tool | Do not scrape downstream aggregator; query authorized upstream providers directly. | No | **No** | **REJECT** |
| **CSST.at**<br>https://www.csst.at/ | Cross-platform CS2 stat lookup (Steam, FACEIT, Leetify, Scope.gg, CSTracker) | Cross-service profile & stat aggregation | **Private / invite-only API** (`Authorization: Bearer`), requires contacting maintainer (`@snek239`/Discord) — not open self-serve. | Custom per approved key | Small-project coordination / paid tiers via maintainer. | Upstream redistribution/chaining risks; StackForge already integrates Steam, Leetify & FACEIT directly. | Low (redundant) | **No** | **MONITOR / RESEARCH ONLY** |
| **HLTV**<br>https://www.hltv.org/ | Pro CS2 esports news, rankings, team/player match database | Pro tournament stats & HLTV 2.x/3.0 ratings | **No official public API.** | Heavily Cloudflare-protected against bots. | Closed website | Scraping violates anti-bot/TOS controls; StackForge focuses on private community players, not esports pros. | No | **No** | **REJECT** |
| **BO3.gg**<br>https://bo3.gg/ | Pro esports tournament live ticker & match analytics | Pro match analytics (commercial/syndicated feeds via 3rd-party marketplaces) | **No free self-serve public API portal** (unofficial wrappers / commercial APIs exist). | Commercial/partner gated | Paid/partner access | Community StackForge rosters have no pro HLTV/BO3 profiles. | No | **No** | **REJECT** |
| **Tracker Network**<br>https://tracker.gg/ | Multi-game stats frontend (`tracker.gg/cs2`) | Web Premier/competitive history UI | **CS:GO API officially deprecated; CS2 developer API access gated** (requires explicit production whitelisting/approval; no open self-serve CS2 key). | Strict key quotas when whitelisted | Approval gated | **Scraping explicitly prohibited by TOS.** | No (gated + Leetify already richer) | **No** | **REJECT** |

---

### B. Anti-Cheat, Account Reputation & Player Screening

| Source | Purpose & Signals | Public API & Auth | Rate Limits & Freshness | Access / Pricing | TOS & Attribution | Suitable? | Integrated? | Action |
|---|---|---|---|---|---|---|---|---|
| **CSWatch & Dev API**<br>https://cswatch.gg/<br>https://cswatch.gg/developers | Reputation score (`0-100`), `riskLevel`, `isCheater`, `convictionCount`, `aiSeverity`, `bans.{vac,gameBans,lastBanDays}`, `breakdown`, `factors`, `stored`, `storedAt`, `stale` | **Yes (documented public JSON API):** `GET /api/public/player/{steamId}` — **No key needed** on free tier; keyed tier on request. | Fair use: **<= 30 req/min/IP & <= 500 req/day/IP**. StackForge enforces 25/min cap & `3600s` TTL. Upstream flags `stale: true` if `storedAt > 24h`; `convictionCount` live; unindexed returns `stored: false` + queued nightly. | Free fair-use public tier; keyed API via direct request. | **Visible attribution link back to `cswatch.gg` required.** Must never be represented as Valve Trust Factor or official verdict. | **Yes** | **Yes (hardened with `stored`/`storedAt`/`stale`/`convictionCount`/`isCheater`)** | **USE** |
| **CStrike.gg Trust**<br>https://www.cstrike.gg/trust | Match analysis & fact-based standing checks (bans + explicit confirmed demo flags) | **No documented public REST API** confirmed. | Consumer site | Free / consumer account | Emphasizes hard-fact signals over unverified reports — useful design reference only. | Conceptual reference | **No** | **RESEARCH ONLY** |
| **Suspect.gg / CSRep.gg**<br>https://suspect.gg/ | Community trust 0–100 scale combining demos, history, community votes & AI behavioral flags | Associated `csrep.gg` exposes gated/authenticated reference docs rather than an unrestricted keyless API. | Account/tier gated | Requires account / partner review | Third-party AI trust/votes carry false-positive risks without raw sample transparency. | Limited (wait for verifiable public TOS/API) | **No** | **MONITOR** |
| **Mercurial.gg**<br>https://mercurial.gg/ | Demo-only behavioral/AI cheat anomaly scoring (40+ metrics) | **No open public API** (partner keys strictly case-by-case for own users only). | Closed / partner-only | Gated | **TOS explicitly prohibits scraping, automated access, and systematic external storage.** | **No** | **No** | **REJECT** |
| **CS.Ninja**<br>https://cs.ninja/ | Account trust & multi-source profile lookup (Steam, FACEIT, Leetify, CSStats) | **No documented public REST developer API.** | Consumer lookup | Free web UI | Treats private profiles/inventories as missing evidence rather than guilt — good UX validation. | UX reference | **No** | **RESEARCH ONLY** |

---

### C. Official & Developer Documentation Sources

| Source | Purpose & Available Signals | API / Auth | Terms, Limitations & Engineering Impact | Action |
|---|---|---|---|---|
| **Steam Web API (`ISteamUser`)**<br>https://partner.steamgames.com/doc/webapi/isteamuser | `ResolveVanityURL/v1`, `GetPlayerSummaries/v2` (persona, avatar, `communityvisibilitystate`), `GetPlayerBans/v1` (`VACBanned`, `NumberOfVACBans`, `NumberOfGameBans`, `DaysSinceLastBan`, `CommunityBanned`, `EconomyBan`) | Server-side `STEAM_API_KEY` required for `GetPlayerBans` & Web API summaries. Keyless `?xml=1` covers public persona/avatar/vanity fallback. | `NumberOfGameBans` includes non-CS2 titles & non-cheat Steam violations (botting/rank interference); **never treat generic game-ban count as CS2 cheat proof**, and never treat `0` bans as proof clean. Keep VAC/game/community/economy fields distinct. | **USE** (Already implemented; unlocks bans when key supplied) |
| **Steam Anti-Cheat Docs**<br>https://partner.steamgames.com/doc/features/anticheat | Official Steamworks anti-cheat & VAC integration overview | Developer reference doc (not a player query endpoint) | Confirms Valve exposes enforcement outcomes via `GetPlayerBans`, not internal Trust Factor or heuristic internals. | **USE (Governance Baseline)** |
| **CS2 Trusted Mode FAQ**<br>https://help.steampowered.com/en/faqs/view/09A0-4879-4353-EF95 | Explains DLL/code-injection blocking in CS2 Trusted Mode & Trust Factor impact of non-Trusted play | Informational support documentation | Reinforces StackForge's strict **read-only rule**: never inject into CS2, read game memory, or touch game files. | **USE (Safety Baseline)** |
| **FACEIT Developer Portal**<br>https://developers.faceit.com/ | Official App Studio for Data API v4 (`players`, `players/{id}/stats/cs2`, match history) | `Authorization: Bearer <server_api_key>`; client keys support domain restrictions, server keys strictly backend-only. | Keep credentials server-side in `secrets_service.py` (Windows DPAPI) or `backend/.env`; never ship keys in Vite bundle. | **USE (Optional Server Key)** |
| **Leetify Public CS API Docs**<br>https://api-public-docs.cs-prod.leetify.com/ | Official schema for `/v3/profile`, `/v3/profile/matches`, `/v2/matches/{gameId}`, `/api-key/validate` | Optional `_leetify_key` or `Authorization: Bearer` header (`leetify.com/app/developer`). Works keyless with stricter rate limiting. | Verify units carefully (`ranks.leetify` % pts vs match decimal; match `reaction_time` seconds vs `stats.reaction_time_ms`; absent `kast`). | **USE (Implemented)** |

---

## 3. Demo Parsing & Analysis Comparison (Awpy vs demoparser2 vs demo-anticheat)

| Dimension | `pnxenopoulos/awpy` | `LaihoE/demoparser` (`demoparser2`) | `TimAnthonyAlexander/demo-anticheat` |
|---|---|---|---|
| **URL** | https://awpy.readthedocs.io/en/latest/ | https://github.com/LaihoE/demoparser | https://github.com/TimAnthonyAlexander/demo-anticheat |
| **Runtime & Language** | Rust (`pbdems2`) + PyO3 Python outputting **Polars** DataFrames / Parquet | Rust core with native Python (`pip install demoparser2`), JS/TS & WASM bindings | Standalone **Go** CLI / analyzer |
| **License** | MIT | MIT | Open-source GitHub repo (verify commit `LICENSE` before any code reuse) |
| **Windows Compatibility** | Precompiled wheels for Windows (`Python 3.11–3.15`); no local Rust compiler needed | Precompiled Python wheels (`pip install demoparser2`); works natively on Windows | Requires Go toolchain / Windows cross-compiled binary |
| **CS2 `.dem` (`PBDEMS2`) Support** | **Full CS2 `.dem` support** | **Full CS2 `.dem` support** | **CS2 `.dem` support** |
| **Metrics / Output** | High-level **round reconstruction, kills, damages, smokes/flashes, visibility, KAST, ADR, trades, clutches** | Raw database-style tick/property queries (`X,Y,Z`, viewangles, weapon events) — custom code required for KAST/trades | Post-match heuristic/anomaly cheat detection signals |
| **Processing Time** | Fast (~1–4s per 60–150 MB 5v5 `.dem` via Rust core + Polars) | Ultra-fast raw sweeps (~328–740+ MB/s NVMe depending on CPU/disk) | Post-match single-demo sweep |
| **Maintainability in StackForge** | **Highest** — matches Python 3.13 + FastAPI backend directly with structured analytics helpers | Good — requires writing & maintaining custom KAST/trade/clutch round-state logic | Lower (separate Go runtime/IPC; heuristic anti-cheat output is non-authoritative) |
| **Decision** | **RECOMMENDED PARSER (`P3` Async Worker)** | Alternative fallback only if raw tick extraction is needed | **RESEARCH ONLY** (heuristic reference; never auto-convicts players) |

---

## 4. Trust & Cheating Evidence Governance Rules

StackForge enforces five strictly separated `TrustSignal.category` tracks in [models.py](file:///d:/CS2_StackForge/backend/app/models.py) and [trust_service.py](file:///d:/CS2_StackForge/backend/app/services/trust_service.py):

1. **`OFFICIAL_ENFORCEMENT`** — Valve/Steam (`GetPlayerBans`: VAC, generic Game Bans, Community Ban, Economy/Trade Ban) or official FACEIT bans. **VAC/game bans are never conflated with trade/community bans, and generic Steam `NumberOfGameBans` never auto-proves CS2 cheating.**
2. **`THIRD_PARTY_REPUTATION`** — CSWatch (`reputationScore`, `riskLevel`, `isCheater`, `convictionCount`, `storedAt`, `stale`). Requires explicit `cswatch.gg` attribution link; explicitly labeled *"NOT an official Valve verdict."* Unknown (`stored=false`) or `stale=true` records remain `UNKNOWN`/`STALE`, **never** converted into clean `OK` badges.
3. **`COMMUNITY_REPORT`** — Moderator/host observations logged inside the private community (`PENDING_REVIEW`).
4. **`DEMO_BEHAVIOURAL_SIGNAL`** — Future offline `.dem` behavioral indicators (must attach sample size, parser version, confidence, and limitations; never auto-labels/punishes any member).
5. **`HUMAN_REVIEWED_EVIDENCE`** (and legacy `HUMAN_REVIEW` alias preserved for watchlist audit compatibility) — Explicit host/moderator disposition (`REVIEWED`, `DISMISSED`) with appeal/note support.

**Invariants:**
- High `ADR`, `HS%`, `aim_rating`, low `reaction_time_ms`, or high `ELO` are **skill metrics, never cheating evidence**.
- Suspicious stats or demo signals **never** alter matchmaking ratings or auto-ban any community member.
- Missing, private, or stale data remains explicitly flagged as `UNKNOWN` / `PRIVATE` / `STALE` / `NOT_CONFIGURED`.

---

## 5. Recommended Implementation Sequence (Modular Monolith)

1. **Completed (`97e2fff` + CSWatch patch):** Standardized providers, canonical 24-metric registry, Windows DPAPI credential vault (`Ops & Keys`), active 24h/login/startup scheduler, `positioning_rating` + `traded_deaths_pct` matchmaking & display, post-match results + separate community standings, and CSWatch `stored`/`storedAt`/`stale`/`convictionCount`/`isCheater` preservation.
2. **Next (`Keyed Activation` — zero code rewrite needed):** Supply optional `STEAM_API_KEY` / `FACEIT_API_KEY` / `LEETIFY_API_KEY` in `Ops & Keys` when ready to unlock `GetPlayerBans`, direct FACEIT v4 lifetime stats, and higher Leetify quota.
3. **Future (`P3` Async Demo Pipeline):** Implement [DEMO_PIPELINE.md](file:///d:/CS2_StackForge/docs/DEMO_PIPELINE.md) using **`Awpy`** inside a single-process `ProcessPoolExecutor(max_workers=1)` worker to extract exact `KAST` and private-lobby combat metrics (`provider="community_demo"`), only when custom demo uploads are actively used.
