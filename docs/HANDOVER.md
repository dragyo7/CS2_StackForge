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

## Current implemented state (MVP + Player Intelligence V2, Individual Refresh & Auto Freshness)
Implemented and tested in `backend/` and `frontend/`:
1. **Backwards-compatible SQLite schema & migrations** (`backend/app/migrations.py`): additive columns for `faceit_level`, `aim_rating`, `utility_rating`, `positioning_rating`, `preaim`, `reaction_time_ms`, `spotted_accuracy`, `spray_accuracy`, `enemies_flashed_per_round`, `traded_deaths_pct`, plus `is_archived`. Legacy `manual_rating` column preserved safely but excluded from matchmaking (`norm_v2`).
2. **Community Google Sheet / CSV / XLSX Import & Sync**: preview, column mapping, duplicate/conflict detection, safe re-import preserving edits, and `Sync Now` (`backend/app/services/import_service.py`).
3. **Universal Identity Resolution & Alias History**: resolves SteamID64, Steam `/profiles/` & `/id/`, CSStats, Leetify, CSWatch, FACEIT, and nickname candidates with `VERIFIED`/`CANDIDATE`/`UNRESOLVED` confidence and append-only alias tracking.
4. **Live Keyless CS2 Data (`Leetify v3`, `Steam ?xml=1`, `CSWatch`) + Keyed Adapters (`Steam Bans`, `FACEIT v4`)**: extracts real Premier CSR, Leetify Rating, FACEIT ELO/Level, Aim/Utility/Positioning ratings, Pre-aim, Time-to-Damage (`reaction_time_ms`), spotted/spray accuracy, recent 10 & lifetime snapshots, and match history (`Unavailable` where genuinely absent — e.g. `kast` on Leetify v3).
5. **Individual Player Refresh & Single-Instance Freshness Scheduler** (`refresh_coordinator.py`, `scheduler.py`): refreshes a single player from Registry (Cards/Standings), Player Profile (with optional provider slice), or Match Room (Roster/Picker); returns explicit `SUCCESS`/`PARTIAL`/`PRIVATE`/`NOT_LINKED`/`NOT_CONFIGURED`/`RATE_LIMITED`/`UNAVAILABLE`/`FAILED`; enforces single-flight dedup, per-provider TTLs, rate limits, `Retry-After`/exponential backoff, and 24h/startup/login stale refreshes.
6. **10-player Match Room, Community Standings & CS2-Native Explanations** (`norm_v2`, `stackforge_126_v2`): excludes manual ratings entirely, separates scales, calibrates aim/utility/damage/entry/trading/clutch/consistency + recent/lifetime priority cleanly, splits `INSUFFICIENT_DATA` players evenly, ranks players by competitive strength (`GET /api/players/rankings`), shows compact safety badges, and explains matchups like a CS2 captain without formula leakage.
7. **Trust Watch & Tactical UI**: separated `OFFICIAL_ENFORCEMENT`, `THIRD_PARTY_REPUTATION`, `COMMUNITY_REPORT`, `HUMAN_REVIEW`, private watchlist review/dismiss, `Standings Table` & `Card View` toggle, and Discord export.

**Current live status & planned/deferred items:**
- **Active live without keys:** Steam Community XML (`?xml=1`), Leetify Public CS API v3 (`429` retry/backoff), CSWatch Public JSON API (25/min cap), and Google Sheets CSV export (live-verified across persistent community DB).
- **Pending API keys (`NOT_CONFIGURED`):** `STEAM_API_KEY` (official `GetPlayerBans` enforcement checks) and `FACEIT_API_KEY` (FACEIT Data API v4 stats/ELO).
- **Not implemented / prohibited scraping:** No scrapers or adapters exist for `csstats.gg` (link & SteamID64 extraction only), `tracker.gg`, `faceitanalyser.com`, or `trustfactor.gg`.
- **Planned next:** Multi-community isolation/RBAC UI, Steam OpenID login, automated official ban monitoring once `STEAM_API_KEY` is configured, and optional offline `.dem` replay ingestion (`awpy`/`demoparser2`).

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
- `AUDIT_AND_ROADMAP.md`: verified end-to-end provider/metric audit (Part B), open-source CS2 ecosystem research (`cs-demo-manager`, `awpy`, `demoparser2`, `CSManager`, Leetify API v3), and prioritized product roadmap.
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
