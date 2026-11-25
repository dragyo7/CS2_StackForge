# Defense: Third-Party Trust Source Review

## CSWatch
Its developer page documents a public JSON endpoint `GET /api/public/player/{steamId}`, a stated fair-use rate of up to 30 player requests/minute/IP, and visible attribution to cswatch.gg. Treat response as third-party reputation, not official Steam status. Re-check terms, privacy policy and commercial permission before launch.

## CS2SUS
Its FAQ describes a demo-derived anomaly score based on aim signals and explicitly says a high score does not prove cheating. No public API was confirmed in this review. Reference methodology only; do not scrape.

## Cheatscanner.eu
Public product describes demo evidence classes and signals. No public integration API or redistribution permission confirmed. Reference only.

## CS2Track
Public product describes watchlist and ban monitoring. No authorized public API contract confirmed. Reference only.

## VACWatch / CS.Ninja
Useful UX references. Verify API access and terms before any integration. Do not infer Valve Trust Factor from third-party scores.

## Review cadence
Before each public release:
- verify links and docs still exist;
- verify API/terms/rate limits;
- confirm attribution;
- run contract tests;
- update this file and `INTEGRATIONS.md`;
- disable source if terms or access become unclear.
