from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CommunityPlayer, SpreadsheetImport, WatchlistEntry
from app.providers.cswatch import CSWatchProvider
from app.providers.external import LeetifyProvider
from app.providers.steam import SteamProvider
from app.services import auth_service, identity_resolver, import_service, player_service, trust_service

router = APIRouter(prefix="/api", tags=["platform"])


# ---------------------------------------------------------------------------
# Auth foundation (PBKDF2-HMAC-SHA256 + Bearer session tokens)
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    username: str = Field(..., min_length=2, max_length=80)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=1, max_length=128)


@router.post("/auth/signup")
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    user, token = auth_service.signup_user(db, payload.email, payload.username, payload.password)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "role": user.role,
            "linked_steam_id64": user.linked_steam_id64,
        },
    }


@router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user, token = auth_service.login_user(db, payload.email, payload.password)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "role": user.role,
            "linked_steam_id64": user.linked_steam_id64,
        },
    }


@router.post("/auth/logout")
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    token = authorization.split(" ", 1)[1].strip() if authorization and " " in authorization else None
    auth_service.logout_token(db, token)
    return {"ok": True}


@router.get("/auth/me")
def me(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    user = auth_service.get_optional_user(db, authorization)
    if not user:
        return {"authenticated": False, "mode": "local_dev_host", "user": None}
    return {
        "authenticated": True,
        "mode": "authenticated",
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "role": user.role,
            "linked_steam_id64": user.linked_steam_id64,
        },
    }


# ---------------------------------------------------------------------------
# Universal Identity Resolution
# ---------------------------------------------------------------------------

class ResolveIdentityRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    discover_providers: bool = True


class ConfirmIdentityLinkRequest(BaseModel):
    community_player_id: str
    provider: str
    external_id: str
    profile_url: str | None = None
    steam_id64: str | None = None


@router.post("/identity/resolve")
async def resolve_identity(payload: ResolveIdentityRequest, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return await identity_resolver.resolve_identifier(
        db, comm.id, payload.query, discover_providers=payload.discover_providers
    )


@router.post("/identity/confirm")
def confirm_identity(payload: ConfirmIdentityLinkRequest, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return identity_resolver.confirm_identity_link(
        db,
        comm.id,
        community_player_id=payload.community_player_id,
        provider=payload.provider,
        external_id=payload.external_id,
        profile_url=payload.profile_url,
        steam_id64=payload.steam_id64,
    )


# ---------------------------------------------------------------------------
# Google Sheets / CSV / XLSX Import & Read-Only Sync
# ---------------------------------------------------------------------------

class GoogleSheetRequest(BaseModel):
    url: str = Field(..., min_length=10, max_length=500)
    mapping_override: dict[str, str | None] | None = None
    overwrite_manual: bool = False
    default_rating: float = Field(default=55.0, ge=1.0, le=100.0)


@router.post("/imports/google-sheet/preview")
async def preview_google_sheet(payload: GoogleSheetRequest, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    csv_text, export_url = await import_service.fetch_google_sheet_csv(payload.url)
    headers, rows = import_service.parse_csv_bytes(csv_text.encode("utf-8"))
    preview = import_service.preview_spreadsheet(
        db,
        comm.id,
        headers=headers,
        rows=rows,
        mapping_override=payload.mapping_override,
        default_rating=payload.default_rating,
    )
    preview["source_url"] = payload.url
    preview["export_url"] = export_url
    return preview


@router.post("/imports/google-sheet/commit")
async def commit_google_sheet(payload: GoogleSheetRequest, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    csv_text, _ = await import_service.fetch_google_sheet_csv(payload.url)
    headers, rows = import_service.parse_csv_bytes(csv_text.encode("utf-8"))
    return import_service.commit_spreadsheet_import(
        db,
        comm.id,
        source_type="GOOGLE_SHEET",
        source_label="Google Sheet",
        source_url=payload.url,
        headers=headers,
        rows=rows,
        mapping_override=payload.mapping_override,
        overwrite_manual=payload.overwrite_manual,
        default_rating=payload.default_rating,
    )


@router.post("/imports/file/preview")
async def preview_file_import(
    file: UploadFile = File(...),
    mapping_json: str | None = Form(default=None),
    default_rating: float = Form(default=55.0),
    db: Session = Depends(get_db),
):
    comm = player_service.get_or_create_default_community(db)
    raw = await file.read()
    fname = (file.filename or "").lower()
    if fname.endswith(".xlsx"):
        headers, rows = import_service.parse_xlsx_bytes(raw)
    elif fname.endswith(".csv"):
        headers, rows = import_service.parse_csv_bytes(raw)
    else:
        raise HTTPException(status_code=422, detail="Unsupported file type. Upload a .csv or .xlsx file.")
    mapping = json.loads(mapping_json) if mapping_json else None
    return import_service.preview_spreadsheet(
        db, comm.id, headers=headers, rows=rows, mapping_override=mapping, default_rating=default_rating
    )


@router.post("/imports/file/commit")
async def commit_file_import(
    file: UploadFile = File(...),
    mapping_json: str | None = Form(default=None),
    overwrite_manual: bool = Form(default=False),
    default_rating: float = Form(default=55.0),
    db: Session = Depends(get_db),
):
    comm = player_service.get_or_create_default_community(db)
    raw = await file.read()
    fname = (file.filename or "upload.csv").lower()
    if fname.endswith(".xlsx"):
        headers, rows = import_service.parse_xlsx_bytes(raw)
        stype = "XLSX"
    elif fname.endswith(".csv"):
        headers, rows = import_service.parse_csv_bytes(raw)
        stype = "CSV"
    else:
        raise HTTPException(status_code=422, detail="Unsupported file type. Upload a .csv or .xlsx file.")
    mapping = json.loads(mapping_json) if mapping_json else None
    return import_service.commit_spreadsheet_import(
        db,
        comm.id,
        source_type=stype,
        source_label=file.filename or stype,
        source_url=None,
        headers=headers,
        rows=rows,
        mapping_override=mapping,
        overwrite_manual=overwrite_manual,
        default_rating=default_rating,
    )


@router.get("/imports/history")
def import_history(db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return import_service.list_import_history(db, comm.id)


@router.post("/imports/{import_id}/sync")
async def sync_import(import_id: str, overwrite_manual: bool = False, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    job = db.scalar(
        select(SpreadsheetImport).where(
            SpreadsheetImport.id == import_id, SpreadsheetImport.community_id == comm.id
        )
    )
    if not job or not job.source_url:
        raise HTTPException(status_code=404, detail="Syncable Google Sheet import not found.")

    job.last_attempted_sync_at = datetime.now(timezone.utc)
    try:
        csv_text, _ = await import_service.fetch_google_sheet_csv(job.source_url)
    except HTTPException as exc:
        job.sync_status = "UNAVAILABLE"
        db.commit()
        raise exc

    headers, rows = import_service.parse_csv_bytes(csv_text.encode("utf-8"))
    mapping = json.loads(job.mapping_json)
    result = import_service.commit_spreadsheet_import(
        db,
        comm.id,
        source_type="GOOGLE_SHEET",
        source_label=job.source_label,
        source_url=job.source_url,
        headers=headers,
        rows=rows,
        mapping_override=mapping,
        overwrite_manual=overwrite_manual,
    )
    result["changed_from_previous"] = result["content_hash"] != job.content_hash
    return result


# ---------------------------------------------------------------------------
# Trust & Account Watch + Activity Feed
# ---------------------------------------------------------------------------

class WatchlistAddRequest(BaseModel):
    community_player_id: str
    reason: str = Field(..., min_length=2, max_length=500)
    source_url: str | None = None


class WatchlistReviewRequest(BaseModel):
    status: str = Field(..., pattern="^(WATCHING|REVIEWED|DISMISSED)$")
    review_note: str | None = None
    reviewed_by: str = "Host"


class TrustReportRequest(BaseModel):
    community_player_id: str
    summary: str = Field(..., min_length=3, max_length=500)
    source_url: str | None = None
    category: str = "COMMUNITY_REPORT"


@router.get("/trust/overview")
def trust_overview(db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return trust_service.get_trust_overview(db, comm.id)


@router.post("/trust/players/{player_id}/check")
async def run_trust_check(player_id: str, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return await trust_service.run_trust_check_for_player(db, comm.id, player_id)


@router.post("/trust/watchlist")
def add_watchlist(payload: WatchlistAddRequest, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return trust_service.add_watchlist_entry(
        db, comm.id, payload.community_player_id, payload.reason, payload.source_url
    )


@router.patch("/trust/watchlist/{entry_id}")
def review_watchlist(entry_id: str, payload: WatchlistReviewRequest, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return trust_service.review_watchlist_entry(
        db, comm.id, entry_id, payload.status, payload.review_note, payload.reviewed_by
    )


@router.post("/trust/reports")
def add_trust_report(payload: TrustReportRequest, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return trust_service.add_community_trust_report(
        db, comm.id, payload.community_player_id, payload.summary, payload.source_url, payload.category
    )


@router.post("/trust/refresh-watched")
async def refresh_watched(db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    entries = db.scalars(
        select(WatchlistEntry).where(
            WatchlistEntry.community_id == comm.id, WatchlistEntry.status == "WATCHING"
        )
    ).all()
    checked = 0
    for w in entries[:15]:
        cp = db.scalar(
            select(CommunityPlayer).where(
                CommunityPlayer.community_id == comm.id,
                CommunityPlayer.player_id == w.player_id,
                CommunityPlayer.is_active.is_(True),
            )
        )
        if cp and cp.player.steam_id64:
            await trust_service.run_trust_check_for_player(db, comm.id, cp.id)
            checked += 1
    return {"checked": checked, "overview": trust_service.get_trust_overview(db, comm.id)}
