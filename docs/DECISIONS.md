# Architecture Decision Records

## D-001 — Product focus
**Decision:** StackForge is a private CS2 10-player match organizer and team-balancing assistant.  
**Reason:** The main pain is selecting ten people and forming fair 5v5 teams quickly.  
**Consequence:** Match room is the primary UX; public community discovery is secondary.

## D-002 — Maps remain random
**Decision:** No map picker, map veto or map recommendation in the generation flow. Map-specific performance is a hidden optimizer input used to balance teams robustly across the active map pool.  
**Reason:** The actual match map is random and must not be chosen by StackForge.  
**Consequence:** Optimizer uses a map-pool prior or expected/worst-case map robustness. Store pool version and weights internally. Do not display a selected map.

## D-003 — Modular monolith
**Decision:** One FastAPI application, one PostgreSQL database, modular internal boundaries.  
**Reason:** Fast delivery and simpler operations for an early product.  
**Rejected:** Microservices, Kafka and Kubernetes at MVP.

## D-004 — Global player identity, community-scoped membership
**Decision:** Global `players` keyed by SteamID64; separate `community_players` for nickname, roles, ratings, match history and community moderation.  
**Reason:** Same Steam identity may participate in multiple communities without leaking community data.

## D-005 — Provider adapters
**Decision:** Steam, FACEIT, Leetify and other services integrate behind normalized provider interfaces.  
**Reason:** External APIs change, rate-limit and fail. Core product must remain functional.

## D-006 — Premier data is source-qualified
**Decision:** No assumption of a supported public Valve endpoint for comprehensive Premier rating/history. Prefer authorized provider data (e.g. Leetify where exposed), approved tracker APIs, and optional local GSI capture for future matches on the opted-in user's machine.  
**Reason:** Valve's public Web API does not provide a dependable general Premier history feed in the sources reviewed; community tracker evidence documents the gap.  
**Consequence:** Store source, capture time, season, coverage and freshness. Do not invent missing values.

## D-007 — Stats normalization
**Decision:** Normalize Premier rating, FACEIT ELO, Leetify metrics and demo metrics separately.  
**Reason:** They have different scales, cohorts and meanings.  
**Consequence:** Keep normalizer version, cohort and confidence. Missing stats are unknown, not zero.

## D-008 — Exhaustive 5v5 optimization
**Decision:** For exactly ten players, evaluate 126 unique unordered 5v5 partitions.  
**Reason:** Small, exact search space; no ML or heuristic optimizer needed for MVP.  
**Consequence:** Deterministic objective and hard-constraint validation.

## D-009 — Map-robust objective
**Decision:** With map unknown, optimize expected team balance across configured active map pool and optionally penalize worst-map imbalance.  
**Reason:** Teams should not be lopsided if a random map is selected.  
**Consequence:** Do not choose or reveal a map. Use shrinkage for low map sample sizes.

## D-010 — Trust is not a single cheat score
**Decision:** Keep official enforcement, third-party reputation, behavioural anomalies and community reports as separate evidence classes.  
**Reason:** No public signal proves all cheating; Steam game-ban reasons are broader than cheating.  
**Consequence:** No automatic conviction from stats, age, playtime or accusations.

## D-011 — Ban history is append-only
**Decision:** Store timestamped ban snapshots and derived change events.  
**Reason:** Watchtower needs to detect new changes and explain what changed.  
**Consequence:** Never overwrite previous observations.

## D-012 — Proposal-based team generation
**Decision:** Every generation is an immutable proposal; objections/remakes create new proposals.  
**Reason:** Players may disagree; history and reversibility matter.  
**Consequence:** Store seed, algorithm version, inputs, constraints, explanation and parent generation.

## D-013 — No fabricated win probability
**Decision:** Show balance difference and confidence first. Show win probability only after calibration against sufficient held-out community results.  
**Reason:** A balanced score is not a probability.  
**Consequence:** No 50/50 badge by default.

## D-014 — Async enrichment
**Decision:** External stats, monitoring and demo parsing run asynchronously with cache.  
**Reason:** Provider downtime must not block player selection or team generation.

## D-015 — Discord and desktop companion are later
**Decision:** Web-first MVP; Discord bot and optional local GSI companion after core flow.  
**Reason:** Avoid scope explosion. GSI only observes opted-in local gameplay and cannot backfill other players' history.
