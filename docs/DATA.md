# Data Model and Data Governance

## Core identity model (Implemented in SQLite + SQLAlchemy)
- `players`: global CS2 player identity canonically keyed by `steam_id64` string (`vanity_name`, `steam_persona_name`, `avatar_url`, `identity_status`, `last_successful_refresh_at`, `last_refresh_attempt_at`, `refresh_status`, `refresh_error`, `profile_visibility`).
- `player_aliases`: append-only historical display-name observations (`player_id`, `alias_name`, `previous_name`, `source`, `observed_at`) with consecutive duplicate suppression.
- `player_stat_snapshots`: source-qualified, timestamped competitive & combat metrics (`provider`, `scope`, `game_mode`, `season`, `sample_size`, `matches_played`, `win_rate`, `kd_ratio`, `adr`, `kast`, `hs_pct`, `opening_duel_pct`, `trade_kills_per_match`, `utility_damage_per_round`, `flash_assists_per_round`, `clutch_win_pct`, `multi_kill_rate`, `consistency_score`, `freshness`, `is_sample_demo`, `captured_at`). Missing metrics are stored as `NULL`, never `0`.
- `provider_snapshots`: append-only raw provider status/payload observations (`steam_profile`, `steam_bans`, `faceit`, `leetify`).
- `communities`: tenant (`Main CS2 Stack` default).
- `community_players`: tenant-specific `display_name`, `manual_rating`, `premier_rating` (+ source/season), `faceit_elo`, `leetify_rating`, `recent_form`, roles, `notes`, `is_seeded`, and card/visibility controls (`humour_enabled`, `humour_intensity`, `hidden_badges_json`, `card_tagline_variant`, `stats_visibility`).
- `player_external_identities`: canonical cross-provider mappings (`steam`, `csstats`, `leetify`, `faceit`, `cswatch`) with `verification_state` (`VERIFIED` | `CANDIDATE` | `UNRESOLVED`) and confidence.
- `player_match_records`: deduplicated external/private match history (`provider`, `external_match_id`, `map_name`, `outcome`, `score_text`, `kd_ratio`, `adr`, `hs_pct`, `leetify_rating`, `played_at`).
- `spreadsheet_imports` & `spreadsheet_import_rows`: Google Sheet / CSV / XLSX import provenance, `content_hash`, column mapping, sync timestamps, and per-row original JSON.
- `watchlist_entries` & `trust_signals`: separated evidence classes (`OFFICIAL_ENFORCEMENT`, `THIRD_PARTY_REPUTATION`, `BEHAVIORAL_ANOMALY`, `COMMUNITY_REPORT`, `HUMAN_REVIEW`).
- `activity_events`: deduplicated in-app community notifications.
- `users` & `user_sessions`: PBKDF2-HMAC-SHA256 hashed credentials and SHA-256 hashed session tokens.
- Planned/deferred auth tables: `auth_identities`, `community_memberships`.

## Match-room model
- `match_rooms`: room status, host, community, version.
- `match_room_players`: selected ten and optional lock.
- `team_generations`: immutable proposals, parent generation, seed, algorithm version, objective and explanation.
- `generated_team_players`: assignments.
- `generation_feedback`: approval, objection and swap request.
- `team_constraints`: locks, together pairs, opponent pairs.
- `finalized_lineups`: immutable final team snapshot.

## Statistics model
Use typed columns for frequently queried normalized metrics and JSONB for provider-specific raw data.
Each observation must record:
- provider;
- provider player ID;
- game/mode;
- season;
- period/window;
- map (for historical map stats only);
- sample count;
- metric values and units;
- captured timestamp;
- source URL or match identifier where allowed;
- freshness state;
- normalizer version.

Never overwrite historical observations. Use snapshots and derived latest-value views.

## Map data
No map selection in the match room. Store map-specific historical player statistics as input features. Maintain a versioned active map pool and internal weights. The team objective should minimize expected team-strength gap across the pool and optionally penalize worst-case imbalance. Do not return a selected map.

## Integrity model
- `ban_snapshots`: timestamped provider responses.
- `ban_events`: detected changes between snapshots.
- `watch_subscriptions`: communities/users watching a player.
- `third_party_reputation_snapshots`: attributed external service responses.
- `integrity_assessments`: structured signals with confidence and limitations.
- `review_cases`, `review_evidence`, `review_votes`, `appeals`.
- `audit_events`: immutable decision history.

Keep official platform enforcement separate from third-party reputation and community allegations.

## External source registry

| Source | Data/use | Integration status | Important caveat |
|---|---|---|---|
| Steam Web API `GetPlayerSummaries` | SteamID profile name/avatar/profile visibility | Core planned integration | Public fields only; privacy may hide data |
| Steam Web API `GetPlayerBans` | VAC/game/community/economy ban fields and available ban details | Core planned integration | A game-ban count is not automatically a CS2 cheat conviction; inspect app context and Steam policy |
| Steam OpenID | Verify linked Steam identity | Core planned integration | Authentication only; does not grant private stats |
| FACEIT Data API | Player lookup, ELO/level, matches, stats, bans | Planned adapter | API key, public data permissions, rate limits; do not infer unavailable fields |
| Leetify Public CS API | Profile, ranks/ratings, recent matches, match detail, platform ban info where returned | Planned adapter | API key available through developer portal; privacy-aligned API; follow attribution/developer guidelines |
| Premier data providers | Premier rating/history when lawfully exposed | Provider evaluation | No dependable supported public Valve Premier history/rating endpoint assumed |
| CS2 GSI | Local user's live match state for future matches | Later optional companion | Opt-in local capture only; does not backfill other players' history |
| CSWatch public API | Third-party reputation/conviction and public profile signal | Optional, attributed adapter after review | CSWatch states API is public, fair use 30 player requests/min/IP, attribution required; reputation is not Valve enforcement |
| CS2SUS website | Reference for demo-derived aim/stat anomaly methodology | Research/reference only | No public API confirmed in reviewed docs; do not scrape or reuse verdict without permission |
| Cheatscanner.eu | Reference for demo evidence and suspicious-behaviour methodology | Research/reference only | No public API/redistribution permission confirmed; use only user-supplied demos or authorized access |
| CS2Track | Reference for watchlist and ban-change workflow | Research/reference only | No authorized API contract confirmed; do not scrape |
| VACWatch | Reference for ban monitoring concepts | Research/reference only | Verify API and terms before integration |
| CS.Ninja | Reference for multi-signal trust presentation | Research/reference only | Do not treat trust score as Valve Trust Factor |
| Awpy | Parse CS2 demos and extract events/stats/visibility/nav data | Candidate open-source dependency | MIT license per repository; pin version and retain notices; verify demo/map asset licensing |
| demoparser2 | Alternative CS2 demo parser | Candidate open-source dependency | Review repository license/version before adoption; use only needed functionality |
| GitHub | Source code, issue/PR tracking, CI | Development tool | Connect only if needed; no runtime dependency |

## Data retention
- Provider snapshots: retain according to provider terms and product need; configurable retention.
- Ban history: preserve observation timestamps and source; support correction/deletion requests where required.
- Community reports: private by default; retention and appeal policy required before public launch.
- Demo files: default private, limited retention, user-controlled deletion; store parsed aggregates separately where permitted.
- Secrets: never store in this data model.
