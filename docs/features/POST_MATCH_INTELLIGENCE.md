# Feature: Post-Match Intelligence

## Scope
Later release: record completed private matches, player stats, community Elo, MVP, map-specific performance and chemistry.

## Rules
- Match result must be host-confirmed or supported by parsed demo.
- Keep source and confidence.
- Elo is community-specific and separate from Premier/FACEIT.
- Use a documented rating update (e.g. Elo or Glicko-2 after evaluation).
- Player chemistry is sample-size adjusted; raw pair win rate is misleading.
- MVP score must be explainable and not K/D-only.
- Actual map is recorded after play, not selected in the pre-match room.
- Use actual map to update player-map statistics for future hidden balancing.
