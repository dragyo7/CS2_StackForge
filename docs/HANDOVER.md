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

## Current implemented state (MVP + Player Intelligence & CS2 Redesign)
Implemented and tested in `backend/` and `frontend/`:
1. **Backwards-compatible SQLite schema & migrations** (`backend/app/migrations.py`): `communities`, `players`, `player_aliases`, `player_stat_snapshots`, `community_players`, `provider_snapshots`, `match_rooms`, `match_room_players`, `team_constraints`, `team_generations`, `generation_feedback`, `finalized_lineups`, `audit_events`.
2. **Canonical SteamID64 identity & alias history**: Steam URL/ID parser, bulk import (`CREATED_STEAM`, `CREATED_MANUAL`, `DUPLICATE`, `UNRESOLVED`, `INVALID`), TTL-cached profile refresh (`POST /api/players/{id}/refresh`), append-only alias tracking, and searchable previous names.
3. **Player profile & source-qualified stats**: `GET /api/players/{id}/profile`, `POST /api/players/{id}/stats`, `GET /api/players/compare`, missing metrics displayed as `Unavailable from this source`.
4. **Evidence-based CS2 Player Cards (`card_rules_v1`)**: `PATCH /api/players/{id}/card-settings`, sample-gated humorous titles, hideable badges, intensity selector (`MILD`/`SPICY`/`SAVAGE`), tagline reroll, Discord card copy.
5. **10-player Match Room & 126-partition optimizer**: exhaustive deterministic optimization (`stackforge_126_v1` + `norm_v1` + hidden `active_duty_v1`), alternatives, swap preview/commit, locks, pair constraints, regenerate with repeat-avoidance, objections, proposal restore, finalize, and Discord/shareable lineup.
6. **CS2 tactical frontend**: **Dashboard**, **Match Room**, **Players**, **Player Stats**, **Player Cards**, and **Shared Lineup** views.

**Known limitations:** Steam/FACEIT/Leetify adapters are implemented and unit-tested for unconfigured fallback, but live API calls remain untested until API keys are configured in `backend/.env`. Multi-user authentication (Steam OpenID), multi-tenant RBAC, Watchtower background polling, and demo `.dem` parsing remain deferred.

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
