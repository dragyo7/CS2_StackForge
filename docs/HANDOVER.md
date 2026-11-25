# StackForge Handover

## One-sentence definition
StackForge helps a community select ten CS2 players, assess available player data and integrity signals, generate explainable balanced 5v5 teams, negotiate remakes, and finalize a shareable lineup.

## Non-negotiable product clarification
- The match is a private 5v5 / Premier-like private match workflow, not a Valve Premier queue automation tool.
- Maps are random. Do not ask the host to select a map. Use map-specific performance privately as a robustness input across the configured active map pool.
- The primary screen is the 10-player match room.
- Team output must include explanation, alternatives, objections, swaps, locks, regeneration and restoration.
- New players must be quickly resolved and preflight-checked without blocking the lobby on provider failures.
- Trust data is evidence and status, not an automatic guilt verdict.

## Current implemented state (MVP + Intelligence, Spreadsheet Sync & Trust Evolution)
Implemented and tested in `backend/` and `frontend/`:
1. **Backwards-compatible SQLite schema & migrations** (`backend/app/migrations.py`): `communities`, `users`, `user_sessions`, `players`, `player_aliases`, `player_external_identities`, `player_stat_snapshots`, `player_match_records`, `spreadsheet_imports`, `spreadsheet_import_rows`, `watchlist_entries`, `trust_signals`, `activity_events`, `community_players`, `provider_snapshots`, `match_rooms`, `match_room_players`, `team_constraints`, `team_generations`, `generation_feedback`, `finalized_lineups`, `audit_events`.
2. **Community Google Sheet / CSV / XLSX Import & Sync**: preview, column mapping, duplicate/conflict detection, safe re-import preserving manual edits, and `Sync Now` (`backend/app/services/import_service.py`).
3. **Universal Identity Resolution & Alias History**: resolves SteamID64, Steam `/profiles/` & `/id/`, CSStats, Leetify, CSWatch, FACEIT, and nickname candidates with `VERIFIED`/`CANDIDATE`/`UNRESOLVED` confidence, cross-provider discovery, and append-only alias tracking.
4. **Live Keyless CS2 Data (`Leetify v3` & `CSWatch`) + Keyed Adapters (`Steam`, `FACEIT`)**: extracts real Premier/Leetify/FACEIT ELO ratings, recent 10 & lifetime combat metrics, match history, avatars, and hidden map deltas without scraping.
5. **Trust & Account Watch**: separated `OFFICIAL_ENFORCEMENT`, `THIRD_PARTY_REPUTATION`, `COMMUNITY_REPORT`, and `HUMAN_REVIEW` signals, private watchlist review/dismiss, and deduplicated activity feed.
6. **10-player Match Room & CS2-Native Explanations**: 126-partition deterministic optimizer with shared Registry/Optimizer normalization (`build_player_input`), explicit `recent` (recent form/ADR) and `lifetime` (opening duels/trading/clutch/consistency) snapshot priority, CS2-native matchup notes, alternatives, swaps, locks, regeneration, restoration, finalize, and Discord share.
7. **Pre-Match Refresh & Roster Safety Warnings**: Match Room `Refresh Status` delegates to `refresh_player_profile` (Steam, Leetify profile/stats/matches, CSWatch, FACEIT when keyed, TTL cache + 429 retry + cached preservation), renders a per-player/per-provider report, and displays compact informational warnings (`CSWatch`, `Watchlist`, `Unverified ID`, `Stale Stats`, provider unavailable) without altering skill ratings.
8. **Auth Foundation & Tactical UI**: Landing/Sign-Up/Login/Logout (`PBKDF2-HMAC-SHA256`), `Dashboard`, `Match Room`, `Players` (with Sheet Import & Universal Resolver), `Player Stats` (Profile, Match History & Compare), `Player Cards`, and `Trust Watch`.

**Current live status & planned/deferred items:**
- **Active live without keys:** Steam Community XML (`?xml=1`), Leetify Public CS API v3 (`429` retry/backoff), CSWatch Public JSON API (25/min cap), and Google Sheets CSV export (`14` unique players verified in `backend/stackforge.db`).
- **Pending API keys (`NOT_CONFIGURED`):** `STEAM_API_KEY` (official `GetPlayerBans` enforcement checks) and `FACEIT_API_KEY` (FACEIT Data API v4 stats/ELO).
- **Not implemented / prohibited scraping:** No scrapers or adapters exist for `csstats.gg` (link & SteamID64 extraction only), `tracker.gg`, `faceitanalyser.com`, or `trustfactor.gg`.
- **Planned next:** Multi-community isolation/RBAC UI, Steam OpenID login, automated background Trust Watch check scheduling with keys enabled, and optional offline `.dem` replay ingestion (`awpy`/`demoparser2`).

## Source-of-truth docs
- `../Userflow.md`: user journeys.
- `../Rules.md`: binding product and engineering rules.
- `DECISIONS.md`: accepted architecture/product decisions.
- `ALTERNATIVES.md`: considered options and rejected approaches.
- `ARCHITECTURE.md`: system boundaries and flows.
- `CONSTRAINTS.md`: hard limits and assumptions.
- `THREAT.md`: threat model.
- `FAILURE.md`: failure modes and recovery.
- `DATA.md`: data model, provenance and external source registry.
- `TESTING.md`: acceptance and test strategy.
- `ROLLBACK.md`: rollback/migration/release plan.
- `INTEGRATIONS.md`: external services, usage, access status and licensing checklist.
- `features/`: feature specifications.
- `bugs/`: known issues and triage template.
- `defense/`: integrity/anti-cheat methodology and review policy.

## Agent start protocol
1. Inspect repository tree, git status and existing tests.
2. Read root `Rules.md` and this handover.
3. Identify current milestone and actual implemented state. Do not trust stale docs over code/tests.
4. Make a concise plan limited to the next vertical slice.
5. Implement with tests.
6. Run lint/typecheck/tests/migrations as relevant.
7. Update docs and report exact changed files, commands and results.

## Do not do
- Do not build a map picker.
- Do not claim an official Valve Premier rating API exists.
- Do not scrape sites as a substitute for an authorized API.
- Do not call all Steam game bans CS2 cheat bans without app/game context.
- Do not generate fake win probabilities.
- Do not start with microservices, Kubernetes, Kafka or ML infrastructure.
- Do not build a generic dashboard before the match-room flow works.

## Definition of MVP done
A host can import/reuse ten unique players, run a non-blocking preflight, generate and understand teams, show alternatives, accept objections, swap/lock/regenerate, restore an old generation, finalize and copy the lineup. Community isolation and auditability must pass tests.
