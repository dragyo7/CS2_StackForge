# Feature: Player Intelligence & Live CS2 Data

**Status:** Implemented (`backend/app/providers/external.py`, `PlayerStatsView.tsx`)

## Live Provider Coverage
- **Leetify Public CS API v3:** Keyless public lookups (`GET /v3/profile`, `GET /v3/profile/matches`) retrieve `ranks.leetify`, `ranks.premier`, `ranks.faceit_elo`, overall `winrate`/`total_matches`, recent 10-match and 30-match aggregates (`ADR`/`dpr`, `K/D`, `HS%`, utility dmg, flash assists, multi-kill rate), deduplicated `player_match_records`, `recent_form`, and hidden per-map deltas (`map_ratings_json`).
- **FACEIT Data API v4:** Implemented (`GET /players`, `GET /players/{id}/stats/cs2`); requires server-side `FACEIT_API_KEY`.
- **CSStats.gg:** Profile links and `SteamID64` extraction from `/player/{steamid64}` supported; no scraping of Cloudflare-gated pages.

## Provenance & Presentation
- Separate scales (Premier, FACEIT ELO, Leetify Rating, Manual Baseline, Normalized `norm_v1`) are displayed distinctly.
- Missing metrics display `"Unavailable from this source"`, never zero.
