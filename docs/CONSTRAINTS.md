# Product and Technical Constraints

## Match constraints
- Standard room contains exactly ten distinct players before generation.
- Standard output is two teams of five.
- Only players in the room can be assigned.
- A player cannot appear on both teams.
- Hard locks and together/opponent constraints must be satisfied.
- A valid result must be reproducible from saved inputs, seed and algorithm version.
- Alternative proposals must be distinct when feasible.
- Team generation must not choose a map.

## Random-map constraint
The map is random outside StackForge. No map field is required for generation. Map-specific statistics are incorporated privately across the active map pool to avoid a split that is balanced only on one map. Pool and weights are versioned. No map is selected, predicted or exposed.

## Data & Identity constraints
- `SteamID64` is a string and the canonical global player identity.
- Steam display names are mutable; historical aliases are append-only without consecutive duplicates.
- Premier, FACEIT and Leetify scores are different scales.
- Premier season and source are mandatory context where available.
- Stats carry provider, scope, sample size, timestamp and freshness.
- Missing/private/unavailable is not zero (`Unavailable from this source`).
- Third-party provider terms and rate limits apply (`PROVIDER_CACHE_TTL_SECONDS` default 900s).
- No official Valve Premier rating/history API is assumed.
- Local GSI captures only the opted-in local user's future game-state events; it is not a universal match-history source.

## Player Card & Humour constraints
- Positive/style card titles require `sample_size >= 5`; negative roasts require `sample_size >= 8` or `>= 10`.
- Missing stats never trigger negative titles.
- Humour is restricted to CS2 gameplay banter; no real-world personal attacks or cheat accusations.

## Trust constraints
- Steam ban counts do not always identify a CS2-specific cheating reason.
- Steam CS2 game-ban policy includes multiple grounds beyond cheating.
- Third-party risk scores are not official enforcement.
- Community reports are allegations until reviewed.
- Behavioural anomalies require evidence and human review.
- No system can promise detection of all cheats or DMA hardware cheats.

## Performance targets
- Saved-player search p95 < 200 ms under normal MVP load.
- Ten-player team generation p95 < 1 second after data retrieval.
- Generation never waits synchronously for third-party enrichment.
- Import should be idempotent and return per-entry results.
- Provider refresh jobs must be rate-limited and retry-safe.

## Security constraints
- Tenant isolation enforced server-side and in database constraints.
- No secrets in browser bundles.
- No Steam password collection.
- Secure sessions, CSRF protection for cookie auth, rate limiting and audit logs.
- Demo parsing isolated and resource-limited.
- Evidence links private by default.
- Data retention/deletion rules documented before public launch.

## Scope constraints
MVP excludes:
- Actual Valve Premier lobby creation/control.
- Automatic map selection/veto.
- AI cheat verdicts.
- Public global blacklist/accusation board.
- Discord bot.
- Full demo analytics.
- ML win-probability prediction.
- Microservices/Kubernetes.
