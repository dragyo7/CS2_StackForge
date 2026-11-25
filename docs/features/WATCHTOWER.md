# Feature: Watchtower — Integrity and Ban Monitoring

## Goal
Provide transparent, source-qualified account history and alerts. It is not an anti-cheat engine and must not issue unsupported accusations.

## Evidence classes
1. Official platform enforcement (Steam/FACEIT, with exact scope).
2. Third-party reputation (e.g. CSWatch, explicitly attributed).
3. Behavioural anomaly from demo analysis.
4. Community allegation/report.
5. Human-reviewed evidence outcome.

Keep these independent in storage and UI.

## Steam
Use `ISteamUser/GetPlayerBans` and `GetPlayerSummaries` server-side. Store timestamped snapshots. Compare for changes. Use app context where supplied. Steam CS2 game-ban reasons include cheating, matchmaking-rank manipulation, botting/automation and interference; generic game-ban counts are not necessarily a cheat conviction. Do not call a generic VAC/game ban a CS2 cheat unless evidence establishes scope.

## New-player preflight
When a new Steam identity enters a community:
- resolve SteamID64;
- fetch Steam public profile and ban fields;
- check available FACEIT/Leetify identity;
- optionally query CSWatch API only after terms/attribution review;
- show source status and freshness;
- do not block team generation on provider outage;
- require host acknowledgement for configured severe official enforcement flags.

## Continuous monitoring
- watchlist is opt-in and scoped to global player plus community subscriptions;
- schedule polling within provider limits (daily default for Steam);
- append snapshots, never overwrite;
- emit event only on meaningful state change;
- deduplicate notifications;
- show last checked time;
- support unwatch and retention controls.

## Third-party sources
CSWatch documents a public JSON API and asks for visible attribution; its stated fair-use limit is 30 player requests/minute/IP. Confirm current terms before launch.
CS2SUS, Cheatscanner, CS2Track, VACWatch and CS.Ninja are reference-only unless a documented authorized API and terms are verified. No scraping.

## Review
A suspicious score is a prompt for review, not a verdict. Demo findings must include evidence location, baseline and limitations. Reports need private-by-default access, reviewer audit trail and appeal.

## Acceptance
- ban snapshot history retained;
- new ban change creates one event;
- generic game ban not labelled CS2 cheat without scope;
- missing data never shown as clean;
- third-party reputation never presented as official Valve status;
- community report never shown as confirmed fact.
