# Feature: CS2-Native Match Explanations & Multi-Dimensional Balancing

**Status:** Implemented & Verified (`backend/app/optimizer/normalizer.py`, `backend/app/optimizer/engine.py`, `backend/app/services/room_service.py`, `MatchRoomView.tsx`)

## Multi-Dimensional Ranking & Balancing (`norm_v2`, `stackforge_126_v2`)
- **No manual ratings:** `manual_rating` is completely excluded from normalization, user-facing spreadsheet import mappings (`import_service.py` / `CommunityImportPanel.tsx`), community standings, and 5v5 team generation (legacy column preserved in SQLite only for backwards compatibility).
- **Separate scale calibration:** Premier CSR, FACEIT ELO, and Leetify Rating are mapped via provider-specific curves to an internal `[0, 100]` competitive scale.
- **Sub-dimension signals (coverage-weighted & reproducible):** Combines verified `Aim` (`aim_rating`, `preaim`, `reaction_time_ms`, spotted/spray accuracy, strictly bounded `hs_pct`), `Utility` (`utility_rating`, utility damage, per-round flash assists `[0.002..0.080]`, enemies flashed), **`Positioning` (`positioning_rating` 72% + `traded_deaths_pct` 28%)**, `Damage` (`adr`, counter-strafe consistency), `Survival` (`kd_ratio`, optional `kast`), `Entry`, `Trading`, `Clutch`, and sample-damped `recent_form`.
- **Reproducible generation snapshots:** Every `TeamGeneration` freezes raw inputs AND computed `dimension_scores` (`aim_score`, `utility_score`, `positioning_score`, `damage_score`, `survival_score`, `entry_score`, `trade_score`, `clutch_score`) inside `input_snapshot_json` alongside exact model versions (`algorithm_version`, `normalizer_version`, `map_pool_version`).
- **Missing & insufficient data:** Players without external ratings and `< 5` combat matches receive `normalized_strength = None` (`INSUFFICIENT_DATA`, confidence `0%`), appear at the bottom of Community Standings as `Unranked`, and are split evenly across Team A and Team B without inventing fake skill numbers.
- **Trust separation:** CSWatch / watchlist warnings appear as compact informational badges and never alter skill strength.

## CS2-Native Captain Explanations & Post-Match Lifecycle
- Summarizes genuine statistical edges (`Aim Rating`, `pre-aim`, `opening-duel potential`, `ADR`, `Utility Rating`, **`Positioning Rating & Traded Deaths %`**, `trading`, `consistency`, `clutch conversion`, `recent form`, and `tagged roles`) plus transparent data uncertainty notes (`insufficient_data_players`, `low_confidence_players`, `stale_count`).
- Supports full room lifecycle (`DRAFT -> PROPOSED -> REVIEWING -> FINALIZED -> PLAYED -> RESULT_RECORDED -> ANALYZED`) with post-match result capture (`map_played`, score, winner) that keeps random maps strictly post-match (no pre-match picker/veto) and keeps community standings completely separate from Valve Premier / FACEIT / Leetify ladder ranks.
