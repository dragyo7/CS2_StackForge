from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    BulkImportRequest,
    BulkImportResponse,
    PlayerCardSettingsUpdate,
    PlayerCompareOut,
    PlayerCreate,
    PlayerOut,
    PlayerProfileOut,
    PlayerUpdate,
    RefreshProfileResponse,
    StatSnapshotCreate,
)
from app.services import player_service

router = APIRouter(prefix="/api/players", tags=["players"])


@router.get("", response_model=list[PlayerOut])
def list_players(
    q: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    comm = player_service.get_or_create_default_community(db)
    return player_service.list_players(db, comm.id, query=q, include_archived=include_archived)


@router.post("", response_model=PlayerOut, status_code=201)
async def create_player(payload: PlayerCreate, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return await player_service.create_player_with_resolution(db, comm.id, payload)


@router.post("/refresh-all")
async def refresh_all(force: bool = Query(default=False), db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return await player_service.refresh_all_players(db, comm.id, force=force)


@router.post("/{player_id}/archive", response_model=PlayerOut)
def archive_player(player_id: str, archived: bool = Query(default=True), db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return player_service.archive_player(db, comm.id, player_id, archived=archived)


@router.get("/compare", response_model=PlayerCompareOut)
def compare_players(a: str = Query(...), b: str = Query(...), db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return player_service.compare_players(db, comm.id, a, b)


@router.get("/{player_id}/profile", response_model=PlayerProfileOut)
def get_player_profile(player_id: str, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return player_service.get_player_profile(db, comm.id, player_id)


@router.post("/{player_id}/refresh", response_model=RefreshProfileResponse)
async def refresh_player_profile(
    player_id: str, force: bool = Query(default=False), db: Session = Depends(get_db)
):
    comm = player_service.get_or_create_default_community(db)
    return await player_service.refresh_player_profile(db, comm.id, player_id, force=force)


@router.post("/{player_id}/stats", response_model=PlayerProfileOut, status_code=201)
def add_stat_snapshot(player_id: str, payload: StatSnapshotCreate, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return player_service.add_stat_snapshot(db, comm.id, player_id, payload)


@router.patch("/{player_id}/card-settings", response_model=PlayerProfileOut)
def update_card_settings(
    player_id: str, payload: PlayerCardSettingsUpdate, db: Session = Depends(get_db)
):
    comm = player_service.get_or_create_default_community(db)
    return player_service.update_card_settings(db, comm.id, player_id, payload)


@router.patch("/{player_id}", response_model=PlayerOut)
def update_player(player_id: str, payload: PlayerUpdate, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return player_service.update_player(db, comm.id, player_id, payload)


@router.delete("/{player_id}", status_code=204)
def delete_player(player_id: str, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    player_service.delete_player(db, comm.id, player_id)


@router.post("/bulk-import", response_model=BulkImportResponse)
async def bulk_import(payload: BulkImportRequest, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return await player_service.bulk_import_players(db, comm.id, payload)


@router.post("/seed-demo", response_model=list[PlayerOut])
def seed_demo(db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return player_service.seed_demo_players(db, comm.id)


@router.post("/{player_id}/preflight", response_model=list[PlayerOut])
async def preflight_single(player_id: str, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return await player_service.run_preflight_for_players(db, comm.id, [player_id])
