from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import HTTPException
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    ActivityEvent,
    CommunityPlayer,
    Player,
    PlayerAlias,
    SpreadsheetImport,
    SpreadsheetImportRow,
)
from app.schemas import PlayerCreate
from app.services.identity_resolver import upsert_external_identity
from app.services.player_service import create_player, to_player_out
from app.services.steam_parser import VALID_ROLES, detect_universal_identifier, is_valid_steam_id64

GSHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


def build_gsheet_csv_export_url(sheet_url: str) -> tuple[str, str]:
    """Converts a Google Sheets /edit or /view URL to its read-only CSV export URL."""
    m = GSHEET_ID_RE.search(sheet_url)
    if not m:
        raise HTTPException(
            status_code=422,
            detail="Invalid Google Sheets URL. Expected https://docs.google.com/spreadsheets/d/<ID>/...",
        )
    sheet_id = m.group(1)
    parsed = urlparse(sheet_url)
    qs = parse_qs(parsed.query)
    gid = qs.get("gid", ["0"])[0]
    if not gid and parsed.fragment and "gid=" in parsed.fragment:
        gid = parsed.fragment.split("gid=", 1)[1].split("&", 1)[0]
    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    return export_url, sheet_id


async def fetch_google_sheet_csv(sheet_url: str, timeout: float = 10.0) -> tuple[str, str]:
    export_url, _ = build_gsheet_csv_export_url(sheet_url)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(export_url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not fetch Google Sheet: {exc}") from exc

    if resp.status_code in (401, 403):
        raise HTTPException(
            status_code=403,
            detail="Google Sheet is private/requires sign-in. Share as 'Anyone with the link can view' or upload an exported CSV/XLSX.",
        )
    if resp.status_code != 200 or "text/html" in (resp.headers.get("content-type") or "").lower():
        raise HTTPException(
            status_code=403,
            detail="Google Sheet returned HTML/login page instead of CSV. Ensure link access is enabled or upload CSV/XLSX.",
        )
    return resp.text, export_url


def parse_csv_bytes(raw_bytes: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip() for h in (reader.fieldnames or []) if h and h.strip()]
    rows: list[dict[str, str]] = []
    for row in reader:
        cleaned = {(k.strip() if k else ""): (v.strip() if v is not None else "") for k, v in row.items() if k}
        if any(cleaned.values()):
            rows.append(cleaned)
    return headers, rows


def parse_xlsx_bytes(raw_bytes: bytes) -> tuple[list[str], list[dict[str, str]]]:
    wb = load_workbook(io.BytesIO(raw_bytes), read_only=True, data_only=True)
    ws = wb.active
    raw_rows = list(ws.iter_rows(values_only=True))
    if not raw_rows:
        return [], []
    headers = [str(c).strip() if c is not None else f"col_{idx+1}" for idx, c in enumerate(raw_rows[0])]
    rows: list[dict[str, str]] = []
    for r in raw_rows[1:]:
        row_dict = {
            headers[i]: (str(r[i]).strip() if i < len(r) and r[i] is not None else "")
            for i in range(len(headers))
        }
        if any(row_dict.values()):
            rows.append(row_dict)
    return headers, rows


def auto_detect_mapping(headers: list[str]) -> dict[str, str | None]:
    """Maps spreadsheet columns to StackForge fields."""
    mapping: dict[str, str | None] = {
        "display_name": None,
        "real_name": None,
        "identity_url": None,
        "steam_id64": None,
        "manual_rating": None,
        "primary_role": None,
        "premier_rating": None,
        "faceit_elo": None,
        "notes": None,
    }
    low_map = {h.lower().strip(): h for h in headers}

    # Prefer IGN / Nickname for display_name if both Name and IGN exist
    for key in ("ign", "nickname", "alias", "in-game name", "gamertag", "player"):
        if key in low_map:
            mapping["display_name"] = low_map[key]
            break
    for key in ("name", "full name", "player name", "real name"):
        if key in low_map:
            if mapping["display_name"] is None:
                mapping["display_name"] = low_map[key]
            else:
                mapping["real_name"] = low_map[key]
            break
    for key in ("url", "profile", "profile url", "csstats", "csstats url", "steam url", "link"):
        if key in low_map:
            mapping["identity_url"] = low_map[key]
            break
    for key in ("steamid64", "steam_id64", "steamid", "steam64"):
        if key in low_map:
            mapping["steam_id64"] = low_map[key]
            break
    for key in ("rating", "manual rating", "skill", "skill rating"):
        if key in low_map:
            mapping["manual_rating"] = low_map[key]
            break
    for key in ("role", "primary role"):
        if key in low_map:
            mapping["primary_role"] = low_map[key]
            break
    for key in ("premier", "premier rating"):
        if key in low_map:
            mapping["premier_rating"] = low_map[key]
            break
    for key in ("faceit", "faceit elo", "elo"):
        if key in low_map:
            mapping["faceit_elo"] = low_map[key]
            break
    for key in ("notes", "note", "comments"):
        if key in low_map:
            mapping["notes"] = low_map[key]
            break
    return mapping


def _compute_hash(headers: list[str], rows: list[dict[str, str]]) -> str:
    payload = json.dumps({"headers": headers, "rows": rows}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_row(
    row: dict[str, str],
    mapping: dict[str, str | None],
    default_rating: float = 55.0,
) -> dict[str, Any]:
    def get_col(field: str) -> str:
        col = mapping.get(field)
        return (row.get(col) or "").strip() if col else ""

    display_name = get_col("display_name") or get_col("real_name")
    real_name = get_col("real_name")
    raw_url = get_col("identity_url")
    raw_sid = get_col("steam_id64")

    steam_id64: str | None = None
    source_provider: str | None = None
    source_url: str | None = None

    if raw_sid and is_valid_steam_id64(raw_sid):
        steam_id64 = raw_sid
    elif raw_url:
        det = detect_universal_identifier(raw_url)
        if det.steam_id64:
            steam_id64 = det.steam_id64
            if det.identifier_type in ("csstats_url", "leetify_url", "cswatch_url", "steam_profile_url"):
                source_provider = det.identifier_type.replace("_url", "")
                source_url = det.profile_url

    rating_val = default_rating
    raw_rating = get_col("manual_rating")
    invalid_reason: str | None = None
    if raw_rating:
        try:
            r_f = float(raw_rating)
            if 1.0 <= r_f <= 100.0:
                rating_val = r_f
            else:
                invalid_reason = f"Rating '{raw_rating}' out of range (expected 1–100)."
        except ValueError:
            invalid_reason = f"Invalid rating '{raw_rating}'."

    premier_val: int | None = None
    if get_col("premier_rating"):
        try:
            premier_val = int(float(get_col("premier_rating").replace(",", "")))
        except ValueError:
            pass

    faceit_val: int | None = None
    if get_col("faceit_elo"):
        try:
            faceit_val = int(float(get_col("faceit_elo").replace(",", "")))
        except ValueError:
            pass

    role_val: str | None = None
    raw_role = get_col("primary_role")
    if raw_role:
        role_val = next((r for r in VALID_ROLES if r.lower() == raw_role.lower()), None)

    notes_parts = []
    if real_name and display_name and real_name.lower() != display_name.lower():
        notes_parts.append(f"Name: {real_name}")
    if get_col("notes"):
        notes_parts.append(get_col("notes"))

    return {
        "display_name": display_name,
        "real_name": real_name,
        "steam_id64": steam_id64,
        "source_provider": source_provider,
        "source_url": source_url or (raw_url or None),
        "manual_rating": rating_val,
        "has_explicit_rating": bool(raw_rating) and invalid_reason is None,
        "primary_role": role_val,
        "premier_rating": premier_val,
        "faceit_elo": faceit_val,
        "notes": " | ".join(notes_parts) if notes_parts else None,
        "invalid_reason": invalid_reason,
    }


def preview_spreadsheet(
    db: Session,
    community_id: str,
    headers: list[str],
    rows: list[dict[str, str]],
    mapping_override: dict[str, str | None] | None = None,
    default_rating: float = 55.0,
) -> dict[str, Any]:
    mapping = auto_detect_mapping(headers)
    if mapping_override:
        for k, v in mapping_override.items():
            if k in mapping:
                mapping[k] = v

    existing_cps = db.scalars(
        select(CommunityPlayer)
        .options(joinedload(CommunityPlayer.player))
        .where(CommunityPlayer.community_id == community_id, CommunityPlayer.is_active.is_(True))
    ).all()
    by_sid = {cp.player.steam_id64: cp for cp in existing_cps if cp.player.steam_id64}

    seen_sids_in_sheet: set[str] = set()
    preview_rows: list[dict[str, Any]] = []
    counts = {"NEW": 0, "MATCHED_EXISTING": 0, "DUPLICATE_IN_SHEET": 0, "CONFLICT": 0, "UNRESOLVED": 0, "INVALID": 0}

    for idx, raw_row in enumerate(rows, start=1):
        norm = _normalize_row(raw_row, mapping, default_rating=default_rating)
        sid = norm["steam_id64"]
        status = "NEW"
        msg = "New player ready to import."
        matched_id: str | None = None
        matched_name: str | None = None

        if norm["invalid_reason"]:
            status = "INVALID"
            msg = norm["invalid_reason"]
        elif not norm["display_name"] and not sid:
            status = "INVALID"
            msg = "Missing both display name and SteamID64."
        elif not sid:
            status = "UNRESOLVED"
            msg = "No SteamID64 or supported profile URL found; requires manual review."
        elif sid in seen_sids_in_sheet:
            status = "DUPLICATE_IN_SHEET"
            msg = f"Duplicate SteamID64 {sid} within this spreadsheet."
        elif sid in by_sid:
            existing = by_sid[sid]
            matched_id = existing.id
            matched_name = existing.display_name
            seen_sids_in_sheet.add(sid)
            if norm["display_name"] and norm["display_name"].lower() != existing.display_name.lower():
                status = "CONFLICT"
                msg = f"Matches '{existing.display_name}' by SteamID64, but sheet name is '{norm['display_name']}'."
            else:
                status = "MATCHED_EXISTING"
                msg = f"Already registered as '{existing.display_name}' (safe re-import)."
        else:
            seen_sids_in_sheet.add(sid)
            status = "NEW"
            msg = f"New canonical SteamID64 {sid}" + (f" ({norm['source_provider']})" if norm["source_provider"] else "")

        counts[status] += 1
        preview_rows.append(
            {
                "row_number": idx,
                "raw": raw_row,
                "normalized": norm,
                "status": status,
                "message": msg,
                "matched_community_player_id": matched_id,
                "matched_display_name": matched_name,
            }
        )

    return {
        "headers": headers,
        "mapping": mapping,
        "content_hash": _compute_hash(headers, rows),
        "total_rows": len(rows),
        "counts": counts,
        "rows": preview_rows,
    }


def commit_spreadsheet_import(
    db: Session,
    community_id: str,
    source_type: str,
    source_label: str,
    source_url: str | None,
    headers: list[str],
    rows: list[dict[str, str]],
    mapping_override: dict[str, str | None] | None = None,
    overwrite_manual: bool = False,
    default_rating: float = 55.0,
) -> dict[str, Any]:
    preview = preview_spreadsheet(
        db,
        community_id=community_id,
        headers=headers,
        rows=rows,
        mapping_override=mapping_override,
        default_rating=default_rating,
    )

    summary_counts = {"created": 0, "matched": 0, "updated": 0, "duplicates": 0, "unresolved": 0, "invalid": 0}
    job = SpreadsheetImport(
        community_id=community_id,
        source_type=source_type,
        source_label=source_label,
        source_url=source_url,
        content_hash=preview["content_hash"],
        mapping_json=json.dumps(preview["mapping"]),
        summary_json=json.dumps(summary_counts),
        sync_status="OK",
        last_attempted_sync_at=datetime.now(timezone.utc),
        last_successful_sync_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.flush()

    imported_players = []

    for item in preview["rows"]:
        norm = item["normalized"]
        status = item["status"]
        sid = norm["steam_id64"]
        row_status = status
        row_msg = item["message"]
        cp_id = item["matched_community_player_id"]

        if status in ("INVALID", "UNRESOLVED", "DUPLICATE_IN_SHEET"):
            if status == "INVALID":
                summary_counts["invalid"] += 1
            elif status == "UNRESOLVED":
                summary_counts["unresolved"] += 1
            else:
                summary_counts["duplicates"] += 1
                row_status = "DUPLICATE"
        elif status == "NEW":
            created = create_player(
                db,
                community_id,
                PlayerCreate(
                    display_name=norm["display_name"] or f"Player {sid[-4:]}",
                    steam_id64=sid,
                    steam_profile_url=f"https://steamcommunity.com/profiles/{sid}",
                    manual_rating=norm["manual_rating"],
                    premier_rating=norm["premier_rating"],
                    faceit_elo=norm["faceit_elo"],
                    primary_role=norm["primary_role"],
                    notes=norm["notes"],
                ),
            )
            cp_id = created.id
            if norm["source_provider"] and norm["source_url"]:
                upsert_external_identity(
                    db,
                    player_id=created.player_id,
                    provider=norm["source_provider"],
                    external_id=sid,
                    profile_url=norm["source_url"],
                    verification_state="VERIFIED",
                    confidence=1.0,
                    metadata={"source": source_label, "sheet_name": norm.get("real_name")},
                )
            summary_counts["created"] += 1
            row_status = "CREATED"
            imported_players.append(created)
        elif status in ("MATCHED_EXISTING", "CONFLICT") and cp_id:
            cp = db.scalar(
                select(CommunityPlayer)
                .options(joinedload(CommunityPlayer.player))
                .where(CommunityPlayer.id == cp_id)
            )
            if cp:
                # Attach external identity link (e.g. CSStats) idempotently without overwriting manual edits
                if norm["source_provider"] and norm["source_url"] and sid:
                    upsert_external_identity(
                        db,
                        player_id=cp.player_id,
                        provider=norm["source_provider"],
                        external_id=sid,
                        profile_url=norm["source_url"],
                        verification_state="VERIFIED",
                        confidence=1.0,
                        metadata={"source": source_label, "sheet_name": norm.get("real_name")},
                    )
                if overwrite_manual:
                    if norm["display_name"] and norm["display_name"] != cp.display_name:
                        db.add(
                            PlayerAlias(
                                player_id=cp.player_id,
                                alias_name=norm["display_name"],
                                previous_name=cp.display_name,
                                source="spreadsheet_sync",
                            )
                        )
                        cp.display_name = norm["display_name"]
                    if norm["has_explicit_rating"]:
                        cp.manual_rating = norm["manual_rating"]
                    if norm["notes"] and not cp.notes:
                        cp.notes = norm["notes"]
                    summary_counts["updated"] += 1
                    row_status = "UPDATED"
                    row_msg = f"Updated '{cp.display_name}' from spreadsheet."
                else:
                    # Preserve manual edits, but add real name note if notes empty and alias if new IGN
                    if norm["notes"] and not cp.notes:
                        cp.notes = norm["notes"]
                    summary_counts["matched"] += 1
                    row_status = "MATCHED"
                imported_players.append(to_player_out(db, cp))

        db.add(
            SpreadsheetImportRow(
                import_id=job.id,
                row_number=item["row_number"],
                raw_json=json.dumps(item["raw"]),
                status=row_status,
                matched_community_player_id=cp_id,
                extracted_steam_id64=sid,
                message=row_msg[:300],
            )
        )

    job.summary_json = json.dumps(summary_counts)
    db.add(
        ActivityEvent(
            community_id=community_id,
            event_type="SPREADSHEET_IMPORT",
            title=f"Imported {source_label}",
            detail=f"Created {summary_counts['created']}, matched {summary_counts['matched']}, updated {summary_counts['updated']}, unresolved {summary_counts['unresolved']}.",
        )
    )
    db.commit()

    return {
        "import_id": job.id,
        "source_type": job.source_type,
        "source_label": job.source_label,
        "source_url": job.source_url,
        "content_hash": job.content_hash,
        "summary": summary_counts,
        "last_successful_sync_at": job.last_successful_sync_at,
        "players": imported_players,
    }


def list_import_history(db: Session, community_id: str) -> list[dict[str, Any]]:
    jobs = db.scalars(
        select(SpreadsheetImport)
        .where(SpreadsheetImport.community_id == community_id)
        .order_by(SpreadsheetImport.created_at.desc())
        .limit(15)
    ).all()
    return [
        {
            "id": j.id,
            "source_type": j.source_type,
            "source_label": j.source_label,
            "source_url": j.source_url,
            "content_hash": j.content_hash,
            "summary": json.loads(j.summary_json),
            "sync_status": j.sync_status,
            "last_attempted_sync_at": j.last_attempted_sync_at,
            "last_successful_sync_at": j.last_successful_sync_at,
        }
        for j in jobs
    ]
