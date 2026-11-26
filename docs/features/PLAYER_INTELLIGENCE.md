# Feature: Player Intelligence V2, Canonical Metrics & Auto Freshness

**Status:** Implemented & Verified (`metric_registry.py`, `external.py`, `player_service.py`, `refresh_coordinator.py`, `scheduler.py`, `secrets_service.py`, `ops_service.py`, `PlayerStatsView.tsx`, `OpsAndSettingsView.tsx`)

## Canonical CS2 Metric Registry (`GET /api/metrics/registry`)
Every metric has an explicit definition in `backend/app/services/metric_registry.py` (unit, value type, valid clamp bounds, source mapping, data scope, confidence/freshness, UI display, and matchmaking status):
- **Primary Competitive Scales (displayed with provider/source, never summed blindly):**
  - `CS2 Premier CSR` (`premier_rating`, sourced from Leetify `ranks.premier`)
  - `Leetify Rating` (`leetify_rating`, `ranks.leetify` / normalized across match records)
  - `FACEIT ELO` & `FACEIT Skill Level` (`FACEIT Data API v4` when key present or Leetify `ranks.faceit_elo`/`faceit`)
- **Mechanical, Positioning & Utility Ratings (`Leetify v3`, bounds-validated `[0, 100]`):**
  - `aim_rating` (`rating.aim`), `utility_rating` (`rating.utility`), **`positioning_rating` (`rating.positioning` — now displayed in Profile + Stat Snapshots & feeding `positioning_score`)**
  - `preaim` (`[0, 180]°`), `reaction_time_ms` (`[50, 2500] ms`, converting match `reaction_time` seconds -> ms), `spotted_accuracy` (`%`), `spray_accuracy` (`%`), `hs_pct` (`%`)
- **Combat, Survival, Entry, Trading & Clutch:**
  - `adr` (`[0, 300]`), `kd_ratio` (`[0, 10]`), `win_rate` (`%`), `opening_duel_pct` (`%`), `trade_kills_per_match` (`%`), **`traded_deaths_pct` (`%` — now displayed in UI & blended with `positioning_rating` into `positioning_score`)**, `utility_damage_per_round`, `flash_assists_per_round` (re-calibrated to per-round CS2 rates `[0.002, 0.080]`), `enemies_flashed_per_round`, `clutch_win_pct`, `consistency_score` (`counter_strafing_good_shots_ratio`).
  - **Missing-data rule:** Fields absent from upstream APIs (`kast` on Leetify v3) remain `None` (`Unavailable`) unless extracted from community demos or manually logged. Out-of-range/corrupt upstream numbers are sanitized to `None`.

## Keyless Mode & Optional Encrypted Credentials (`secrets_service.py`)
- Operates keyless by default via Steam Community `?xml=1`, Leetify Public v3, CSWatch Public API, and Google Sheets CSV.
- Optional API keys (`STEAM_API_KEY`, `FACEIT_API_KEY`, `LEETIFY_API_KEY`) can be configured via `Ops & Keys` (`PUT/POST/DELETE /api/settings/credentials/{provider}`), encrypted server-side using **Windows DPAPI** (`CryptProtectData`, stored outside SQLite in gitignored `.stackforge_secrets.dpapi.json`), never logged or sent back to the browser.

## Individual Refresh, Operational Health & Active Scheduler
- Fixed `main.py` reference bug so `/api/health` (`"scheduler": "active"`) accurately reflects `scheduler._scheduler_task` in runtime!
- `ProviderSnapshot` records `endpoint_category`, `player_identity`, `normalized_status`, `failure_reason`, `retry_eligible`, `data_freshness`, and `last_successful_at`.
- `LeetifyProvider` uses bounded retry (`Retry-After <= 5s`, max 3 attempts) to avoid repeated blocking retries on long HTTP 429 windows.
- `Ops & Keys` (`GET /api/ops/overview`) exposes honest per-provider health (`HEALTHY` / `PARTIAL_COVERAGE` / `NOT_CONFIGURED` / `DEGRADED`), rate-limit events, stale/insufficient players with 1-click refresh, and scheduler cycle telemetry.
