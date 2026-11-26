# StackForge External Integrations & Ecosystem Compliance

This document is the single source of truth for external CS2 data providers, official documentation verification, rate limits, Terms of Service compliance, demo-parser candidates, and rejected/unsupported sources.

---

## 1. Read-Only Anti-Cheat & Legal Compliance Model

StackForge strictly enforces read-only HTTP access and offline user-supplied files:
- **Never** injects into CS2, reads/writes process memory, touches game binaries/VPKs, simulates input, or automates Valve matchmaking queues.
- **Never** bypasses Cloudflare/anti-bot challenges or scrapes websites whose Terms of Service prohibit scraping or automated storage.
- **Never** converts third-party reputation scores or statistical anomalies into Valve Trust Factor claims or cheating verdicts.

---

## 2. Active & Adapter-Ready Integrations Matrix

| Provider / Source | Auth / Key | Official Docs / URL | Implementation Status | Cache TTL / Rate Controls | Primary Caveats & Compliance |
|---|---|---|---|---|---|
| **Steam Community XML (`?xml=1`)** | None (Keyless) | https://steamcommunity.com/ | **Implemented & Active** (`providers/steam.py`) | `900s` TTL + single-flight | Public profile fields only (`steamID64`, persona, avatar, visibility). Fails gracefully to cached identity on outage. |
| **Steam Web API (`ISteamUser`)** | `STEAM_API_KEY` (server-side) | https://partner.steamgames.com/doc/webapi/ISteamUser | **Implemented** (`NOT_CONFIGURED` until key set) | `900s` TTL | Unlocks official `GetPlayerBans/v1`, `GetPlayerSummaries/v2`, `ResolveVanityURL/v1`. Game-ban counts include non-CS2/non-cheat enforcement. |
| **Leetify Public CS API v3** | Optional `LEETIFY_API_KEY` | https://api-public-docs.cs-prod.leetify.com/ | **Implemented & Active** (`providers/external.py`) | `1800s` TTL; max 3 retries (`Retry-After <= 5s`) | Keyless mode hits stricter HTTP `429 RATE_LIMITED`; private profiles return explicit `PRIVATE`; `kast` absent on public v3 (`None`). |
| **FACEIT Data API v4** | `FACEIT_API_KEY` (server Bearer) | https://docs.faceit.com/docs/data-api/ | **Implemented** (`NOT_CONFIGURED` until key set) | `1800s` TTL | Lifetime CS2 stats & ELO/level when keyed (handles `400/401/403/404/429`). Without key, Steam-linked FACEIT `elo`/`level` still reads from Leetify when exposed. |
| **CSWatch Public JSON API** | None on free tier (keyed tier via support) | https://cswatch.gg/developers<br>https://cswatch.gg/terms | **Implemented Keyless — `CLARIFICATION_REQUIRED`** (`providers/cswatch.py`) | **25 req/min local cap** (`<= 30/min`, `<= 500/day` fair use); `3600s` TTL | `/developers` allows JSON API + embeds with link attribution; `/terms` §4 restricts non-personal redistribution. See Section 4. |
| **Google Sheets CSV / `.csv` / `.xlsx`** | Public share link or local file upload | https://docs.google.com/spreadsheets/ | **Implemented & Active** (`import_service.py`) | Manual Preview / Commit / Sync Now | Extracts canonical URLs/IDs cleanly; ignores manual ratings in balancing. |
| **CSStats.gg** | N/A (No open REST API) | https://csstats.gg/ | **URL Parse & Link-Out Only** (`steam_parser.py`) | No HTTP requests made | Cloudflare-gated; extracts `SteamID64` from `/player/{steamid64}` URLs only; never scraped. |

---

## 3. Official API Verification Details (Checked 2026-11-26)

### Steam `ISteamUser/GetPlayerBans/v1/` & Anti-Cheat Policy
- Official Steamworks documentation confirms `GetPlayerBans/v1` returns per-account fields: `CommunityBanned` (`bool`), `VACBanned` (`bool`), `NumberOfVACBans` (`uint32`), `DaysSinceLastBan` (`int`), `NumberOfGameBans` (`uint32` — Overwatch/developer/publisher game bans), and `EconomyBan` (`string`, e.g., `"none"`, `"probation"`, `"banned"`).
- **Governance impact:** StackForge keeps VAC, generic game ban, community ban, and economy/trade ban fields distinct inside `OFFICIAL_ENFORCEMENT` and forbids labeling a generic `NumberOfGameBans` count as CS2 cheating without game/context proof. Valve exposes enforcement outcomes via `GetPlayerBans` — not Trust Factor internals.

### FACEIT Data API v4
- Official docs (`docs.faceit.com`, `developers.faceit.com`) confirm `Authorization: Bearer <api_key>` authentication, strict distinction between server-side API keys (never embedded in client JS) and client-side keys, player/stats/ban/history endpoints (`/data/v4/players`, `/players/{id}/stats/{game_id}`, `/players/{id}/bans`, `/players/{id}/history`), and HTTP status handling (`400`, `401`, `403`, `404`, `429`).
- StackForge's `FaceitProvider` keeps `FACEIT_API_KEY` strictly on the FastAPI server (`secrets_service.py` / `backend/.env`) and preserves `NOT_CONFIGURED` cleanly when unset.

### Leetify Public CS API v3
- Official schema covers `GET /v3/profile?steam64_id={id}`, `GET /v3/profile/matches?steam64_id={id}`, `GET /v2/matches/{gameId}`, and `GET /api-key/validate`.
- Keyless access works with dynamic HTTP `429` limits; optional `LEETIFY_API_KEY` (`_leetify_key` / Bearer) raises quota limits. Metric unit normalization converts match `reaction_time` seconds to milliseconds (`reaction_time_ms`), validates bounds, and treats absent `kast` as `None` (`Unavailable`).

---

## 4. CSWatch Investigation: `/developers` vs `/terms` Discrepancy

> **Current Permission Status:** **`CLARIFICATION_REQUIRED`**  
> **Operator Details (from live `cswatch.gg/terms`):** *CSWatch*, Dutch KvK `82826757`, Pisuissestraat 12, 3034 WK Rotterdam, Netherlands · Legal/API Contact: `support@cswatch.gg`

### Verified Live Findings (Retrieved 2026-11-26)
1. **`https://cswatch.gg/developers` (`HTTP 200`):**
   - Explicitly publishes free unauthenticated `GET https://cswatch.gg/api/public/player/{steamId}`, HTML embed `<iframe>`, and `GET /api/public/leaderboard?limit=50`.
   - States fair use: **up to 30 player requests per minute and 500 per day per IP**.
   - States attribution & commercial note: *"Please attribute with a visible link to cswatch.gg so users can dig deeper into the evidence. Commercial use is fine. Need more than 500 players a day, or live data? Email support@cswatch.gg about a keyed API."*
   - Explicitly documents freshness semantics: `storedAt` indicates when Steam data was fetched; `stale: true` means Steam fetch is >24 hours old (so VAC/Game bans may be newer), **while `"Convictions are always current."`** When `stored: false`, `riskLevel` is `"unknown"` and the player is queued for nightly refresh.
2. **`https://cswatch.gg/terms` (`HTTP 200`, Last updated `28 October 2026`):**
   - Section 4 (**Acceptable use**) states: *"You agree not to: **Scrape, mirror, or redistribute data beyond your personal lookup use.** ... Attempt to bypass rate limits, credit requirements, or the anti-abuse system."*
   - Section 2 confirms CSWatch aggregates public Steam, FACEIT, and Leetify data plus community reports, is not affiliated with Valve/FACEIT/Leetify, does not issue bans, and does not claim a low reputation score proves cheating.

### Discrepancy & StackForge Mitigation
- **Why clarification is required:** `/developers` explicitly invites third-party apps/sites (including commercial apps) to embed/consume `/api/public/player/{steamId}` with attribution, whereas general website `/terms` §4 restricts redistributing data *"beyond your personal lookup use"* — creating legal ambiguity for a hosted/multi-user community dashboard that caches/displays CSWatch responses for other community members.
- **How StackForge enforces safety right now:**
  1. Keeps `permission_status = "CLARIFICATION_REQUIRED"` in documentation and CSWatch provider metadata (`providers/cswatch.py`).
  2. Enforces a conservative **25 requests/minute** client sliding cap (safely under 30/min) plus a `3600s` snapshot TTL.
  3. Preserves field-level freshness separately (`steam_data_freshness: STALE|CURRENT|UNKNOWN` vs `convictions_freshness: CURRENT` when indexed) and keeps `UNKNOWN` / `STALE` / `FLAGGED` / `OK` distinct so stale Steam cache never masquerades as a fresh clean verdict.
  4. Stores and surfaces the direct `cswatch.gg/player/{steamId}` attribution link and *"NOT an official Valve verdict"* disclaimer on every signal.

### Draft Clarification Email to `support@cswatch.gg` (Not Sent)

> **To:** `support@cswatch.gg`  
> **Subject:** Clarification on `/api/public/player/{steamId}` vs Terms §4 for Private CS2 Community Organizer (StackForge)  
>
> Hello CSWatch team,  
>  
> We are building **StackForge**, a small non-public Counter-Strike 2 private 5v5 match organizer for a local friend/community stack (`D:\CS2_StackForge`). We would like to clarify the relationship between your developer documentation (`https://cswatch.gg/developers`) and your general Terms of Service §4 (`https://cswatch.gg/terms`, updated 28 October 2026) before relying on CSWatch outside private personal testing:  
>  
> 1. Under `/developers`, `GET /api/public/player/{steamId}` is offered for third-party integrations (with visible attribution links back to `cswatch.gg` and commercial use noted as permitted up to 30 req/min and 500 req/day per IP), whereas Terms §4 prohibits redistributing data *"beyond your personal lookup use."* Does `/developers` supersede §4 when calling the documented JSON endpoint cleanly under fair-use limits and displaying attributed CSWatch status/links inside a private community lobby view?  
> 2. Does StackForge's server-side response snapshot caching (TTL 60 minutes, storing observation history alongside `storedAt`, `stale`, and `cswatchProfileUrl`) align with your acceptable caching/retention expectations?  
> 3. If this use requires a keyed API agreement or tighter TTL/display rules, what tier or terms apply?  
>  
> For clarity, StackForge never scrapes web pages, enforces a 25 req/min local cap, links directly to `https://cswatch.gg/player/{steamId}`, preserves `stale`/`unknown` semantics, and explicitly disclaims that CSWatch signals are third-party reputation indicators rather than official Valve enforcement verdicts.  
>  
> Thank you for your time and guidance.  

---

## 5. Candidate CS2 Demo Parsers (Deferred `P3` Research)

Verified directly against official documentation before any implementation decision:

| Parser | License | Python / OS Support | Strengths & Fit for StackForge | Decision |
|---|---|---|---|---|
| **[Awpy](https://awpy.readthedocs.io/en/latest/)** (`pnxenopoulos/awpy`) | **MIT** | Python `>= 3.11` (`3.11–3.15`); precompiled Windows wheels (no Rust toolchain needed); Polars `2.x` + `pbdems2` | Built-in CS2 `.dem` (`PBDEMS2`) round reconstruction plus `awpy.stats.adr`, `kast`, and `calculate_trades(demo, trade_length_in_seconds=5.0)`. Cleanest match for Python 3.13 + FastAPI async worker. | **Preferred P3 Parser Candidate** |
| **[demoparser2](https://github.com/LaihoE/demoparser)** (`LaihoE/demoparser`) | **MIT** | Rust core with Python (`>= 3.8`, `pip install demoparser2`), JS (`@laihoe/demoparser2`), and WASM | High-throughput query-based CS2 `.dem` tick/property/event extraction when custom low-level analytics are required. | **Alternative Candidate** |

---

## 6. External Ecosystem — Evaluated Sources

| Source | Category | API / Terms Finding | Decision | Rationale |
|---|---|---|---|---|
| **Valve / Steam (`ISteamUser`)** | Official Identity & Bans | Public `?xml=1` + keyed `ISteamUser` Web API | **Implemented** | Canonical `SteamID64`, alias history, official `GetPlayerBans` enforcement tracks. |
| **Leetify Public CS API v3** | CS2 Stats & Match History | Official `/v3/profile*` API (key optional) | **Implemented** | Core source for aim, utility, positioning, preaim, reaction time, openings, trades, form. |
| **FACEIT Data API v4** | Competitive Ladder & Lifetime Stats | Official Bearer API at `open.faceit.com/data/v4` | **Implemented (Keyed)** | Authoritative FACEIT ELO/level & CS2 lifetime combat stats once key is added. |
| **CSWatch Public API** | Third-Party Reputation | Public JSON API (`<=30/min`, `<=500/day`); ToS §4 ambiguity | **Implemented (`CLARIFICATION_REQUIRED`)** | Attributed non-verdict signal only; 25/min cap; preserves `stale` Steam vs current convictions. |
| **CSStats.gg** | Match History Website | Cloudflare-gated; no open public API | **Link-Out & ID Parse Only** | Respect Cloudflare/TOS; extract `SteamID64` from `/player/{id}` and link out cleanly. |
| **Tracker Network (`tracker.gg`)** | Multi-Game Stats | Legacy CS:GO API deprecated; CS2 API approval-gated; scraping prohibited | **Unsupported / Rejected** | Cannot scrape; Leetify + FACEIT already supply richer CS2 metrics cleanly. |
| **HLTV / BO3.gg** | Pro Esports Databases | Closed/Cloudflare-gated or commercial pro feeds | **Rejected** | Private community players are not esports pros; scraping prohibited. |
| **CSMeta.gg / Mercurial.gg** | Aggregators / Demo AI | No open self-serve API; Mercurial TOS prohibits scraping/storage | **Rejected** | TOS incompatibility and downstream aggregation redundancy. |
| **Scope.gg / CSST.at** | Coaching / Private Aggregator | Scope consumer-only; CSST.at invite-only Bearer API | **Research Only** | Feature/UX reference without adding upstream chaining risk. |
| **CS2SUS / Cheatscanner / CStrike.gg Trust / Suspect.gg / CS2Track / VACWatch / CS.Ninja** | Trust & Demo Screening References | Closed/reference sites or non-public APIs (`CS2SUS` confirms anomaly != cheat) | **Research Only** | Useful for non-accusatory evidence UX and review workflows; never scrape. |
| **`akiver/cs-demo-manager` / `CSManager` / `demo-anticheat`** | Open-Source CS2 Projects | MIT Electron+Go (`cs-demo-manager`), MIT Next/Supabase (`CSManager`), Go CLI (`demo-anticheat`) | **Research Only** | Inspiration for KAST formulas, yearly community standings, and `.dem` heuristic limits. |
| **CS2 Local Game State Integration (`cs2-tracker`)** | Local Client Telemetry | Opt-in local localhost HTTP events during live client play | **Future Optional Companion** | Only observes the local opted-in player's active match; cannot backfill a 10-player stack. |

---

## 7. New Integration Acceptance Checklist

Before enabling any new provider or parser in runtime:
1. Read current official docs, auth rules, commercial/redistribution Terms, and rate limits.
2. Confirm attribution requirements, missing/private behavior, and non-accusatory wording.
3. Implement behind a bounded adapter in `backend/app/providers/` with `ProviderSnapshot` status normalization.
4. Add unit/mock contract tests in `backend/tests/` before UI exposure.
