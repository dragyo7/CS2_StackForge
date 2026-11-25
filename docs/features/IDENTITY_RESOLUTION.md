# Feature: Universal Player Identity Resolution

**Status:** Implemented (`backend/app/services/steam_parser.py`, `backend/app/services/identity_resolver.py`)

## Supported Identifiers
- `SteamID64` (`7656119...`)
- `steamcommunity.com/profiles/{steamid64}` & `/id/{vanity}`
- `csstats.gg/player/{steamid64}`
- `leetify.com/app/profile/{steamid64|uuid}`
- `cswatch.gg/player/{steamid64}`
- `faceit.com/en/players/{nickname}`
- Community nickname / historical alias candidates

## Confidence Model
- `VERIFIED`: Canonical `SteamID64` or verified provider ID matched reliably.
- `CANDIDATE`: Nickname or alias match requiring explicit host confirmation (`POST /api/identity/confirm`); never auto-merged.
- `UNRESOLVED`: Insufficient identifier data or missing Steam/FACEIT API key for vanity/nickname lookup.

## Cross-Provider Discovery
Given a verified `SteamID64`, `resolve_identifier` queries authorized public endpoints (Leetify Public API, CSWatch Public API, and FACEIT/Steam when keys are set) and returns discovered external identities for confirmation or attachment in `player_external_identities`.
