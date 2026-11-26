# StackForge — Full Integration Audit, Ecosystem Research & Product Roadmap

Last audited: 2026-11-26 against `D:\CS2_StackForge` (`backend/stackforge.db`, `norm_v2`, `stackforge_126_v2`).

---

## 1. Provider & Integration Audit (Part B)

Verified against `backend/app/providers/`, `backend/app/services/`, and persistent `backend/stackforge.db` (`16` active community players, `72` provider snapshots per configured slot family, `53` `player_stat_snapshots` rows):

| Provider / Source | Code Location | Live Status Today | Config / Rate Limit | Persisted Data & Observed DB Evidence |
|---|---|---|---|---|
| **Steam Community XML (`?xml=1`) + Vanity** | `backend/app/providers/steam.py` (`SteamProvider`) | **ACTIVE KEYLESS** | Timeout bounded; TTL `900s` | `steam_profile` (`72 OK` snapshots); updates persona, avatar, visibility, vanity SteamID64, `player_aliases` |
| **Steam Web API (`GetPlayerBans` / keyed Summaries)** | `backend/app/providers/steam.py` | **NOT_CONFIGURED** (adapter ready) | Requires `STEAM_API_KEY` | `steam_bans` (`72 NOT_CONFIGURED` snapshots in keyless DB); populates `OFFICIAL_ENFORCEMENT` `TrustSignal` when keyed |
| **Leetify Public CS API v3** | `backend/app/providers/external.py` (`LeetifyProvider`) | **ACTIVE KEYLESS** (optional `LEETIFY_API_KEY`) | TTL `1800s`; 3x 429 `Retry-After`/backoff | `leetify` snapshots: `27 OK`, `20 NOT_LINKED`, `2 PRIVATE`, `22 RATE_LIMITED`, `1 UNAVAILABLE`; `53` stat snapshots (`27 lifetime`, `26 recent`) |
| **FACEIT Data API v4** | `backend/app/providers/external.py` (`FaceitProvider`) | **NOT_CONFIGURED** (adapter ready) | Requires `FACEIT_API_KEY`; TTL `1800s` | `faceit` (`72 NOT_CONFIGURED` snapshots); note Steam-linked FACEIT `level`/`elo` still ingests via Leetify `ranks` when present |
| **CSWatch Public API** | `backend/app/providers/cswatch.py` (`CSWatchProvider`) | **ACTIVE KEYLESS** | 25 req/min sliding cap; TTL `3600s` | `cswatch` (`72 OK` snapshots); writes `THIRD_PARTY_REPUTATION` `TrustSignal` cleanly separated from Valve bans |
| **Google Sheets / CSV / XLSX Import** | `backend/app/services/import_service.py` | **ACTIVE** | Public read-only `/export?format=csv` or file upload | `spreadsheet_imports`, `spreadsheet_import_rows`, players & external identity links |
| **URL / Identity Resolver & Alias History** | `backend/app/services/steam_parser.py`, `identity_resolver.py` | **ACTIVE** | Regex + vanity/summary canonicalization | SteamID64, Steam `/profiles/` & `/id/`, CSStats `/player/`, Leetify, CSWatch, FACEIT URLs -> `player_aliases` & `external_identities` |
| **Freshness Coordinator & Background Scheduler** | `backend/app/services/refresh_coordinator.py`, `scheduler.py` | **ACTIVE** | Single-flight locks; `900s`/`1800s`/`3600s` TTLs; `86400s` stale sweep | Startup, login, and 24h background stale checks (disabled under `pytest`) |
| **CSStats.gg** | `steam_parser.py`, `player_service.py` | **LINK-ONLY (NO SCRAPING)** | Cloudflare-gated | Extracts SteamID64 from URL and displays direct link only |
| **Tracker Network (`tracker.gg`)** | N/A | **UNSUPPORTED / REJECTED** | Legacy CS:GO API deprecated; CS2 API approval-gated; scraping prohibited | See [CS2_ECOSYSTEM_RESEARCH.md](CS2_ECOSYSTEM_RESEARCH.md) |
| **CSMeta / HLTV / BO3.gg / Mercurial.gg** | N/A | **UNSUPPORTED / REJECTED** | No self-serve public CS2 API / scraping prohibited | See [CS2_ECOSYSTEM_RESEARCH.md](CS2_ECOSYSTEM_RESEARCH.md) |
| **Scope.gg / CSST.at / CStrike.gg / Suspect.gg / CS.Ninja** | N/A | **RESEARCH ONLY** | Closed or private APIs; conceptual UX/methodology references | See [CS2_ECOSYSTEM_RESEARCH.md](CS2_ECOSYSTEM_RESEARCH.md) |

---

## 2. CS2 Metric End-to-End Pipeline Trace & Flagged Gaps

| Metric | Provider Extraction | DB (`community_players` / `player_stat_snapshots`) | API / Schema (`PlayerOut` / `StatSnapshotOut`) | Frontend Display (`PlayerStatsView` / Standings / Profile) | Normalization (`norm_v2`) | Matchmaking (`stackforge_126_v2`) & Explanations |
|---|---|---|---|---|---|---|
| `premier_rating` | Leetify `ranks.premier` | `community_players.premier_rating` | Yes (`PlayerOut`) | Yes (Registry, Standings, Profile) | Yes (`0.36` ladder weight) | Yes (scale-normalized + explanation) |
| `faceit_elo` / `faceit_level` | Leetify `ranks.faceit_elo`/`faceit`, FACEIT v4 | `community_players.faceit_elo`, `faceit_level` | Yes (`PlayerOut`) | Yes (Registry, Standings, Profile) | `faceit_elo` (`0.36` ladder weight); `faceit_level` display | Yes (`faceit_elo` in strength + explanation) |
| `leetify_rating` | Leetify `ranks.leetify` / match avg | `community_players.leetify_rating` + `recent_form` | Yes (`PlayerOut`) | Yes (Registry, Standings, Profile) | Yes (`0.32` ladder weight + form adjustment) | Yes |
| `aim_rating` | Leetify `rating.aim` (`7` DB rows non-null) | Both tables | Yes | Yes (`Aim Rating`, Profile, Standings) | Yes (`0.50` weight inside `aim_score`) | Yes (`aim_score` weighted `0.28 * cov`) |
| `utility_rating` | Leetify `rating.utility` (`7` DB rows non-null) | Both tables | Yes | Yes (`Utility Rating`, Profile) | Yes (`0.56` weight inside `utility_score`) | Yes (`utility_score` weighted `0.24 * cov`) |
| `positioning_rating` | Leetify `rating.positioning` (`8` DB rows non-null) | Both tables | Yes | Yes (`PlayerStatsView` KPI + `METRIC_LABELS`) | Yes (`0.72` weight inside `positioning_score`) | Yes (`pos_gap` in `engine.py` + positioning notes in explanations) |
| `preaim` | Leetify `stats.preaim` & matches (`16` rows) | Both tables | Yes | Yes (`Pre-aim (°)`) | Yes (`0.18` of `aim_score`) | Indirect via `aim_score` |
| `reaction_time_ms` | Leetify `stats.reaction_time_ms` / match `reaction_time` (`16` rows) | Both tables | Yes | Yes (`Time to Damage`) | Yes (`0.14` of `aim_score`) | Indirect via `aim_score` |
| `spotted_accuracy` / `spray_accuracy` | Leetify `stats.*` & matches (`16` rows each) | `player_stat_snapshots` | Yes | Yes (`Spotted Acc`, `Spray Acc`) | Yes (`0.08` & `0.05` of `aim_score`) | Indirect via `aim_score` |
| `kd_ratio` / `adr` / `hs_pct` / `win_rate` | Leetify recent30/10 & FACEIT lifetime (`54-55` rows) | `player_stat_snapshots` | Yes | Yes (Registry, Standings, Profile) | `adr` (`0.72` `damage_score`), `kd_ratio` (`0.55` `survival_score`), `hs_pct` (`0.05` `aim_score`) | `combat_composite` (`0.28` damage, `0.20` survival, `0.21` aim, `0.13` utility, `0.08` pos, `0.05` entry, `0.05` clutch) |
| `opening_duel_pct` / `trade_kills_per_match` / `clutch_win_pct` | Leetify `stats` / `rating.clutch` / matches (`28-36` rows) | `player_stat_snapshots` | Yes | Yes (`Opening Duel %`, `Trade Kills %`, `Clutch Win %`) | `entry_score`, `trade_score`, `clutch_score` | Used directly in `engine.py` (`0.14`, `0.12`, `0.10` * cov) + CS2 explanations |
| `utility_damage_per_round` / `flash_assists_per_round` / `enemies_flashed_per_round` | Leetify `stats` & matches (`16-55` rows) | `player_stat_snapshots` | Yes | Yes (`Utility Dmg / Rd`, `Flash Assists / Rd`, `Enemies Flashed / Rd`) | Inside `utility_score` (`flash_assists_per_round` calibrated to `[0.002..0.080]`/rd) | Indirect via `utility_score` + CS2 explanations |
| `consistency_score` | Leetify `counter_strafing_good_shots_ratio` (`36` rows) | `player_stat_snapshots` | Yes | Yes (`Counter-Strafe %`) | Inside `damage_score` (`0.28`) | Used directly in `engine.py` (`cons_gap * 0.10 * cov`) |
| `traded_deaths_pct` | Leetify `traded_deaths_success_percentage` (`16` rows) | `player_stat_snapshots` | Yes (`StatSnapshotOut`) | Yes (`Traded Deaths %` in `METRIC_LABELS` & Profile) | Yes (`0.28` weight inside `positioning_score`) | Yes (inside `positioning_score` & team positioning notes) |
| `kast` | Unavailable on Leetify v3 (`0` non-null rows in DB) | Column exists (`NULL` unless manual log) | Yes | Shown only when present (else hidden/N/A) | `survival_score` blends `kd_ratio` (`0.55`) & `kast` (`0.45`) with auto re-normalization | Gracefully omitted cleanly |
| **Computed sub-scores & `manual_rating`** | N/A | Sub-scores now frozen inside `team_generations.input_snapshot_json` (`dimension_scores`); `manual_rating` legacy-only | `manual_rating` ignored; sub-scores computed | `manual_rating` removed from user-facing forms & spreadsheet import mappings | `manual_rating=None` forced everywhere in `player_service.py` & `normalizer.py` | Excluded from balancing (`0` effect) |

---

## 3. Open-Source CS2 Ecosystem Research & Comparison (Part C)

| Project | Stack & Architecture | License | Core Strengths vs StackForge | Adoption Complexity | Verdict / Priority |
|---|---|---|---|---|---|
| **[akiver/cs-demo-manager](https://github.com/akiver/cs-demo-manager)** | Electron + TypeScript + Go (`cs-demo-analyzer` / `demoinfocs-golang`) + PostgreSQL | **MIT** | Mature desktop UI, HLTV rating, KAST, 2D minimap replay viewer, video export, VAC ban watcher | High (desktop Electron + Go + Postgres) | **Reference only** (borrow schema/KAST calculations & ban-tracking UX; do not fork desktop runtime) |
| **[pnxenopoulos/awpy](https://github.com/pnxenopoulos/awpy)** | Python wrapper over Rust (`pbdems2`) emitting Polars DataFrames & Parquet | **MIT** | Clean Python API matching StackForge's FastAPI backend; round reconstruction, KAST/ADR/trade computation, visibility/analytics helpers | Medium (requires background worker queue for 50–150 MB `.dem` files) | **Recommended P3 candidate** for StackForge's async `.dem` parser |
| **[LaihoE/demoparser (`demoparser2`)](https://github.com/LaihoE/demoparser)** | Rust core with native Python (`demoparser2`), Node/TS, and WASM bindings | **MIT** | Extreme raw tick/property query throughput (`X,Y,Z`, viewangles, weapon states, damage/kill tables) | Medium-Low (if building lightweight custom aggregators) | **Strong alternative P3 parser** if minimal dependencies & fastest tick extraction are preferred over `awpy`'s higher-level frame abstractions |
| **[JulianoBazzi/CSManager](https://github.com/JulianoBazzi/CSManager)** | Next.js 16 + React 19 + Chakra UI 3 + Supabase + OpenAI Vision scoreboard OCR | **MIT** | Community yearly & per-map leaderboards, AI comparison copy, automated match sweepstakes & screenshot scoreboard capture | Medium (for ideas; stack mismatch — Supabase/Next vs FastAPI/SQLite) | **UX Reference** for yearly standings, per-map community records, and optional screenshot-to-post-match ingestion |
| **[Leetify Public CS API v3](https://api-public-docs.cs-prod.leetify.com/)** | Hosted REST API (`/v3/profile`, `/v3/profile/matches`, `/v2/matches/{gameId}`, `/api-key/validate`) | Proprietary TOS (free public tier) | Already supplies KAST-free preaim, time-to-damage, utility, opening duels, and match history keyless | **Zero** (already integrated; optional key unlocks higher quota & `/v2/matches/{gameId}` round detail) | **P1 quick win:** add `LEETIFY_API_KEY` support docs/validation indicator and optional `/v2/matches/{gameId}` deep link/enricher |

---

## 4. Recommended Product Improvements & Roadmap (Part D)

Designed to extend `D:\CS2_StackForge` cleanly without violating `Rules.md` (**strictly keep Random Map Policy — never add a map picker/veto**):

1. **Priority 1 — Post-Match Result System (Fastest Community Value)**
   - Add a **Record Match Outcome** flow to finalized `MatchRoom` records (`match_outcomes` table linked to `match_rooms` + `team_generations`): winner (Team A / Team B / Tie), random-rolled map played (`de_*`), final round score (e.g. `13-9`), optional per-player K/D/A/ADR or Leetify/FACEIT match link, and automatic `completed` room status transition.
   - Surface **Surface-the-Unused-Metrics** quick patch alongside it: render stored `positioning_rating` and `traded_deaths_pct` cleanly on `PlayerStatsView` (zero new API calls required!).
2. **Priority 1 / 2 — Community Leaderboard & Season Standings**
   - Build an internal **Private 5v5 Standings** view backed by recorded `match_outcomes` (community W-L record, win %, internal Elo/CSR delta, clutch/ADR leaders, head-to-head teammate/opponent chemistry, and current win/loss streaks) separate from public Valve/FACEIT ladder ranks.
3. **Priority 2 — Match Organization & Pre-Game Workflow**
   - Add **One-Click "Fill Last 10 / Core Squad"** and **Discord Check-In Import** (paste Discord nicknames/mentions to auto-select 10 players in seconds).
   - Keep **Random Map Generator** purely random (e.g., spin/roll from Active Duty pool *after* teams are finalized to decide what server map to launch, never as a vote/picker influencing team splits).
4. **Priority 3 — Asynchronous CS2 `.dem` Analysis Pipeline**
   - Introduce `demo_uploads` + background job worker (`awpy` or `demoparser2` in Python) accepting `.dem` / `.dem.bz2` files uploaded after private custom matches (where Leetify/Valve may not track local dedicated server games).
   - Compute exact **KAST**, **trade kills & traded deaths**, **flash assists**, **opening duels**, **utility damage**, and **1vX clutches** from the actual custom lobby demo, storing per-match `player_stat_snapshots` (`provider="community_demo"`) without blocking any FastAPI request thread.
