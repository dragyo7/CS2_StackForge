# Feature: Canonical Steam Identity & Alias History

**Status:** Implemented (local SQLite + optional Steam Web API refresh)

## Purpose
Keep every player uniquely and reliably identifiable across frequent Steam username changes, avoiding duplicate records and preserving historical aliases.

## User Flow
1. Host adds or bulk-imports players via `SteamID64`, `steamcommunity.com/profiles/{id}`, `steamcommunity.com/id/{vanity}`, or manual nickname.
2. When `SteamID64` is provided (or resolved via `STEAM_API_KEY`), the canonical global `Player.steam_id64` string links to the community profile.
3. On profile refresh (`POST /api/players/{id}/refresh`), if Steam reports a changed `personaname`, the previous and new names are appended to `player_aliases` while preserving the same `Player.id` and `steam_id64`.
4. Searching in the Players or Player Stats screens matches current community nickname, Steam persona name, `SteamID64`, vanity name, and historical aliases.

## Data Requirements
- `players`: `id`, `steam_id64` (unique string when set), `vanity_name`, `steam_persona_name`, `avatar_url`, `identity_status`, `last_successful_refresh_at`, `last_refresh_attempt_at`, `refresh_status`, `refresh_error`, `profile_visibility`.
- `player_aliases`: `id`, `player_id`, `alias_name`, `previous_name`, `source`, `observed_at` (append-only, consecutive duplicates suppressed).
- `community_players.display_name` remains community-scoped and independent of `players.steam_persona_name`.

## API Contracts
- `GET /api/players?q=...` — searches current names, `steam_id64`, and historical `player_aliases`.
- `POST /api/players/{id}/refresh?force=false` — TTL-cached (`PROVIDER_CACHE_TTL_SECONDS`, default 900s) refresh returning `RefreshProfileResponse` (`profile`, `cache_hit`, `alias_changed`, `message`).

## UI Behaviour
- Player Registry and Profile views show canonical `SteamID64` (or `Manual only`), `Previously: <alias>` indicator, `Last updated` timestamp, and `Refresh` / `Force Refresh` controls.

## Failure Handling
- Vanity URLs without `STEAM_API_KEY` return `UNRESOLVED` in bulk import and are never guessed.
- Provider timeouts/outages set `refresh_status = UNAVAILABLE` and preserve the last valid `steam_persona_name`, `avatar_url`, and cached statistics.

## Security & Privacy
- Display names are never treated as verified Steam ownership.
- Two distinct `SteamID64`s with identical display names remain separate global records.

## Acceptance Criteria
- Changing a player's Steam persona updates the same `Player` row, records `PlayerAlias`, prevents duplicate consecutive entries, and stays searchable by previous name.
- Failed refreshes do not overwrite cached identity fields.
