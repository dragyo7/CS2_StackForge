# Feature: Community Spreadsheet Import & Read-Only Sync

**Status:** Implemented (`backend/app/services/import_service.py`, `CommunityImportPanel.tsx`)

## Supported Sources
- **Google Sheets (read-only CSV export):** Converts `/spreadsheets/d/{id}/...` to `/export?format=csv&gid={gid}` without writing to the sheet.
- **CSV & XLSX uploads:** Parsed server-side (`csv.DictReader`, `openpyxl`) with auto-detected column mapping (`Name`, `Url`, `IGN`, `SteamID64`, `Rating`, `Role`, `Notes`).

## Verified Real Community Sheet
- Inspected `https://docs.google.com/spreadsheets/d/1iakYU0vzcceZ1AYjgndrwwEkaeAt6Bym3dIjzS41reM/edit?usp=drivesdk` (`Sheet1`, 12 player rows, columns `Name`, `Url`, `IGN`).
- All 12 `Url` entries follow `https://csstats.gg/player/<17-digit SteamID64>` and extract canonical `SteamID64` + verified `csstats` external identity links.

## Safety & Re-Import Guarantees
- Preview classifies `NEW`, `MATCHED_EXISTING`, `DUPLICATE_IN_SHEET`, `CONFLICT`, `UNRESOLVED`, and `INVALID` before committing.
- Re-import & **Sync Now** compute `content_hash`, track `last_attempted_sync_at` / `last_successful_sync_at`, and preserve manual edits unless `overwrite_manual=true` is explicitly chosen.
