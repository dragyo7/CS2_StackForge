# Feature: Player Intelligence V2, Individual Refresh & Auto Freshness

**Status:** Implemented & Live-Tested (`backend/app/providers/external.py`, `backend/app/services/player_service.py`, `backend/app/services/refresh_coordinator.py`, `backend/app/services/scheduler.py`, `PlayerRegistryView.tsx`, `PlayerStatsView.tsx`)

## Supported CS2 Metrics & Ratings (Verified Genuine API Fields Only)
- **Primary Competitive Scales (displayed with provider/source, never summed blindly):**
  - `CS2 Premier CSR` (sourced from Leetify `ranks.premier` when linked)
  - `Leetify Rating` (sourced from Leetify `ranks.leetify`)
  - `FACEIT ELO` & `FACEIT Skill Level` (from `FACEIT Data API v4` when `FACEIT_API_KEY` configured, or Leetify `ranks.faceit_elo` / `ranks.faceit` when exposed)
- **Mechanical & Utility Ratings (`Leetify v3`):**
  - `aim_rating` (`rating.aim`), `utility_rating` (`rating.utility`), `positioning_rating` (`rating.positioning`)
  - `preaim` (degrees), `reaction_time_ms` (ms), `spotted_accuracy` (%), `spray_accuracy` (%), `hs_pct` (%)
- **Combat, Survival, Entry, Trading & Clutch:**
  - `adr` (`dpr`), `kd_ratio`, `win_rate`, `opening_duel_pct` (CT/T mean), `trade_kills_per_match`, `traded_deaths_pct`, `utility_damage_per_round` (HE avg), `flash_assists_per_round`, `enemies_flashed_per_round`, `clutch_win_pct`, `consistency_score` (`counter_strafing_good_shots_ratio`), `multi_kill_rate`, plus deduplicated `player_match_records`.
  - **Missing-data rule:** Fields genuinely absent (e.g., `kast` in Leetify v3) remain `None` (`Unavailable from this source`) — never zero-filled and never scraped.

## Individual & Automatic Refresh Policy
- **Refresh Player (`POST /api/players/{id}/refresh?force=...&provider=...`):** Refreshes only that target player (all providers or a specific `steam` / `leetify` / `faceit` / `cswatch` slice) and returns itemized statuses (`SUCCESS`, `PARTIAL`, `PRIVATE`, `NOT_LINKED`, `NOT_CONFIGURED`, `RATE_LIMITED`, `UNAVAILABLE`, `FAILED`). Available from Players Registry (Cards & Standings), Player Profile, and Match Room (Roster & Picker).
- **Rate-Limit & Single-Flight Protections:** Per-provider TTLs (`steam` 15m, `leetify` 30m, `faceit` 30m, `cswatch` 60m), concurrent request deduplication (`run_single_flight`), per-provider async spacing (`throttle_provider`), `Retry-After` parsing + exponential backoff on HTTP `429`, and strict preservation of last-known-good snapshots on error.
- **Single-Instance Auto Scheduler (`scheduler.py`):** On backend startup (with polite randomized jitter), every `24 hours`, and on user login (for the signed-in user's stale linked Steam account), refreshes only profiles whose `last_successful_refresh_at` is missing or older than `24h` (automatically disabled under `pytest`).
