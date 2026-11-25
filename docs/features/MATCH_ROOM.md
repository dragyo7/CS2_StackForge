# Feature: 10-Man Match Room

## Goal
Fast, repeatable selection and negotiation of exactly ten CS2 players.

## Requirements
- Create room in a community.
- Search/select saved players.
- Bulk import Steam IDs/URLs.
- Resolve unknown players without blocking.
- Prevent duplicate identities.
- Show slot count, data freshness and integrity status.
- Allow replacement before finalization.
- No map picker.
- Persist room roster and version.
- Support invitation link and optional guest response token.

## States
`DRAFT`, `ROSTER_READY`, `PREFLIGHT_RUNNING`, `READY_TO_GENERATE`, `PROPOSED`, `REVIEWING`, `FINALIZED`, `COMPLETED`, `CANCELLED`.

## Acceptance
- Exactly ten unique players required to generate.
- A provider outage does not block roster completion.
- Room changes invalidate current proposal but preserve history.
- Every mutation is permission-checked and audited.
