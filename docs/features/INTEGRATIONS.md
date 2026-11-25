# Feature: Provider Integration Adapters

## Interface
Each adapter should expose normalized methods where supported:
- `resolve_player(identifier)`
- `fetch_profile(provider_player_id)`
- `fetch_competitive_ratings(provider_player_id)`
- `fetch_recent_matches(provider_player_id, period)`
- `fetch_match_details(match_id)`
- `fetch_enforcement(provider_player_id)`

Not every provider implements every method. Return `NOT_SUPPORTED`, `NOT_FOUND`, `PRIVATE`, `RATE_LIMITED`, `UNAVAILABLE`, or `OK` explicitly.

## Normalized observation
`provider`, `provider_player_id`, `game`, `mode`, `season`, `period`, `map`, `sample_count`, `metrics`, `captured_at`, `source_ref`, `freshness`, `normalizer_version`.

## Provider isolation
- server-side calls only;
- bounded timeouts;
- cache and rate limits;
- exponential backoff;
- circuit breaker;
- raw response stored only when terms/privacy allow;
- schema contract tests;
- provider outage cannot block room/generation.

## Premier
No supported Valve Premier history endpoint is assumed. Prefer Leetify fields where exposed, approved third-party APIs, or optional local GSI capture for future local matches. Label source and coverage.
