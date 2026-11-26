# StackForge Architecture, Data Model & API Reference

> **Status:** Active Modular Monolith (`React 18 + TypeScript + Vite` + `FastAPI + SQLAlchemy + SQLite`)  
> **Ports (Local V2):** Backend `127.0.0.1:8001` · Frontend `127.0.0.1:5174`

---

## 1. System Architecture & Runtime Boundaries

StackForge is intentionally structured as a single-service modular monolith backed by a local SQLite database (`backend/stackforge.db`), avoiding premature microservices, Kafka, Redis, or Kubernetes overhead while keeping clean module boundaries inside `backend/app/`.

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

### Verified Codebase Layout

- **Backend entry & config:** `backend/app/main.py`, `backend/app/config.py`, `backend/app/database.py`, `backend/app/migrations.py`, `backend/app/models.py`, `backend/app/schemas.py`
- **Backend routes:** `backend/app/routes/platform.py`, `backend/app/routes/players.py`, `backend/app/routes/rooms.py`
- **Backend services:** `auth_service.py`, `humour_engine.py`, `identity_resolver.py`, `import_service.py`, `match_result_service.py`, `metric_registry.py`, `ops_service.py`, `player_service.py`, `refresh_coordinator.py`, `room_service.py`, `scheduler.py`, `secrets_service.py`, `steam_parser.py`, `trust_service.py`
- **Backend providers:** `backend/app/providers/base.py`, `backend/app/providers/steam.py`, `backend/app/providers/external.py`, `backend/app/providers/cswatch.py`
- **Backend optimizer:** `backend/app/optimizer/normalizer.py`, `backend/app/optimizer/engine.py`
- **Frontend:** `frontend/src/App.tsx`, `api.ts`, `types.ts`, `styles.css`, and views (`DashboardView.tsx`, `LandingAuthView.tsx`, `MatchRoomView.tsx`, `OpsAndSettingsView.tsx`, `PlayerAvatar.tsx`, `PlayerCardsView.tsx`, `PlayerCardTile.tsx`, `PlayerRegistryView.tsx`, `PlayerStatsView.tsx`, `SharedLineupView.tsx`, `TrustWatchView.tsx`, `CommunityImportPanel.tsx`)

---

## 2. Data Model & Provenance (`SQLite + SQLAlchemy`)

### Identity, Profiles & Stats
- **`players`**: global canonical identity keyed by string `steam_id64`, holding `vanity_name`, `steam_persona_name`, `avatar_url`, `identity_status`, `profile_visibility`, `last_successful_refresh_at`, `last_refresh_attempt_at`, `refresh_status`, and `refresh_error`.
- **`player_aliases`**: append-only historical Steam/provider name observations (`player_id`, `alias_name`, `previous_name`, `source`, `observed_at`) with consecutive duplicate suppression so profile searches match old aliases without duplicating players.
- **`player_external_identities`**: verified or candidate cross-provider links (`steam`, `csstats`, `leetify`, `faceit`, `cswatch`) with `verification_state` (`VERIFIED` | `CANDIDATE` | `UNRESOLVED`) and confidence.
- **`communities` & `community_players`**: tenant membership (`Main CS2 Stack` default), `display_name`, roles, `premier_rating` (+ source/season), `faceit_elo`, `faceit_level`, `leetify_rating`, `recent_form`, `aim_rating`, `utility_rating`, `positioning_rating`, `preaim`, `reaction_time_ms`, `is_archived`, notes, and card settings (`humour_enabled`, `humour_intensity`, `hidden_badges_json`, `card_tagline_variant`, `stats_visibility`). Legacy `manual_rating` column is retained strictly for backwards schema safety and ignored (`manual_rating=None` forced in `norm_v2`).
- **`player_stat_snapshots`**: append-only source-qualified competitive and combat metrics (`provider`, `scope`, `game_mode`, `season`, `sample_size`, `matches_played`, `win_rate`, `kd_ratio`, `adr`, `kast`, `hs_pct`, `opening_duel_pct`, `trade_kills_per_match`, `traded_deaths_pct`, `utility_damage_per_round`, `flash_assists_per_round`, `enemies_flashed_per_round`, `clutch_win_pct`, `multi_kill_rate`, `consistency_score`, `spotted_accuracy`, `spray_accuracy`, `freshness`, `is_sample_demo`, `captured_at`). Missing metrics are stored as `NULL`, never `0`.
- **`player_match_records`**: deduplicated recent/community match records (`provider`, `external_match_id`, `map_name`, `outcome`, `score_text`, `kd_ratio`, `adr`, `hs_pct`, `leetify_rating`, `played_at`).
- **`provider_snapshots`**: append-only upstream fetch telemetry (`steam_profile`, `steam_bans`, `faceit`, `leetify`, `cswatch`) recording `endpoint_category`, `player_identity`, `normalized_status`, `failure_reason`, `retry_eligible`, `data_freshness`, `last_successful_at`, and `payload_json`.

### Imports, Match Rooms & Standings
- **`spreadsheet_imports` & `spreadsheet_import_rows`**: Google Sheet / CSV / XLSX provenance, `content_hash`, column mapping, sync timestamps, and raw row JSON.
- **`match_rooms` & `match_room_players`**: 10-slot lobby state and optional pre-generation team locks.
- **`team_generations` & `generated_team_players`**: immutable balancing proposals storing seed, algorithm version (`stackforge_126_v2`), parent generation, frozen input snapshot (`dimension_scores` + per-player normalized inputs), objective score, and natural-language CS2 explanations.
- **`generation_feedback` & `team_constraints`**: player approvals/objections, swap requests, team locks, together pairs, and opponent pairs.
- **`finalized_lineups` & `match_results`**: immutable finalized team assignments plus post-match outcome records (`map_played`, `team_a_score`, `team_b_score`, `winner_side`, `result_source`, `lineup_snapshot_json`, `played_at`) feeding private community standings (`W-L-T`, round differential, `community_internal_rating`) isolated from external ladder ranks.

### Integrity & Auth
- **`watchlist_entries`, `trust_signals`, `activity_events`**: separated integrity categories (`OFFICIAL_ENFORCEMENT`, `THIRD_PARTY_REPUTATION`, `COMMUNITY_REPORT`, `DEMO_BEHAVIOURAL_SIGNAL`, `HUMAN_REVIEWED_EVIDENCE`), append-only observations, and deduplicated alert feed.
- **`users` & `user_sessions`**: PBKDF2-HMAC-SHA256 password hashes and SHA-256 hashed session tokens.
- **Secrets outside SQLite:** optional `STEAM_API_KEY`, `FACEIT_API_KEY`, and `LEETIFY_API_KEY` are encrypted via Windows DPAPI inside `.stackforge_secrets.dpapi.json` (`secrets_service.py`), never stored in SQLite.

---

## 3. Matchmaking Engine & User Flows

### Match-Room Workflow
1. Create or open a room (`DRAFT`). **No map picker or map veto exists.**
2. Add/select **10 unique players** from saved registry, CSV/Google Sheet sync, or inline Steam/Leetify/FACEIT/CSWatch/CSStats URL paste (auto-resolved without duplicate creation).
3. Run non-blocking **Preflight** across local cache + configured providers (`OK`, `FLAGGED`, `UNKNOWN`, `STALE`, `UNAVAILABLE`, `NOT_LINKED`, `NOT_CONFIGURED`). Provider outages warn without blocking room progression.
4. **Generate Teams** (`stackforge_126_v2`): enumerates all **126 unique unordered 5v5 partitions** across the 10 players (mirroring deduplicated), applies hard constraints (`lock`, `together`, `opponent`), scores multi-dimension balance (ladder scale, aim/utility/positioning composites, entry/trade/clutch, consistency, form, roles, hidden map-pool robustness), and returns the top split + distinct alternatives with CS2-grounded explanations.
5. Negotiate swaps (`swap-preview` delta), locks, remakes (new immutable child generation preserving history), or restore earlier proposals.
6. **Finalize** (`FINALIZED`) to freeze teams and export Discord lineup -> mark **Played** (`PLAYED`) -> record **Post-Match Result** (`RESULT_RECORDED` / `ANALYZED`).

### Core Normalization Rules (`norm_v2`)
- Competitive ladder scales (`premier_rating`, `faceit_elo`, `leetify_rating`) and combat dimensions are normalized separately with cohort shrinkage and coverage weights.
- Unknown metrics lower data confidence rather than substituting zeroes or hidden manual ratings.
- StackForge does not display fabricated 50/50 win probabilities.

---

## 4. Architecture Decision Summary

| ID | Decision | Rationale & Consequence |
|---|---|---|
| **D-001 / D-002** | Private 10-player organizer; maps remain random | Match room is the primary screen; no map picker/veto; map stats act only as hidden pool robustness inputs. |
| **D-003 / D-004** | Single modular monolith; global `players` + community scope | FastAPI + SQLite (`run_migrations`) keeps local deployment friction near zero while isolating community notes/standings by `community_id`. |
| **D-005 / D-014** | Adapter isolation + cached async refresh | External rate limits/outages never block team selection or balancing; TTLs + single-flight dedup bound upstream traffic. |
| **D-006 / D-007** | Source-qualified metrics & separate scale normalization | No official public Valve Premier history endpoint assumed; missing stats remain `None` / `Unavailable`. |
| **D-008 / D-009 / D-012 / D-013** | Exact 126-partition search, immutable proposals, no fake win% | Deterministic & reversible generation with transparent balance gaps and confidence rather than uncalibrated win odds. |
| **D-010 / D-011** | Separated non-verdict trust classes & append-only history | Enforcement, CSWatch reputation, community reports, and human reviews never merge into a single "cheat score." |

---

## 5. REST API Reference (`http://127.0.0.1:8001/api`)

### Health, Metrics & Operational Telemetry
- `GET /api/health` — Backend readiness, provider config summary (`steam`, `faceit`, `leetify`, `cswatch`), `map_policy: "random_no_picker"`, active/inactive `scheduler`, and `scheduler_detail`.
- `GET /api/metrics/registry` — Canonical 24-metric registry definitions (unit, clamp bounds, provider field map, scope, UI/matchmaking role).
- `GET /api/ops/overview` — DB counts, scheduler cycle telemetry, per-provider ingestion health (`HEALTHY`, `PARTIAL_COVERAGE`, `NOT_CONFIGURED`, `DEGRADED`), rate-limit/private counts, stale/insufficient players, credential status, and future demo queue placeholder.

### Credentials Vault (`Windows DPAPI`)
- `GET /api/settings/credentials` — Masked hints (`****1234`) & active status for `steam`, `faceit`, `leetify`.
- `PUT /api/settings/credentials/{provider}` — Encrypt and store optional API key server-side (supports optional live validation).
- `POST /api/settings/credentials/{provider}/validate` — Validate candidate or stored key without exposing plaintext.
- `DELETE /api/settings/credentials/{provider}` — Remove stored key from DPAPI vault.

### Players, Intelligence, Imports & Cards
- `GET /api/players` · `GET /api/players/rankings` · `POST /api/players` · `PATCH /api/players/{id}` · `DELETE /api/players/{id}` · `POST /api/players/{id}/archive`
- `GET /api/players/{id}/profile` — Normalized profile, stat snapshots, recent match records, alias history, external identities, provider statuses, trust summary, and `card`.
- `POST /api/players/{id}/refresh?force=false&provider=all` (`all` | `steam` | `leetify` | `faceit` | `cswatch`)
- `POST /api/players/refresh-all?force=false`
- `POST /api/players/{id}/stats` · `GET /api/players/compare?a=...&b=...` · `PATCH /api/players/{id}/card-settings`
- `POST /api/players/bulk-import` · `POST /api/imports/google-sheet/{preview,commit}` · `POST /api/imports/file/{preview,commit}` · `POST /api/imports/{id}/sync`
- `POST /api/identity/resolve` · `POST /api/identity/confirm`

### Match Rooms, Balancing & Community Standings
- `GET /api/rooms` · `POST /api/rooms` · `GET /api/rooms/{id}`
- `PUT /api/rooms/{id}/roster` · `POST /api/rooms/{id}/replace-player` · `PUT /api/rooms/{id}/players/{pid}/lock` · `POST /api/rooms/{id}/constraints`
- `POST /api/rooms/{id}/preflight` · `POST /api/rooms/{id}/generate` · `POST /api/rooms/{id}/regenerate`
- `POST /api/rooms/{id}/swap-preview` · `POST /api/rooms/{id}/swap` · `POST /api/rooms/{id}/proposals/{gid}/adopt-alternative` · `POST /api/rooms/{id}/proposals/{gid}/restore`
- `POST /api/rooms/{id}/finalize` · `POST /api/rooms/{id}/reopen` · `POST /api/rooms/{id}/played` · `POST /api/rooms/{id}/result`
- `GET /api/standings/community` · `GET /api/lineups/{share_slug}`

### Trust Watch & Auth
- `GET /api/trust/overview` · `POST /api/trust/players/{id}/check` · `POST /api/trust/watchlist` · `PATCH /api/trust/watchlist/{id}` · `POST /api/trust/reports` · `POST /api/trust/refresh-watched`
- `POST /api/auth/{signup,login,logout}` · `GET /api/auth/me`

---

## 6. Deferred / Planned Enhancements

- **Async CS2 `.dem` Replay Pipeline (`P3`):** Parse optional post-match `.dem` / `.dem.bz2` uploads (strictly bounded `<= 250 MB`, HL2/Source2 header check, SHA-256 deduplication, SteamID64-only player matching, isolated `ProcessPoolExecutor(max_workers=1)` outside HTTP threads) using **`Awpy`** (`pnxenopoulos/awpy`) to extract true private-lobby `KAST`, trade stats, utility damage, flash assists, and 1vX clutches tagged `provider="community_demo"` — cleanly isolated from public ladder ratings and any `DEMO_BEHAVIOURAL_SIGNAL` governance warnings. Disabled in runtime until justified.
- **Identity & Access:** Optional Steam OpenID account linking and multi-community membership/role enforcement UI.
- **Automated Ban Watchlist:** Continuous Valve `GetPlayerBans` diff alerts once `STEAM_API_KEY` is configured by a deployment.
