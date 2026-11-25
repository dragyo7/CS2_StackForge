# Rollback and Release Safety

- Schema migrations in `backend/app/migrations.py` are additive (`CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ... ADD COLUMN` only) so rollback to an earlier build preserves existing rows without data loss.
- Provider adapters (`steam`, `faceit`, `leetify`, `cswatch`) can be isolated or disabled independently without blocking match-room balancing.

## General release rules
- Ship behind feature flags where practical.
- Deploy backward-compatible schema changes first.
- Back up PostgreSQL before destructive migrations.
- Keep previous container image and frontend build available.
- Never delete old team proposals or ban snapshots during rollback.
- Record release version and migration version.

## Database migration pattern
Prefer expand -> migrate -> contract:
1. Add nullable/new tables/columns.
2. Deploy code that writes compatible old/new representation.
3. Backfill in batches if required.
4. Switch reads.
5. Verify.
6. Remove obsolete fields only in a later release with explicit approval.

Every migration must be tested on a copy of production-like data. Down migrations should be available where safe; if a migration is irreversible, document forward-fix and restore strategy.

## Feature rollback
- Provider adapter failure: disable that provider feature flag; cached data remains visible with stale marker.
- Premier provider outage/terms change: disable adapter; do not remove stored provenance.
- Watchtower false-positive incident: disable external reputation display/alerts while preserving raw audit snapshots; publish correction.
- Optimizer regression: restore prior algorithm version and use stored generation snapshots.
- Map-pool weight regression: restore prior pool version; do not rewrite historical generations.
- Demo parser vulnerability: disable uploads/worker queue, quarantine pending files, patch parser and reprocess only after validation.
- Discord outage: web app continues.
- GSI companion issue: disable local capture; web workflow continues.

## Data recovery
- Automated PostgreSQL backups and tested restore.
- Object storage versioning/lifecycle for demos.
- Keep finalized lineups and generation input snapshots.
- Ban snapshots and audit events append-only.
- Restore test at least before public launch and periodically thereafter.

## Rollback checklist
- [ ] Identify affected release and migration.
- [ ] Stop background jobs if they can corrupt/repeat work.
- [ ] Disable faulty feature/provider.
- [ ] Preserve logs and evidence.
- [ ] Restore previous app image or deploy forward fix.
- [ ] Restore DB only if data integrity requires it; avoid losing new valid records.
- [ ] Verify login, community isolation, player search, room and generation.
- [ ] Re-enable workers gradually.
- [ ] Document incident and follow-up tests.
