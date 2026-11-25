# Feature: Trust & Account Watch (Watchtower)

**Status:** Implemented (`backend/app/services/trust_service.py`, `TrustWatchView.tsx`)

## Separated Evidence Categories
1. `OFFICIAL_ENFORCEMENT`: Steam `GetPlayerBans` (when `STEAM_API_KEY` configured).
2. `THIRD_PARTY_REPUTATION`: CSWatch public JSON API (`cswatch.gg/api/public/player/{steamId}`) with explicit attribution link and 25/min fair-use client limiter.
3. `BEHAVIORAL_ANOMALY`: Schema-ready for future offline demo parsing.
4. `COMMUNITY_REPORT`: Private community moderator observations (`POST /api/trust/reports`).
5. `HUMAN_REVIEW`: Watchlist review decisions (`REVIEWED` / `DISMISSED`).

## Non-Accusatory Policy
- No automatic `CHEATER / CLEAN` labels.
- No ban record does not prove clean; a generic Steam game-ban count does not prove a CS2 cheating conviction.
- Watchlist entries and reports remain private to the community.
