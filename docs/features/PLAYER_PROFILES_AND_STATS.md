# Feature: Player Profiles & Source-Qualified Statistics

**Status:** Implemented (SQLite snapshots + FACEIT/Leetify adapters + community match stat logging)

## Purpose
Give authorized community members a transparent view of each teammate's identity, competitive ratings, combat metrics, data freshness, and side-by-side player comparison without conflating incompatible rating scales.

## User Flow
1. Open **Player Stats** or click **Profile** on any player in the Registry, Dashboard, or Match Room.
2. Inspect Identity, Competitive Profile (`norm_v1`, Premier, FACEIT ELO, Leetify Rating, Manual Baseline), Alias History, Provider Statuses, and Combat Statistics.
3. Filter combat snapshots by provider (`community_match`, `faceit`, `leetify`) and scope (`recent`, `lifetime`, `season`).
4. Optionally log community match statistics via `Log Match Stats` or switch to **Compare Players** for a side-by-side comparison.

## Data Requirements
- `player_stat_snapshots`: stores `provider`, `scope`, `game_mode`, `season`, `sample_size`, `matches_played`, `win_rate`, `kd_ratio`, `adr`, `kast`, `hs_pct`, `opening_duel_pct`, `trade_kills_per_match`, `utility_damage_per_round`, `flash_assists_per_round`, `clutch_win_pct`, `multi_kill_rate`, `consistency_score`, `freshness`, `is_sample_demo`, `captured_at`.
- Missing fields remain `NULL` (`Unavailable from this source`), never `0`.

## API Contracts
- `GET /api/players/{id}/profile` -> `PlayerProfileOut`
- `POST /api/players/{id}/stats` -> `PlayerProfileOut` (records source-qualified snapshot)
- `GET /api/players/compare?a={id1}&b={id2}` -> `PlayerCompareOut`
- `PATCH /api/players/{id}/card-settings` -> updates `stats_visibility` (`COMMUNITY` | `HOST_ONLY`) and card preferences.

## UI Behaviour
- Separate KPI cards for normalized strength, Premier rating, FACEIT ELO, and Leetify/Manual baseline.
- Side-by-side comparison renders proportional bars only for non-null metrics.
- Demo sample stats are tagged `DEMO SAMPLE`.

## Failure Handling
- Unconfigured providers show `NOT_CONFIGURED` / `Unavailable`; manual and community-logged snapshots remain fully usable.

## Security & Privacy
- `stats_visibility` and `profile_visibility` controls are stored server-side; provider API keys never reach frontend bundles.
- Community notes are separated from public provider observations.

## Acceptance Criteria
- Every displayed metric shows provider, scope, sample size, freshness, and timestamp.
- Missing metrics render `Unavailable from this source`, never `0`.

## Implemented vs Deferred
- **Implemented:** Full profile view, FACEIT/Leetify combat stat extraction (when keys configured), manual community stat snapshot logging, PvP compare, demo sample labeling.
- **Deferred:** Automated post-match `.dem` parsing via Awpy and multi-tenant auth RBAC enforcement.
