# Failure Modes and Recovery

| Failure | User-visible behaviour | Recovery |
|---|---|---|
| Steam API unavailable | Steam status `UNAVAILABLE`; cached record & last persona shown with timestamp | Retry with backoff; preserve last-known valid profile; allow room to proceed |
| Vanity resolution failure | Bulk import returns `UNRESOLVED` for `/id/...` line | Prompt host to supply SteamID64 or `/profiles/...` URL; never guess identity |
| Profile refresh failure | `Refresh unavailable` warning; `refresh_status` updated | Keep last-known `steam_persona_name`, avatar, and cached stats intact |
| FACEIT key missing/invalid | FACEIT `NOT_CONFIGURED` / `UNAVAILABLE` | Continue with other sources; admin configures key |
| Leetify profile unavailable/private | `NOT_LINKED` or `NO_DATA` | Keep identity; do not penalize |
| Premier provider unavailable | Premier metric `UNKNOWN` | Use other metrics/manual baseline; lower confidence |
| Incomplete combat metrics | Metric displays `Unavailable from this source` | Never zero-fill missing values; humour rules skip missing dimensions |
| Stats stale | Show last refresh timestamp | Queue refresh; do not block generation |
| Steam profile URL malformed | Per-entry import error | Allow correction without failing whole batch |
| Duplicate SteamID | Return existing player/membership status | Idempotent upsert |
| Exactly ten players not present | Disable generation with count | Prompt to fill/replace slots |
| Constraint set impossible | Return `CONSTRAINTS_UNSATISFIABLE` and explain conflict | Let host remove/change constraints |
| All valid splits already shown | Say alternatives exhausted | Offer reset history or relax constraints |
| Optimizer timeout/bug | Preserve previous proposal | Return error ID; log structured context |
| Worker down | Show enrichment/monitoring delayed | Retry queue when worker recovers |
| Ban status changed | Create event, avoid repeated duplicate alerts | Idempotent event key and admin notification |
| Provider changes schema | Mark provider parse failure | Contract test alert; disable only adapter |
| Demo parse fails | Keep original file and failure status | Retry with compatible parser; allow manual review |
| User leaves room | Preserve room state | Host replaces player and creates new proposal |
| Two users finalize | One transaction wins | Return conflict and refresh state |
| Database migration fails | Stop deployment | Restore backup or run documented down migration |
| Object storage unavailable | Disable demo upload only | Match-room functions continue |

## Resilience rules
- External provider calls are never in the critical synchronous generation path.
- Use timeouts, bounded retries with exponential backoff and jitter.
- Do not retry non-idempotent actions without idempotency keys.
- Cache last known good values and show age.
- Circuit-break failing providers.
- Persist task state and retry safely.
- Keep finalized lineups and generation history immutable.
