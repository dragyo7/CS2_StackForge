# StackForge — Product, Data and Engineering Rules

These rules are binding for contributors and coding agents. If code conflicts with this file, stop and raise a decision rather than silently changing product behaviour.

## Product rules

1. StackForge organizes an existing ten-player CS2 group into a private 5v5 match. It is not a ranked queue and does not claim to control Valve matchmaking.
2. Ten unique player identities are required for a standard generation.
3. Player identity is global; player membership, nickname, roles, ratings, reports and history are community-scoped.
4. Maps are random during the real match flow. **Never add a map picker, map veto or map-selection step to the team-generation UX.**
5. Map-specific performance may be used privately as a robustness input across the active map pool. It must not select, predict, announce or constrain the match map.
6. A generation is a proposal. The host finalizes it.
7. Every generation, swap, lock, objection, restore and finalization is versioned and auditable.
8. Regeneration must produce a different valid split when possible. Do not claim a new result if it is identical.
9. Users can object, suggest swaps, lock players, regenerate, restore alternatives and request a full remake.
10. External provider outages must not prevent saved-player selection or team generation if usable cached/manual ratings exist.
11. Never fabricate Premier ratings, API availability, bans, trust scores, win probabilities or match history.
12. No AI-generated explanation may contain a reason not present in structured optimizer evidence.

## Player identity and import rules

1. SteamID64 is stored as a string, never a JavaScript number, and is the canonical global player identity.
2. Normalize supported Steam profile URL forms to SteamID64 when possible; vanity `/id/` URLs are mutable and must resolve via authorized Steam API before linking.
3. Never infer identity from display name alone; two accounts sharing a display name remain separate players.
4. Deduplicate global players by SteamID64; deduplicate provider identities by `(provider, external_id)`.
5. Treat Steam display names as mutable metadata: preserve historical aliases in append-only `player_aliases` (preventing consecutive duplicates) and keep community nicknames separate from Steam display names.
6. Import is idempotent and returns per-entry status.
7. Profile privacy means unavailable data, not suspicious behaviour.
8. Steam OpenID verifies identity only; it does not reveal private data or provide all game statistics.
9. Never ask for or store a Steam password.
10. Profile refreshes must respect cache TTLs and retain last-known valid profile data during provider outages.

## Player Card and Humour rules

1. Humour titles, badges, and roasts must be deterministically derived from actual recorded statistics and minimum sample thresholds (`>= 5` matches for style/positive titles, `>= 8–10` for negative roasts).
2. Missing statistics are unknown and must never trigger a negative title or roast.
3. Humour themes are strictly limited to in-game CS2 banter (saving, utility, entries, clutches, whiffs) and must never include harassment, personal insults, or unverified cheating accusations.
4. Players/hosts must be able to toggle humour on/off, adjust intensity, hide individual badges, and regenerate taglines from the same verified evidence.

## Statistics and balancing rules

1. Every metric must carry provider, game/mode, period/season, sample size, captured time, source identifier and freshness.
2. Never compare raw Premier rating, FACEIT ELO and Leetify rating as if they share a scale.
3. Normalize metrics separately against a documented cohort/distribution. Store normalizer version.
4. Prefer recent and season-relevant stats but retain lifetime context.
5. A missing metric is unknown, not zero and not a penalty.
6. Reweight available dimensions with a confidence penalty; disclose reduced confidence.
7. Use sample-size shrinkage for small samples, especially map and player-pair statistics.
8. Do not overfit to K/D. Include impact, ADR, KAST, opening duels, utility/trading and role fit when reliable.
9. Community Elo is separate from Premier and FACEIT ratings.
10. Do not claim predicted win percentages until calibrated and validated against held-out community match outcomes.
11. Team optimizer must be deterministic for a fixed input snapshot, constraints, algorithm version and seed.
12. For ten players, evaluate all 126 unique 5v5 partitions; ensure no mirrored duplicate partition.
13. Respect hard constraints or return a clear unsatisfiable-constraints error.
14. Optimize expected balance across the active map pool using configured weights or a robust worst-case term. Map choice remains unknown and hidden.
15. Save objective components, input snapshot, seed, algorithm version and explanation for every generation.

## Trust and anti-cheat rules

1. Separate **official enforcement**, **third-party reputation**, **behavioural anomaly**, and **community allegation**. Never merge them into one unqualified "cheater" label.
2. Steam VAC/game-ban fields are not automatically proof of a CS2 cheat. Use available app/game context; if context is absent, say so.
3. Steam's CS2 game-ban FAQ states game bans may be issued for cheating, matchmaking rank manipulation, botting/automation, or interference with game systems. The API ban count alone may not reveal the reason.
4. A VAC/game ban is an enforcement record, not a complete account of what happened. Display provider, exact fields, observation time and available game context.
5. No ban found means only "no ban record found by this source at this time", never "clean".
6. Private/hidden profile, young account, low hours, high rank, unusual aim stats or community reports are not proof of cheating.
7. Statistical anomalies trigger review, not conviction.
8. Demo-based indicators must include match/demo reference, round/tick/time, signal, baseline and limitations.
9. Human review decisions require evidence, reviewer identity, rationale and appeal path.
10. Never scrape or automate access to third-party sites where terms do not permit it.
11. Never use leaked cheat lists, doxxing, account compromise, invasive client inspection or unauthorized process scanning.
12. Never claim to detect all cheats, DMA hardware cheats, or hidden Valve Trust Factor.
13. Do not automatically exclude a player based solely on unverified suspicion. Community policy and host make the decision with transparent evidence.

## Map rules

1. No map choice in lobby creation or team generation.
2. No map veto.
3. Map-specific player stats are hidden optimizer inputs only.
4. Use the configured active map pool as a prior; document pool version and weighting.
5. If map distribution is unknown, use equal weights or a robust expected/worst-case objective and disclose that assumption in technical metadata, not as a user map choice.
6. Do not show a generated map recommendation.

## Security and privacy rules

1. Enforce community isolation on every query and mutation.
2. Use secure server-side secrets; never expose provider API keys in frontend code.
3. Use HTTPS, secure HTTP-only sessions, CSRF protection where cookie auth is used, rate limiting and audit logs.
4. Apply least-privilege roles.
5. Keep evidence access private to authorized reviewers/community members.
6. Define retention and deletion policy for demos, reports and personal data.
7. Store only data necessary for product function; honor provider terms and privacy settings.
8. Use signed, expiring invitation and guest-response tokens.
9. Validate file type, size and content before demo processing; parse in isolated workers.
10. Do not trust client-supplied team assignments, scores, provider statuses or permissions.

## Coding-agent rules

1. Read `HANDOVER.md`, `DECISIONS.md`, `RULES.md` (repository root), `ARCHITECTURE.md`, `CONSTRAINTS.md` and relevant feature docs before editing.
2. Inspect the existing repository before creating or replacing files.
3. Do not scaffold duplicate modules or rewrite working code.
4. Implement one vertical slice at a time.
5. Write tests before or alongside logic; run targeted tests and the full relevant suite.
6. Update docs when contracts, schema, dependencies or decisions change.
7. Do not add a dependency without stating why, license, maintenance status and alternative.
8. No placeholders that look implemented. Mark deferred features explicitly.
9. Keep migrations reversible where practical; never drop/rename data without a backup and rollback plan.
10. Report changed files, tests run, known gaps and next exact action.
