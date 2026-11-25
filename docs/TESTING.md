# Testing Strategy and Acceptance Criteria

## Unit & Identity tests (Implemented in `backend/tests/`)
- SteamID64 parser and profile URL resolver (`test_api_workflow.py`).
- Identity deduplication and identical display names across distinct SteamID64s (`test_identity_and_cards.py`).
- Steam username change updates same `Player` row, records append-only `PlayerAlias`, and remains searchable by previous name (`test_identity_and_cards.py`).
- Profile refresh TTL cache hit and retention of last valid profile/avatar on Steam outage (`test_identity_and_cards.py`).
- Backwards-compatible SQLite migration (`run_migrations`) preserving legacy rows (`test_identity_and_cards.py`).
- Provider adapters fail-safe `NOT_CONFIGURED` checks (`test_providers.py`).
- Metric normalization, missing-metric unknown handling, 126 unique partitions, deterministic seed, constraint validation, and regeneration exhaustion (`test_optimizer.py`).
- Evidence-based CS2 player card rules, sample thresholds, missing-stats safety, badge hiding, and tagline rerolling (`test_identity_and_cards.py`).
- Full match room lifecycle -> generate -> swap -> lock/regenerate -> objection -> restore -> finalize -> share (`test_api_workflow.py`).

## Integration tests
- Import mixed Steam URLs and IDs.
- Same player in two communities without profile leakage.
- Provider outage does not block room/generation.
- Batch Steam ban lookup.
- FACEIT/Leetify adapter mock contracts.
- Create room -> add ten -> preflight -> generate -> object -> swap -> regenerate -> restore -> finalize.
- Host/admin/member authorization.
- Concurrent generation/finalization.
- Worker retry and idempotency.
- Migration up/down on a clean test database.

## Matchmaking fixtures
1. Ten equal players.
2. One high and one low rating.
3. Missing Premier for half the roster.
4. FACEIT-only players.
5. Recent form conflicts with lifetime rating.
6. Role-heavy roster (many AWPers, no support).
7. Map performance differs sharply by map.
8. Unknown random map distribution.
9. Together and opponent constraints.
10. Locked players.
11. Constraints impossible.
12. Alternative generation exhaustion.
13. Fixed seed reproducibility.
14. Provider metrics stale.
15. One player's source data changes after a generation; old proposal remains reproducible.

## Trust fixtures
- no bans found;
- VAC ban found;
- game ban found with app context;
- game ban found without app context;
- community ban only;
- economy ban only;
- provider unavailable;
- old snapshot changed to new ban;
- third-party low-risk/high-risk label;
- unreviewed community report;
- human-reviewed evidence;
- appeal accepted/rejected;
- private profile and missing playtime.

## Security tests
- IDOR across community IDs.
- member cannot administer watchlist.
- report evidence inaccessible to unrelated community.
- invite token expiry/replay.
- CSRF/session protections.
- rate limits.
- provider key absent from frontend build.
- malicious/oversized demo upload rejection.
- SQL injection and input validation.
- log redaction.

## Performance targets
- Player search p95 < 200ms at MVP target load.
- Optimizer p95 < 1 second for ten players after input fetch.
- No external provider network call inside optimizer.
- Ten-player batch preflight uses bounded provider calls and caching.
- Benchmark realistic data volumes before production claims.

## Acceptance test: primary user story
Given a community with saved players and two new Steam IDs:
1. Host creates room.
2. Adds eight saved players.
3. Pastes two new IDs.
4. System resolves identities and returns per-source status.
5. Host has exactly ten players.
6. Preflight completes or shows pending/unavailable providers.
7. Host generates teams.
8. System returns recommended split, alternatives and explanation.
9. Player requests a swap.
10. Host evaluates swap delta and regenerates with a lock.
11. Host restores earlier alternative if desired.
12. Host finalizes.
13. Finalized line-up can be copied/shared.
14. No map was selected or displayed during this flow.
