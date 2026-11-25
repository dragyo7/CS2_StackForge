# StackForge — User Flow

**Status:** Product baseline  
**Audience:** Product, design, frontend, backend, QA, coding agents  
**Primary job:** Organize an existing group of ten CS2 players into a competitive 5v5 private match with minimal friction.

## 1. Product principle

StackForge is a **10-player private-match organizer and team-balancing assistant**, not a public ranked matchmaking queue and not a cheat-detection authority.

The happy path is:

1. Open or create a community match room.
2. Add/select ten players from saved players, Steam profile URLs, SteamID64 values, or invitations.
3. Resolve identities and enrich profiles in the background.
4. Run an integrity preflight and show evidence/status without blocking the room unnecessarily.
5. Generate balanced teams.
6. Explain the result and show alternatives.
7. Let players object, request swaps, lock assignments, or remake teams.
8. Host finalizes an agreed proposal.
9. Copy/share the line-up and later record the match result.

**Maps are random in the actual play workflow.** Do not ask users to choose a map, do not select/veto a map, and do not expose a map picker in the team-generation flow. Map-specific player performance is a hidden input to make the two teams robust across the community's active map pool. It must not decide or announce the map.

## 2. Roles

- **Visitor:** Can view public product/community pages and join an invited room according to its access policy.
- **Community member:** Can maintain their own profile, join rooms, respond to proposals and submit feedback.
- **Room host:** Creates a room, selects players, configures team constraints, requests generations and finalizes a team proposal.
- **Community admin/owner:** Manages community players, roles, watch subscriptions, reports, and community settings.
- **Reviewer/moderator:** Reviews evidence-backed integrity reports. This role is separate from match hosting.
- **System worker:** Refreshes permitted provider data, stores snapshots and emits change alerts.

## 3. First-use flow

1. User signs in with StackForge authentication. Steam OpenID may be used to link/verify a Steam identity; never collect Steam passwords.
2. User creates a community or accepts an invitation.
3. User imports players by:
   - Steam profile URL,
   - SteamID64,
   - multiple newline/comma-separated Steam URLs/IDs,
   - existing community player search,
   - invitation/claim link.
4. Parser extracts a candidate SteamID64. Backend validates format and resolves public Steam profile data where available.
5. Show a preview before committing: existing global player, already in this community, new global player, invalid/unresolved.
6. Commit import idempotently. Never create duplicate global Steam identities.
7. Start optional stats refresh and Steam ban check asynchronously. Do not make provider uptime a prerequisite for adding a player.

## 4. Match-room flow (primary)

### 4.1 Create room
- Host selects community and creates a room.
- Room starts in `DRAFT`.
- No map selection field appears.
- Host may set optional constraints: team locks, together pairs, opponent pairs, preferred roles, excluded players, generation mode.
- Defaults should be minimal: ten players, balanced mode, no constraints.

### 4.2 Fill ten slots
- Search saved community players by nickname, Steam name, SteamID64.
- Show avatar, short identity, cached rating summary, stats freshness and integrity summary.
- Add saved player in one action.
- Add a new player by pasting URL/ID. Resolve in background; let the host continue while enrichment runs.
- Allow invited player to claim/verify their profile.
- Show exactly `n/10` slots.
- Prevent duplicate player identity in one room.
- Permit replacing a selected player before finalization.
- When exactly ten valid player identities are selected, enable preflight and generation.

### 4.3 Preflight
Run independent checks in parallel:
- Steam profile summary and ban endpoint, subject to API availability/rate limits.
- FACEIT lookup if identity can be resolved and access is authorized.
- Leetify profile if available and permitted.
- other approved provider lookups.
- local cache/history.
- community review records visible to this community.

Return per-source status: `OK`, `FLAGGED`, `UNKNOWN`, `STALE`, `UNAVAILABLE`, or `NOT_LINKED`.
Do not block team generation on provider outage. Show a clear warning if trust data is incomplete.
A `game ban` or `VAC ban` must be described with source, timestamp, available app/game context and exact provider fields. Do not call every Steam game ban a CS2 cheat conviction.
New-player preflight is required before first inclusion in a community's regular stack, but host may proceed with an explicit acknowledgement if policy permits.

### 4.4 Generate teams
- Generate from the selected ten only.
- Use available ratings and normalized stats with per-metric provenance and confidence.
- Incorporate map-specific stats privately across the active map pool; do not ask for or select a map.
- Enumerate unique 5v5 partitions (126 for ten players), subject to constraints.
- Save every generation with algorithm version, input snapshot/version, seed, objective components and explanation.
- Return the recommended split plus several materially distinct alternatives.
- Team labels should be neutral and swappable (Team A / Team B).
- Do not fabricate win probabilities. Only show calibrated probabilities after enough outcome data exists.

### 4.5 Explain the result
Show:
- players on each side;
- each player's normalized strength band and data confidence;
- team aggregate strength and difference;
- Premier/FACEIT/Leetify source coverage (not raw metrics alone);
- recent-form balance;
- role coverage;
- hidden map-pool robustness summary, with no map selection or map reveal;
- integrity alerts separately from skill;
- missing/stale data;
- constraints honored;
- why this split ranked above alternatives.

Explanation is deterministic from optimizer output. An LLM may rewrite explanation text only from structured facts and must not invent reasons or accusations.

### 4.6 Objection and remake flow
Each selected player can:
- approve;
- request a swap (choose self and optionally a suggested counterpart);
- request a new generation;
- add a short reason;
- flag a factual profile/stat error.

Host can:
- accept/reject/resolve an objection;
- swap two players manually and view balance delta;
- lock a player to Team A or Team B;
- lock a pair together or as opponents;
- regenerate while preserving locks;
- choose another saved alternative;
- full remake after replacing players or changing constraints;
- restore any prior generation.

A remake creates a **new proposal**, never silently overwrites the previous one. Preserve history and explain what changed.
Avoid repeated identical splits. Exclude previous partitions when possible; if constraints or the finite search space are exhausted, say so.

### 4.7 Approval and finalization
- Show approval count and pending objections.
- Community policy may require host-only approval or a configurable quorum.
- Host can finalize even if some users have not responded, but the UI must disclose this.
- Finalization freezes a versioned team assignment.
- Later changes require reopening the room or creating a new proposal; preserve the finalized snapshot.
- Provide copy-to-clipboard and shareable line-up output.
- StackForge does not automatically create or control an official Valve Premier lobby. It provides the selected line-up for players to use in the supported private-match workflow.

### 4.8 Post-match
- Host records map (optional post-match fact), result, score, match date and source.
- If a demo is available, upload it for asynchronous parsing subject to storage/consent rules.
- Update community Elo only from verified/accepted match results.
- Update player-map performance from the actual map played.
- Update chemistry from repeated paired results with sample-size shrinkage.
- Save MVP and match statistics with provenance.
- Do not retroactively change the historical team-generation input snapshot.

## 5. Fast-path UX requirements

- A returning host should be able to create a room and select ten saved players with minimal navigation.
- Bulk paste must accept mixed Steam profile URLs and SteamID64s.
- Player search must be responsive and keyboard-friendly.
- Provider enrichment is asynchronous and cached.
- Keep the room usable when external APIs are slow or unavailable.
- Display a single concise preflight summary with expandable evidence.
- One-click `Generate`, `Regenerate`, `Swap`, `Lock`, `Restore`, `Finalize`, `Copy teams`.
- Mobile layout must support the full workflow.
- Never require manual entry of stats if a supported provider has them.
- Never make the host re-enter the same Steam ID for a returning player.

## 5.1 Player Identity, Profile & Cards Flow (Implemented)

- **Profile refresh & alias tracking:** From **Players** or **Player Stats**, click **Refresh** (respects cache TTL) or **Force Refresh** to update Steam persona/avatar and FACEIT/Leetify metrics. When a player's Steam username changes, the previous name is preserved in `player_aliases` without duplicating the player.
- **Alias lookup:** Searching in **Players** or **Player Stats** matches current nickname, Steam persona, canonical `SteamID64`, and historical aliases.
- **Player intelligence & comparison:** Open **Player Stats** to inspect source-qualified competitive and combat metrics (with `Unavailable from this source` for missing fields), filter by provider/scope, log community match stats, or switch to **Compare Players** for side-by-side comparison.
- **CS2 Player Cards:** Open **Player Cards** (or a player's profile) to view evidence-based CS2 titles and badges, adjust humour intensity (`Mild`/`Spicy`/`Savage`), reroll taglines from the same evidence, hide individual badges, toggle humour off, or copy Discord-ready card text.

## 6. State machine

`DRAFT -> READY_FOR_PREFLIGHT -> PREFLIGHT_RUNNING -> READY_TO_GENERATE -> PROPOSED -> REVIEWING -> FINALIZED -> COMPLETED`

Side paths:
- `PROPOSED/REVIEWING -> PROPOSED` for regenerate/swap/restore.
- `DRAFT/READY_* -> DRAFT` when roster changes.
- `FINALIZED -> REVIEWING` only through explicit reopen with audit event.
- `COMPLETED` is terminal for that match record; corrections are append-only revisions.

Invalid transitions must return a typed conflict response, not silently mutate state.
