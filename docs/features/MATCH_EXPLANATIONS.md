# Feature: CS2-Native Match Explanations & Multi-Dimensional Balancing

**Status:** Implemented & Live-Tested (`backend/app/optimizer/normalizer.py`, `backend/app/optimizer/engine.py`, `MatchRoomView.tsx`)

## Multi-Dimensional Ranking & Balancing (`norm_v2`, `stackforge_126_v2`)
- **No manual ratings:** `manual_rating` is completely excluded from normalization, community standings, and 5v5 team generation (kept only as a benign nullable/default legacy column for DB compatibility).
- **Separate scale calibration:** Premier CSR, FACEIT ELO, and Leetify Rating are mapped via provider-specific curves to an internal `[0, 100]` competitive scale.
- **Sub-dimension signals (coverage-weighted):** Combines verified `Aim` (`aim_rating`, `preaim`, `reaction_time_ms`, spotted/spray accuracy, strictly bounded `hs_pct`), `Utility` (`utility_rating`, utility damage, flash assists, enemies flashed), `Damage` (`adr`, counter-strafe consistency), `Survival` (`kd_ratio`, optional `kast`), `Entry`, `Trading`, `Clutch`, and sample-damped `recent_form` (`recent` snapshot preferred for recent form/ADR; `lifetime` snapshot preferred for lifetime rates).
- **Missing & insufficient data:** Players without external ratings and `< 5` combat matches receive `normalized_strength = None` (`INSUFFICIENT_DATA`, confidence `0%`), appear at the bottom of Community Standings as `Unranked`, and are split evenly across Team A and Team B without inventing fake skill numbers. Missing dimensions shrink automatically via coverage weighting rather than punishing incomplete profiles.
- **Trust separation:** CSWatch / watchlist warnings appear as compact informational badges in Match Room and never modify competitive skill ratings.

## CS2-Native Captain Explanations
- Summarizes each team's genuine statistical profile (`Aim Rating`, `pre-aim`, `opening-duel potential`, `ADR`, `Utility Rating`, `trading`, `consistency`, `clutch conversion`, `recent form`, and `tagged roles`) in natural CS2 language.
- Discloses data uncertainty (`insufficient_data_players`, `low_confidence_players`, `stale_count`) transparently without exposing internal optimizer formulas or weights.
- Preserves exhaustive 126-partition search, locks, swaps, regeneration, alternatives, random-map policy (no map picker), and Discord export.
