# Threat Model

## Assets
- Steam identity mappings.
- User sessions and linked identities.
- Community membership and private roster.
- Player statistics and match history.
- Ban snapshots and integrity assessments.
- Community reports, demo files and reviewer decisions.
- Provider API keys and session secrets.
- Finalized team proposals.

## Threat actors
- Unauthenticated scraper/spammer.
- Malicious community member.
- Malicious or compromised community admin.
- User attempting to impersonate a Steam account.
- User attempting to poison ratings/reports.
- Malicious uploaded demo or archive.
- Compromised provider key.
- Cross-tenant data snooper.

## Main threats and mitigations

### Account impersonation & username spoofing
Threat: User imports another person's SteamID, changes their Steam display name to match a teammate, or attempts to duplicate an identity.
Mitigation: Canonical identity is `SteamID64` string (`players.steam_id64` unique constraint). Steam display names are mutable metadata tracked in `player_aliases`, and two different SteamIDs sharing a display name stay separate. Manual-only profiles are clearly badged unverified; Steam OpenID ownership verification remains deferred to auth milestone.

### Humour misuse & harassment
Threat: Player cards or roasts become abusive, target personal attributes, or imply cheat accusations.
Mitigation: Deterministic `card_rules_v1` allows only in-game CS2 banter backed by verified metric evidence and minimum sample thresholds, never assigns negative titles from missing stats, supports per-player humour disable/intensity/badge hiding, and stays community-scoped.

### Unauthorized profile visibility
Threat: Community notes or stats leak publicly or provider credentials reach the browser.
Mitigation: Provider keys remain strictly in server env (`STEAM_API_KEY`, `FACEIT_API_KEY`, `LEETIFY_API_KEY`). Profiles carry `profile_visibility` and `stats_visibility` fields; public sharing exposes only finalized match lineups (`share_slug`). Full multi-user RBAC remains deferred until StackForge auth ships.

### Cross-community leakage
Threat: Community member queries another community's reports, ratings or roster.
Mitigation: Server-side authorization on every request, composite tenant constraints, tests for IDOR, optional PostgreSQL RLS.

### False cheating accusation
Threat: A ban count, unusual stat or unreviewed report labels a player a cheater.
Mitigation: Separate evidence classes, exact source/timestamp, careful language, review workflow, appeal, audit log, no automatic conviction.

### Provider API abuse/key leakage
Threat: API key exposed or endpoint spammed.
Mitigation: Server-only secrets, per-provider rate limit, cache, quota monitoring, rotate keys, redact logs.

### Data poisoning
Threat: Users submit fake stats, results or reports to influence team generation/reputation.
Mitigation: Store source and trust level; manual values visibly labelled; only verified match results update Elo; reviewer permissions; anomaly detection on repeated reports.

### Demo upload attack
Threat: Malformed or oversized `.dem` file attacks parser/worker.
Mitigation: File-size cap, content signature check, quarantine, isolated unprivileged worker/container, CPU/memory/time limits, no shell execution, safe object storage, malware scanning where available.

### Session and invitation abuse
Threat: Session theft, CSRF, invitation guessing/replay.
Mitigation: Secure HTTP-only SameSite cookies, CSRF token, short-lived single-use signed invites, rotation and revocation.

### Match proposal race
Threat: Two hosts/actions overwrite or finalize conflicting proposals.
Mitigation: Optimistic version field, transaction, idempotency key, unique finalization guard and audit event.

### Reputation scraping and harassment
Threat: Public player reports used to harass/dox.
Mitigation: Private-by-default community reports, no public accusation feed in MVP, moderation, retention, appeal and rate limits.

## Trust boundary
Provider data is untrusted external input. Validate schemas, preserve raw source provenance, normalize safely and never execute provider-supplied content.
