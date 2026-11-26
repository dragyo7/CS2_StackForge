# StackForge External Integrations, Credentials & Compliance

This document is the source of truth for external CS2 data providers, official documentation checks, credential configuration, CSWatch Terms/API compliance status, candidate demo parsers, and evaluated external ecosystem sources.

---

## 1. Read-Only Anti-Cheat & Legal Compliance Policy

- **Read-only access only:** Never inject into CS2, read/write game memory, modify game binaries/VPKs, simulate input, or automate Valve queues.
- **No prohibited scraping:** Never bypass Cloudflare or anti-bot checks, and never automate extraction from sites whose Terms prohibit scraping or external storage.
- **Non-verdict policy:** External scores and reputation labels are supplementary signals only — never Valve Trust Factor and never proof of cheating.

---

## 2. Active & Adapter-Ready Integrations

| Provider / Source | Auth & Key Storage | Official Docs / URL | Implementation Status | Cache TTL / Rate Controls | Primary Caveats & Compliance |
|---|---|---|---|---|---|
| **Steam Community XML (`?xml=1`)** | Keyless | https://steamcommunity.com/ | **Implemented & Active** (`providers/steam.py`) | `900s` TTL + single-flight | Public `steamID64`, persona, avatar, visibility only; retains last cached identity on outage. |
| **Steam Web API (`ISteamUser`)** | `STEAM_API_KEY` (server-side) | https://partner.steamgames.com/doc/webapi/ISteamUser | **Implemented** (`NOT_CONFIGURED` until key supplied) | `900s` TTL | Unlocks `GetPlayerBans/v1`, `GetPlayerSummaries/v2`, `ResolveVanityURL/v1`. Game-ban counts include non-CS2/non-cheat cases. |
| **Leetify Public CS API v3** | Optional `LEETIFY_API_KEY` | https://api-public-docs.cs-prod.leetify.com/ | **Implemented & Active** (`providers/external.py`) | `1800s` TTL; max 3 retries (`Retry-After <= 5s`) | Keyless incurs stricter HTTP `429 RATE_LIMITED`; private profiles return `PRIVATE`; `kast` absent on public v3 (`None`). |
| **FACEIT Data API v4** | `FACEIT_API_KEY` (server Bearer) | https://docs.faceit.com/docs/data-api/ | **Implemented** (`NOT_CONFIGURED` until key supplied) | `1800s` TTL | Server key unlocks ELO/level & CS2 lifetime stats (handles `400/401/403/404/429`). Without key, Steam-linked ELO/level may still ingest from Leetify. |
| **CSWatch Public JSON API** | Free tier public (keyed tier via support) | https://cswatch.gg/developers<br>https://cswatch.gg/terms | **Implemented Keyless — `CLARIFICATION_REQUIRED`** (`providers/cswatch.py`) | **25 req/min local cap** (`<=30/min`, `<=500/day`); `3600s` TTL | `/developers` vs `/terms` §4 discrepancy; **do not claim API Terms compliance** or expand storage/redistribution. See Section 5. |
| **Google Sheets CSV / `.csv` / `.xlsx`** | Public share link or upload | https://docs.google.com/spreadsheets/ | **Implemented & Active** (`import_service.py`) | Manual Preview / Commit / Sync Now | Extracts canonical URLs/IDs cleanly; legacy manual ratings excluded from balancing. |
| **CSStats.gg** | N/A | https://csstats.gg/ | **URL Parse & Link-Out Only** (`steam_parser.py`) | No HTTP requests made | Cloudflare-gated; extracts `SteamID64` from `/player/{steamid64}` URLs only; never scraped. |

---

## 3. Optional Credential Acquisition & Keyless Mode

StackForge runs keyless out of the box (Steam `?xml=1`, Leetify Public v3, CSWatch Public API under local caps, Google Sheets CSV, local match outcomes). Optional server-side credentials may be added via `Ops & Keys` (`PUT /api/settings/credentials/{provider}`, encrypted via Windows DPAPI) or `backend/.env`:
- **`STEAM_API_KEY`:** `https://steamcommunity.com/dev/apikey` (unlocks official `GetPlayerBans` and keyed Steam summaries).
- **`FACEIT_API_KEY`:** `https://developers.faceit.com/` (server-side API key; never ship to frontend assets).
- **`LEETIFY_API_KEY`:** `https://leetify.com/app/developer` (optional higher-quota developer key).

---

## 4. Official API Verification Notes (Checked 2026-11-26)

- **Steam `ISteamUser/GetPlayerBans/v1/`:** Official docs confirm `CommunityBanned` (`bool`), `VACBanned` (`bool`), `NumberOfVACBans` (`uint32`), `DaysSinceLastBan` (`int`), `NumberOfGameBans` (`uint32`), and `EconomyBan` (`string`). Valve exposes enforcement outcomes here rather than internal Trust Factor; StackForge keeps VAC, generic game, community, and economy bans separate.
- **FACEIT Data API v4:** Official docs confirm `Authorization: Bearer <api_key>`, strict server-side vs client-side key separation, `/data/v4/players`, `/players/{id}/stats/{game_id}`, `/players/{id}/bans`, `/players/{id}/history`, and `400/401/403/404/429` handling.
- **Leetify Public CS API v3:** Official endpoints (`/v3/profile`, `/v3/profile/matches`, `/v2/matches/{gameId}`, `/api-key/validate`); converts match `reaction_time` seconds to `reaction_time_ms` and treats absent `kast` as `None`.

---

## 5. CSWatch API & Terms Investigation (`CLARIFICATION_REQUIRED`)

> **Permission Status:** **`CLARIFICATION_REQUIRED`** (until explicit written confirmation from `support@cswatch.gg`)  
> **Operator (from live `cswatch.gg/terms`):** *CSWatch*, Dutch KvK `82826757`, Pisuissestraat 12, 3034 WK Rotterdam, Netherlands · `support@cswatch.gg`

### Live Findings (Checked 2026-11-26)
1. **`https://cswatch.gg/developers` (`HTTP 200`):** Publishes unauthenticated `GET https://cswatch.gg/api/public/player/{steamId}`, HTML embed `<iframe>`, and `GET /api/public/leaderboard?limit=50`; states fair use up to **30 player requests/min and 500/day/IP**, requires a **visible attribution link to `cswatch.gg`**, notes commercial use is permitted, and explicitly defines freshness: `storedAt` records the last Steam fetch, `stale: true` means Steam data is `>24h` old (so bans may be newer), **while `"Convictions are always current."`** Unindexed accounts return `stored: false`, `riskLevel: "unknown"`.
2. **`https://cswatch.gg/terms` (`HTTP 200`, Last updated `28 October 2026`):** Section 4 (*Acceptable use*) states: *"You agree not to: **Scrape, mirror, or redistribute data beyond your personal lookup use.** ... Attempt to bypass rate limits, credit requirements, or the anti-abuse system."* Section 2 confirms CSWatch is unaffiliated with Valve/FACEIT/Leetify, does not issue bans, and does not claim low scores prove cheating.

### Governance Boundaries (Mandatory Until Resolved)
- **Do not claim full API Terms compliance** while `/developers` (third-party embeds/API, commercial permitted) conflicts with general `/terms` §4 (*"beyond your personal lookup use"*).
- **Do not silently expand historical storage or redistribution** of CSWatch data across broader public/multi-tenant feeds without written CSWatch confirmation or a keyed agreement.
- **Preserve separate Steam vs conviction freshness:** [cswatch.py](file:///d:/CS2_StackForge/backend/app/providers/cswatch.py) enforces a 25 req/min sliding cap (`3600s` TTL), preserves `UNKNOWN` / `STALE` / `FLAGGED` / `OK`, surfaces direct `cswatch.gg/player/{id}` attribution + non-verdict disclaimers, and stores separate `"steam_data_freshness"` (`STALE`/`CURRENT`/`UNKNOWN`) vs `"convictions_freshness"` (`CURRENT`/`UNKNOWN`), `"convictions_current"`, and `"permission_status": "CLARIFICATION_REQUIRED"`.

### Draft Clarification Email to `support@cswatch.gg` (Not Sent)

> **To:** `support@cswatch.gg`  
> **Subject:** Clarification on `/api/public/player/{steamId}` vs Terms §4 for Private CS2 Match Organizer (StackForge)  
>  
> Hello CSWatch team,  
>  
> We are building **StackForge**, a private Counter-Strike 2 5v5 match organizer for a small local friend/community stack. Before relying on CSWatch beyond local personal testing, could you please clarify the interaction between `https://cswatch.gg/developers` and Terms of Service §4 (`https://cswatch.gg/terms`, updated 28 October 2026)?  
>  
> 1. Under `/developers`, `GET /api/public/player/{steamId}` is documented for external integrations (with visible attribution links back to `cswatch.gg`, fair-use caps of 30 req/min and 500/day/IP, and commercial use permitted), whereas Terms §4 restricts redistributing data *"beyond your personal lookup use."* Does `/developers` authorize displaying attributed JSON responses and `cswatchProfileUrl` links inside a private community lobby view?  
> 2. What server-side caching TTL and observation-history rules apply to local response snapshots alongside `storedAt`, `stale`, and `cswatchProfileUrl`?  
> 3. If a keyed API agreement or tighter display/retention terms are required for multi-user community use, please let us know what terms apply.  
>  
> StackForge never scrapes web pages, enforces a 25 req/min local cap, includes direct attribution links to `cswatch.gg/player/{steamId}`, preserves `stale`/`unknown` semantics, and explicitly disclaims that CSWatch signals are third-party reputation indicators rather than official Valve enforcement verdicts.  
>  
> Thank you for your guidance.

---

## 6. Candidate CS2 Demo Parsers (Deferred `P3` Research)

| Parser | License | Python / OS Verification | Decision |
|---|---|---|---|
| **[Awpy](https://awpy.readthedocs.io/en/latest/)** (`pnxenopoulos/awpy`) | **MIT** | Python `>= 3.11` (`3.11–3.15`); precompiled Windows wheels; Polars `2.x` + `pbdems2`; built-in `adr`/`kast`/`calculate_trades`. Fits `Python 3.12.10` baseline & `3.13.5` `.venv`. | **Preferred `P3` Candidate** |
| **[demoparser2](https://github.com/LaihoE/demoparser)** (`LaihoE/demoparser`) | **MIT** | Rust core with Python (`>= 3.8`), JS (`@laihoe/demoparser2`), and WASM query bindings for raw tick/event extraction. | **Alternative Candidate** |

---

## 7. External Ecosystem — Evaluated Sources

| Source | Category | Terms / API Finding | Decision | Rationale |
|---|---|---|---|---|
| **Valve / Steam / Leetify / FACEIT v4 / Google Sheets** | Core Stats & Identity | Official public/keyed APIs or public CSV export | **Implemented** | Covers SteamID64, bans (keyed), CS2 stats, ELO, and spreadsheet sync. |
| **CSWatch** | Third-Party Reputation | Public JSON API; `/terms` §4 conflict | **Implemented (`CLARIFICATION_REQUIRED`)** | Attributed non-verdict signal only; 25/min cap; no redistribution expansion. |
| **CSStats.gg** | Match Tracker Site | Cloudflare-gated; no open public REST API | **Link-Out & URL ID Parse Only** | Respect Cloudflare/TOS; extract `SteamID64` and link out cleanly. |
| **Tracker Network (`tracker.gg`)** | Multi-Game Tracker | CS:GO API deprecated; CS2 gated; scraping prohibited | **Unsupported / Rejected** | No public self-serve CS2 API; Leetify + FACEIT already cover metrics cleanly. |
| **HLTV / BO3.gg / CSMeta / Mercurial.gg** | Pro Feeds / Closed AI / Aggregators | Closed/Cloudflare-gated or TOS bans scraping/storage | **Rejected** | Non-pro audience + TOS incompatibility + no public API contract. |
| **Scope.gg / CSST.at / CStrike.gg / Suspect.gg / CS2Track / VACWatch / CS.Ninja** | Consumer / Private / Reference Tools | Closed or invite-only (`CSST.at`); UX/methodology inspiration only | **Research Only** | Useful reference patterns without scraping or API chaining risks. |
| **`cs-demo-manager` / `CSManager` / `demo-anticheat` / Valve GSI (`cs2-tracker`)** | Open-Source Projects & Local Telemetry | MIT desktop/web repos (`demo-manager`, `CSManager`), Go CLI, opt-in local GSI | **Research Only / Future Optional** | Reference KAST/standings UX; GSI only captures local client play. |

### Integration Acceptance Checklist
Before enabling any new source: confirm current docs, terms/redistribution permission, rate limits, attribution requirements, missing-data semantics, fail-safe adapter implementation, and mock/contract tests.
