# StackForge REST API Reference

Base URL (V2 local): `http://127.0.0.1:8001/api` (proxied at `/api` via Vite on `http://127.0.0.1:5174/`).

## Health, Metrics & Operational Telemetry
- `GET /api/health` — Backend status, live provider readiness (`steam`, `faceit`, `leetify`, `cswatch`), `map_policy: "random_no_picker"`, active/inactive `scheduler`, and `scheduler_detail`.
- `GET /api/metrics/registry` — Full canonical metric definitions (unit, valid range, provider field map, scope, UI/matchmaking usage).
- `GET /api/ops/overview` — Database counts, live scheduler cycle telemetry, honest per-provider ingestion health (`HEALTHY`, `PARTIAL_COVERAGE`, `NOT_CONFIGURED`, `DEGRADED`), rate-limit/private counts, stale & insufficient player lists, credential status, and demo queue placeholder.

## Optional Credentials Vault (Server-Side Windows DPAPI)
- `GET /api/settings/credentials` — Lists connection status & masked hint (`****1234`) for `steam`, `faceit`, `leetify`; never returns plaintext secrets.
- `PUT /api/settings/credentials/{provider}` — Stores key encrypted server-side in DPAPI vault (`validate_live` optional).
- `POST /api/settings/credentials/{provider}/validate` — Validates candidate or stored key server-side without logging or returning it.
- `DELETE /api/settings/credentials/{provider}` — Deletes key from local encrypted vault.

## Players, Intelligence & Refresh
- `GET /api/players` / `GET /api/players/rankings` — Community roster ranked cleanly by `norm_v2` competitive strength (`Unranked` last).
- `POST /api/players` / `PATCH /api/players/{id}` / `DELETE /api/players/{id}` / `POST /api/players/{id}/archive`
- `GET /api/players/{id}/profile` — Normalized profile, `recent`/`lifetime` stat snapshots, match records, alias history, external identities, provider statuses, and evidence-based card.
- `POST /api/players/{id}/refresh?force=false&provider=...` — Single-player refresh (`all`, `steam`, `leetify`, `faceit`, `cswatch`) with single-flight dedup & TTL caching.
- `POST /api/players/refresh-all?force=false` — Roster refresh with TTL skipping, provider error isolation, and ops telemetry update.
- `POST /api/players/{id}/stats` / `GET /api/players/compare?a=...&b=...`
- `POST /api/players/bulk-import` / `POST /api/imports/google-sheet/{preview,commit}` / `POST /api/imports/file/{preview,commit}` / `POST /api/imports/{id}/sync`

## Match Rooms, Balancing & Post-Match Results
- `GET /api/rooms` / `POST /api/rooms` / `GET /api/rooms/{id}`
- `PUT /api/rooms/{id}/roster` / `POST /api/rooms/{id}/replace-player` / `PUT /api/rooms/{id}/players/{pid}/lock` / `POST /api/rooms/{id}/constraints`
- `POST /api/rooms/{id}/preflight` — Non-blocking roster identity & freshness check.
- `POST /api/rooms/{id}/generate` / `POST /api/rooms/{id}/regenerate` — Exhaustive 126-partition `stackforge_126_v2` optimizer (random map policy, no map picker).
- `POST /api/rooms/{id}/swap-preview` / `POST /api/rooms/{id}/swap` / `POST /api/rooms/{id}/proposals/{gid}/adopt-alternative` / `restore`
- `POST /api/rooms/{id}/finalize` / `POST /api/rooms/{id}/reopen`
- `POST /api/rooms/{id}/played` — Advances `FINALIZED` room to `PLAYED`.
- `POST /api/rooms/{id}/result` — Records post-match map played, Team A/B score, winner (`A`/`B`/`TIE`), optional URL/notes; freezes teams (`RESULT_RECORDED` / `ANALYZED`).
- `GET /api/standings/community` — Private community 5v5 leaderboard (`W-L-T`, `Win%`, `Round Diff`, `community_internal_rating`) isolated from external ladder ranks.
- `GET /api/lineups/{share_slug}`

## Trust Watch & Auth
- `GET /api/trust/overview` / `POST /api/trust/players/{id}/check` / `POST /api/trust/watchlist` / `PATCH /api/trust/watchlist/{id}` / `POST /api/trust/reports` / `POST /api/trust/refresh-watched`
- `POST /api/identity/resolve` / `POST /api/identity/confirm`
- `POST /api/auth/{signup,login,logout}` / `GET /api/auth/me`
