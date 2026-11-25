# Feature Backlog and Delivery Order

## Completed in local MVP + Phase 2
- Canonical SteamID64 identity parser, registry, bulk import, and alias history (`player_aliases`).
- TTL-cached profile refresh with outage fallback.
- Ten-player match room, 126-partition optimizer, hidden active map-pool robustness, alternatives, swaps, locks, objections, regenerate, restore, finalize, and Discord/shareable lineup.
- Source-qualified player profiles, combat stat snapshots, and side-by-side player comparison.
- Evidence-based CS2 player cards and humour controls (`card_rules_v1`).
- FACEIT and Leetify adapter implementations (ready for API keys).

## Deferred to upcoming milestones
- StackForge authentication & Steam OpenID identity ownership verification.
- Multi-user real-time voting/objections across separate sessions.
- Multi-community tenant isolation enforcement via authenticated sessions / PostgreSQL RLS.
- Watchtower background polling & ban-change alerts.
- Optional CSWatch attributed adapter after terms review.
- Match history recording, verified community Elo, MVP, and player chemistry graphs.
- Post-match `.dem` uploads and Awpy parser worker.
- Discord bot and optional local CS2 GSI companion.

## Explicitly out of scope until separately approved
- Actual Valve Premier lobby automation.
- Map picker/veto.
- Automated cheat verdicts.
- Global public accusation/blacklist.
- Scraping provider sites without permission.
- ML-based prediction before enough validated data.
