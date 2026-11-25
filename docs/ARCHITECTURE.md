# Architecture

## 1. Overview

Use a modular monolith:

- React + TypeScript + Vite frontend.
- FastAPI backend.
- PostgreSQL.
- Background worker for provider refresh, Watchtower polling and demo parsing.
- Redis only when needed for queue/cache/coordination.
- Object storage for demos when demo uploads ship.

Do not split services until measurable scaling or operational ownership requires it.

## 2. Logical modules (Current Implementation + Planned)

- `players` + `player_aliases`: global SteamID64 canonical identity, vanity tracking, refresh status/TTL metadata, append-only alias history, and community-scoped profiles (`community_players`).
- `stats` (`player_stat_snapshots` + `optimizer/normalizer.py`): source-qualified, timestamped competitive and combat stat snapshots, separate cohort normalizer (`norm_v1`), and freshness tracking.
- `providers`: Steam (`GetPlayerSummaries`, `GetPlayerBans`, `ResolveVanityURL`), FACEIT Data API v4 (player + `/stats/cs2`), and Leetify Public CS API (`/v3/profile`) adapters with non-blocking failure isolation.
- `humour_engine` (`card_rules_v1`): deterministic, sample-gated CS2 player-card title, badge, and roast generator backed strictly by verified stat snapshots.
- `match_rooms` & `proposals`: room state, 10-slot roster, locks/pair constraints, immutable proposal history, swap preview/commit, objections, and finalized Discord/shareable lineups.
- `matchmaking` (`optimizer/engine.py`): exhaustive 126-partition deterministic 5v5 optimizer with hidden active map-pool robustness (`active_duty_v1`).
- Frontend (`frontend/src/`): React + TypeScript + Vite CS2 tactical UI with **Dashboard**, **Match Room**, **Players**, **Player Stats** (Profile & PvP Compare), **Player Cards**, and **Shared Lineup** views.
- Deferred modules: `auth` (Steam OpenID), `watchtower` scheduler, `ratings` (community Elo), `chemistry`, `availability`, `demos` (Awpy), `discord` bot.

## 3. Data flow

### Player import
Client -> import API -> URL/SteamID parser -> global player lookup -> Steam profile resolver -> global player upsert -> community membership upsert -> async provider refresh.

### Preflight
Room -> gather ten player IDs -> provider cache lookup -> batch Steam ban request where supported -> FACEIT/Leetify adapters -> community case lookup -> source status aggregation -> return non-blocking report.

### Team generation
Room roster + immutable stats snapshot + constraints -> normalization -> player strength distributions -> map-pool robustness features -> enumerate 126 partitions -> reject hard-constraint violations -> calculate objective -> select recommended + diverse alternatives -> persist proposal and explanation.

### Remake
Current proposal + feedback/locks/swaps -> new constraints -> regenerate -> create child proposal. Previous proposal remains unchanged.

### Monitoring
Scheduled worker -> due watchlist accounts -> provider calls with rate limiting -> append snapshot -> compare prior state -> create event on meaningful change -> notify subscribed admins.

### Demo analysis (later)
Upload -> quarantine/object storage -> validation -> isolated worker -> Awpy/demoparser2 -> normalized events -> evidence indicators -> human review. Do not call parser in request thread.

## 4. Matchmaking model

For each player `i`, build a normalized feature vector with:
- Premier rating percentile/standard score (season and source-qualified).
- FACEIT ELO/level percentile.
- Leetify rating and component percentiles.
- recent-form features.
- impact features: ADR, KAST, opening duel, trade, utility/flash contribution.
- role preferences/strengths.
- community rating.
- map-specific features across the active pool.

Each feature has sample size, freshness and confidence. Missing values are omitted and weights renormalized with an explicit confidence reduction.

Do not compare raw source scales. Do not use uncalibrated win probability.

For map-agnostic balancing:
- Define versioned active map pool and weights.
- If no empirical map frequency exists, start with equal weights.
- For each candidate split calculate expected strength difference across maps.
- Add a robustness penalty for worst-map imbalance or variance across maps.
- Do not choose, reveal or recommend a map.

For ten players, enumerate all 126 unique unordered partitions. Use deterministic tie-breaking with seed. Respect together/opponent/team-lock constraints. If no valid partition remains, return `CONSTRAINTS_UNSATISFIABLE` with a human-readable explanation.

Store:
- input player/stat snapshot IDs;
- normalization model version;
- map-pool version/weights (internal metadata);
- objective component values;
- hard constraints;
- random seed;
- algorithm version;
- alternative ranking and diversity.

## 5. Team explanation

Return structured facts:
- aggregate normalized skill difference;
- Premier/FACEIT/Leetify coverage;
- recent form difference;
- role coverage;
- map-pool expected and worst-case balance (internal map names need not be displayed);
- confidence and missing data;
- constraints honoured;
- objective breakdown.

Frontend explanation is rendered from these fields. LLM paraphrase is optional and cannot add facts.

## 6. Multi-tenancy

Global tables: `users`, `players`, `external_identities`, provider snapshots where appropriate.
Tenant tables: `communities`, `memberships`, `community_players`, lobbies, proposals, matches, reports, ratings.
Every tenant-owned record must have `community_id` or be reachable through a composite FK to a tenant-owned parent.
Use PostgreSQL constraints and optionally row-level security as defence in depth.
Never use client-supplied community ID as authorization proof.

## 7. Integration boundaries

Each provider adapter returns normalized internal objects plus raw provider payload reference:
- `resolve_identity`
- `fetch_profile`
- `fetch_competitive_stats`
- `fetch_recent_matches`
- `fetch_bans` (only if provider offers it and usage is permitted)

Provider failures are isolated. Cache by provider identity and response freshness. Use circuit breakers/backoff for repeated failure. No frontend direct provider API calls.

## 8. Deployment

Local: Docker Compose for PostgreSQL and backend; frontend Vite dev server.
Production: managed PostgreSQL, container backend, static frontend, managed object storage for demos, background worker.
Secrets only in server environment/secret manager.
Use structured logs, metrics and error reporting without logging API keys, session tokens or sensitive raw evidence.
