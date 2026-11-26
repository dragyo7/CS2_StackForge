# StackForge Architecture, Metrics, Matchmaking & Trust Model

> **Status:** Active Modular Monolith (`React 18 + TypeScript + Vite` + `FastAPI + SQLAlchemy + SQLite`)  
> **Ports (Local V2):** Backend `127.0.0.1:8001` · Frontend `127.0.0.1:5174`

---

## 1. System Architecture & Verified Codebase Layout

StackForge runs as a single modular monolith backed by SQLite (`backend/stackforge.db`), avoiding unnecessary microservices, Redis, Kafka, or Kubernetes overhead while keeping clear module boundaries:

```text
┌─────────────────────────────┐         Vite /api proxy         ┌─────────────────────────────────────┐
│ React 18 + TS + Vite (5174) │ ──────────────────────────────▶ │ FastAPI App (8001)                  │
│  - MatchRoomView            │                                 │  - Routes: platform, players, rooms │
│  - PlayerRegistry / Stats   │ ◀────────────────────────────── │  - Services: identity, import,      │
│  - PlayerCards / Standings  │          JSON REST API          │    refresh_coordinator, trust, ops  │
│  - TrustWatch / Ops & Keys  │                                 │  - Optimizer: normalizer, engine    │
└─────────────────────────────┘                                 └──────────┬──────────────┬───────────┘
                                                                           │              │
                                                      SQLAlchemy ORM       │              │ Server-side HTTPX
                                                      + run_migrations()   ▼              ▼
                                                                ┌──────────────┐   ┌──────────────────┐
                                                                │ SQLite DB    │   │ Read-Only Feeds  │
                                                                │ stackforge.db│   │ Steam / Leetify  │
                                                                │ + DPAPI file │   │ FACEIT / CSWatch │
                                                                └──────────────┘   │ Google Sheets    │
                                                                                   └──────────────────┘
```

- **Backend core:** `backend/app/{main,config,database,migrations,models,schemas}.py`
- **Backend routes:** `backend/app/routes/{platform,players,rooms}.py`
- **Backend services:** `auth_service.py`, `humour_engine.py`, `identity_resolver.py`, `import_service.py`, `match_result_service.py`, `metric_registry.py`, `ops_service.py`, `player_service.py`, `refresh_coordinator.py`, `room_service.py`, `scheduler.py`, `secrets_service.py`, `steam_parser.py`, `trust_service.py`
- **Backend providers & optimizer:** `backend/app/providers/{base,steam,external,cswatch}.py`; `backend/app/optimizer/{normalizer,engine}.py`
- **Frontend (`frontend/src/`):** `App.tsx`, `api.ts`, `types.ts`, `styles.css`, and views (`DashboardView`, `LandingAuthView`, `MatchRoomView`, `OpsAndSettingsView`, `PlayerAvatar`, `PlayerCardsView`, `PlayerCardTile`, `PlayerRegistryView`, `PlayerStatsView`, `SharedLineupView`, `TrustWatchView`, `CommunityImportPanel`)

---

## 2. Data Model & Provenance (`SQLite + SQLAlchemy`)

- **`players` & `player_aliases`:** Canonical global identity keyed by string `steam_id64` (`vanity_name`, `steam_persona_name`, `avatar_url`, `identity_status`, `profile_visibility`, refresh timestamps). Nickname changes append to `player_aliases` with consecutive duplicate suppression so old names remain searchable without creating duplicate players.
- **`player_external_identities`:** Cross-provider mappings (`steam`, `csstats`, `leetify`, `faceit`, `cswatch`) tracking `VERIFIED` | `CANDIDATE` | `UNRESOLVED` confidence.
- **`communities` & `community_players`:** Community-scoped membership (`display_name`, roles, ratings snapshot fields, `is_archived`, card/visibility settings). Legacy `manual_rating` stays in SQLite solely for backwards schema compatibility and is forced to `None` in matchmaking (`norm_v2`).
- **`player_stat_snapshots` & `player_match_records`:** Append-only source-qualified metrics (`provider`, `scope`, `game_mode`, `season`, `sample_size`, `freshness`, `is_sample_demo`, `captured_at`) and deduplicated match history. Missing upstream fields stay `NULL`, never `0`.
- **`provider_snapshots`:** Append-only telemetry per fetch (`endpoint_category`, `player_identity`, `normalized_status`, `failure_reason`, `retry_eligible`, `data_freshness`, `last_successful_at`, `payload_json`).
- **`spreadsheet_imports` & `spreadsheet_import_rows`:** CSV / XLSX / Google Sheet provenance, `content_hash`, mapping config, and raw rows.
- **`match_rooms`, `match_room_players`, `team_generations`, `generated_team_players`, `generation_feedback`, `team_constraints`, `finalized_lineups`, `match_results`:** 10-slot room state, immutable team proposals with frozen `dimension_scores`, swap/lock/objection history, finalized assignments, and private community outcomes (`map_played`, `team_a_score`, `team_b_score`, `winner_side`) driving `GET /api/standings/community` independently of Valve/FACEIT ranks.
- **`watchlist_entries`, `trust_signals`, `activity_events`, `users`, `user_sessions`:** Separated integrity history, deduplicated feed, and PBKDF2/SHA-256 session auth. Secrets live outside SQLite (see [Operations](OPERATIONS.md)).

---

## 3. Canonical CS2 Metric Registry (`metric_registry.py`)

`GET /api/metrics/registry` defines the authoritative units, clamp bounds, provider mappings, UI visibility, and matchmaking roles for all 24 tracked dimensions:
- **Competitive Ladder Scales:** `premier_rating`, `leetify_rating` (normalized across rank vs match scales), `faceit_elo`, `faceit_level` (`1–10`).
- **Mechanics & Aim (`[0, 100]` / units):** `aim_rating`, `utility_rating`, `positioning_rating`, `preaim` (`0–180°`), `reaction_time_ms` (`50–2500 ms`; converts Leetify match `reaction_time` seconds to milliseconds), `spotted_accuracy`, `spray_accuracy`, `hs_pct`.
- **Combat, Survival, Entry, Utility & Clutch:** `adr` (`0–300`), `kd_ratio` (`0–10`), `win_rate`, `opening_duel_pct`, `trade_kills_per_match`, `traded_deaths_pct` (combined with `positioning_rating` in `positioning_score`), `utility_damage_per_round`, `flash_assists_per_round` (calibrated to `[0.002, 0.080]`/rd), `enemies_flashed_per_round`, `clutch_win_pct`, `consistency_score` (`counter_strafing_good_shots_ratio`), and `kast` (`None` on Leetify v3 until demo or manual community log data exists).

Out-of-range upstream values sanitize to `None` (`Unavailable`) rather than clamping to invented values.

---

## 4. Matchmaking Engine & Player Cards

### Exhaustive 126-Partition Balancer (`stackforge_126_v2` / `norm_v2`)
1. Requires **10 unique players** in `match_rooms`; supports non-blocking **Preflight** (`OK`, `FLAGGED`, `UNKNOWN`, `STALE`, `UNAVAILABLE`, `NOT_LINKED`, `NOT_CONFIGURED`).
2. Enumerates all **126 unique unordered 5v5 partitions**, enforces hard constraints (`lock`, `together`, `opponent`), and evaluates normalized ladder, combat composites, roles, recent form, and hidden map-pool robustness **without choosing or revealing a map**.
3. Returns recommended teams, distinct alternatives, deterministic CS2-grounded explanations (any optional LLM phrasing stays strictly bound to computed facts), confidence metrics, and **never invents uncalibrated 50/50 win probabilities**.
4. Lifecycle: `DRAFT -> PROPOSED -> REVIEWING -> FINALIZED -> PLAYED -> RESULT_RECORDED / ANALYZED` (every swap/remake creates a new immutable child generation; prior generations remain restorable).

### CS2 Player Cards (`card_rules_v1`)
- Evaluates verified `PlayerStatSnapshot` metrics deterministically (`sample_size >= 5` for positive style titles; `sample_size >= 8` or `>= 10` for negative gameplay banter).
- Players with `< 5` matches or unavailable stats receive safe defaults (*Uncharted Operative* / *Balanced All-Rounder*). Never hints at cheating; supports per-player toggles (`humour_enabled`, `Mild`/`Spicy`/`Savage`, hidden badges, tagline reroll).

---

## 5. Trust & Integrity Evidence Governance

- **Five separated `TrustSignal` classes:** `OFFICIAL_ENFORCEMENT` (Steam `GetPlayerBans` VAC/Game/Community/Economy + FACEIT bans), `THIRD_PARTY_REPUTATION` (CSWatch external signals), `COMMUNITY_REPORT`, `DEMO_BEHAVIOURAL_SIGNAL`, and `HUMAN_REVIEWED_EVIDENCE`.
- **Non-accusatory invariant:** Generic Steam `NumberOfGameBans` includes non-CS2 titles and non-cheat violations; high `ADR`/`HS%`/`aim_rating` or fast `reaction_time_ms` are **skill metrics, never cheat evidence**; trust flags never alter matchmaking skill ratings; missing/stale/private records remain `UNKNOWN`/`STALE`/`PRIVATE`, never converted into clean badges.

---

## 6. Architecture Decisions & REST Endpoints

- **Key ADRs (`D-001`–`D-014`):** Match room is primary; maps remain random; modular monolith; global `players` + community isolation; cached async adapters; separate source scale normalization; exact 126-partition search; immutable proposals; no uncalibrated win%; separated non-verdict trust classes; append-only ban/alias history.
- **API Groups (`/api`, local backend `8001`):**
  - Health/Ops/Registry: `GET /api/health`, `GET /api/metrics/registry`, `GET /api/ops/overview`
  - Vault: `GET/PUT/DELETE /api/settings/credentials*`, `POST /api/settings/credentials/{provider}/validate`
  - Players/Imports/Cards: `GET/POST/PATCH/DELETE /api/players*`, `GET /api/players/{id}/profile`, `POST /api/players/{id}/refresh`, `POST /api/players/refresh-all`, `GET /api/players/compare`, `PATCH /api/players/{id}/card-settings`, `POST /api/imports/*`, `POST /api/identity/{resolve,confirm}`
  - Rooms/Standings: `GET/POST /api/rooms*`, `PUT /api/rooms/{id}/roster`, `POST /api/rooms/{id}/{preflight,generate,regenerate,swap-preview,swap,finalize,reopen,played,result}`, `GET /api/standings/community`, `GET /api/lineups/{share_slug}`
  - Trust/Auth: `GET /api/trust/overview`, `POST /api/trust/{players/{id}/check,watchlist,reports,refresh-watched}`, `POST /api/auth/{signup,login,logout}`, `GET /api/auth/me`
- **Deferred `P3` Architecture:** Optional async `.dem`/`.dem.bz2` replay worker (`ProcessPoolExecutor(max_workers=1)`, `<= 250 MB`, Source2 header check, SHA-256 dedup, SteamID64-only matching) using `Awpy` (`provider="community_demo"`), Steam OpenID, and multi-community RBAC UI remain disabled/deferred until justified.
