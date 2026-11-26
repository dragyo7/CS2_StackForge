from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    AdoptAlternativeRequest,
    FeedbackCreate,
    FeedbackResolve,
    FinalizeRequest,
    GenerateRequest,
    LockPlayerRequest,
    MatchResultCreate,
    MatchRoomCreate,
    MatchRoomOut,
    PairConstraintCreate,
    PlayerOut,
    RoomRosterUpdate,
    RoomSlotReplace,
    SwapCommitRequest,
    SwapPreviewRequest,
    SwapPreviewResponse,
)
from app.services import match_result_service, player_service, room_service

router = APIRouter(prefix="/api", tags=["rooms"])


@router.get("/rooms", response_model=list[MatchRoomOut])
def list_rooms(db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return room_service.list_rooms(db, comm.id)


@router.post("/rooms", response_model=MatchRoomOut, status_code=201)
def create_room(payload: MatchRoomCreate, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return room_service.create_room(db, comm.id, payload.title)


@router.get("/rooms/{room_id}", response_model=MatchRoomOut)
def get_room(room_id: str, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return room_service.get_room(db, comm.id, room_id)


@router.put("/rooms/{room_id}/roster", response_model=MatchRoomOut)
def set_roster(room_id: str, payload: RoomRosterUpdate, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return room_service.set_room_roster(db, comm.id, room_id, payload.community_player_ids)


@router.post("/rooms/{room_id}/replace-player", response_model=MatchRoomOut)
def replace_player(room_id: str, payload: RoomSlotReplace, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return room_service.replace_room_player(db, comm.id, room_id, payload.remove_player_id, payload.add_player_id)


@router.put("/rooms/{room_id}/players/{player_id}/lock", response_model=MatchRoomOut)
def lock_player(room_id: str, player_id: str, payload: LockPlayerRequest, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return room_service.set_player_lock(db, comm.id, room_id, player_id, payload.locked_team)


@router.post("/rooms/{room_id}/constraints", response_model=MatchRoomOut)
def add_constraint(room_id: str, payload: PairConstraintCreate, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return room_service.add_pair_constraint(db, comm.id, room_id, payload)


@router.delete("/rooms/{room_id}/constraints/{constraint_id}", response_model=MatchRoomOut)
def remove_constraint(room_id: str, constraint_id: str, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return room_service.remove_pair_constraint(db, comm.id, room_id, constraint_id)


@router.post("/rooms/{room_id}/preflight", response_model=list[PlayerOut])
async def run_room_preflight(room_id: str, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    room = room_service.get_room(db, comm.id, room_id)
    ids = [entry.player.id for entry in room.roster]
    return await player_service.run_preflight_for_players(db, comm.id, ids)


@router.post("/rooms/{room_id}/generate", response_model=MatchRoomOut)
def generate_teams(room_id: str, payload: GenerateRequest, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return room_service.generate_proposal(
        db, comm.id, room_id, seed=payload.seed, is_regenerate=False, force_cycle=payload.force_cycle
    )


@router.post("/rooms/{room_id}/regenerate", response_model=MatchRoomOut)
def regenerate_teams(room_id: str, payload: GenerateRequest, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return room_service.generate_proposal(
        db, comm.id, room_id, seed=payload.seed, is_regenerate=True, force_cycle=payload.force_cycle
    )


@router.post("/rooms/{room_id}/swap-preview", response_model=SwapPreviewResponse)
def swap_preview(room_id: str, payload: SwapPreviewRequest, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return room_service.preview_swap(db, comm.id, room_id, payload)


@router.post("/rooms/{room_id}/swap", response_model=MatchRoomOut)
def commit_swap(room_id: str, payload: SwapCommitRequest, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return room_service.commit_swap(db, comm.id, room_id, payload)


@router.post("/rooms/{room_id}/proposals/{generation_id}/adopt-alternative", response_model=MatchRoomOut)
def adopt_alternative(
    room_id: str, generation_id: str, payload: AdoptAlternativeRequest, db: Session = Depends(get_db)
) -> MatchRoomOut:
    comm = player_service.get_or_create_default_community(db)
    return room_service.adopt_alternative(db, comm.id, room_id, generation_id, payload.partition_key)


@router.post("/rooms/{room_id}/proposals/{generation_id}/restore", response_model=MatchRoomOut)
def restore_proposal(room_id: str, generation_id: str, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return room_service.restore_proposal(db, comm.id, room_id, generation_id)


@router.post("/rooms/{room_id}/proposals/{generation_id}/feedback", response_model=MatchRoomOut)
def add_feedback(
    room_id: str, generation_id: str, payload: FeedbackCreate, db: Session = Depends(get_db)
):
    comm = player_service.get_or_create_default_community(db)
    return room_service.add_feedback(db, comm.id, room_id, generation_id, payload)


@router.post("/rooms/{room_id}/feedback/{feedback_id}/resolve", response_model=MatchRoomOut)
def resolve_feedback(room_id: str, feedback_id: str, payload: FeedbackResolve, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return room_service.resolve_feedback(db, comm.id, room_id, feedback_id, payload)


@router.post("/rooms/{room_id}/finalize", response_model=MatchRoomOut)
def finalize_room(room_id: str, payload: FinalizeRequest, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return room_service.finalize_room(db, comm.id, room_id, payload)


@router.post("/rooms/{room_id}/reopen", response_model=MatchRoomOut)
def reopen_room(room_id: str, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return room_service.reopen_room(db, comm.id, room_id)


@router.post("/rooms/{room_id}/played", response_model=MatchRoomOut)
def mark_played(room_id: str, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    match_result_service.mark_room_played(db, comm.id, room_id)
    return room_service.get_room(db, comm.id, room_id)


@router.post("/rooms/{room_id}/result", response_model=MatchRoomOut, status_code=201)
def record_result(room_id: str, payload: MatchResultCreate, db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    match_result_service.record_match_result(db, comm.id, room_id, payload)
    return room_service.get_room(db, comm.id, room_id)


@router.get("/standings/community")
def community_standings(db: Session = Depends(get_db)):
    comm = player_service.get_or_create_default_community(db)
    return match_result_service.get_community_standings(db, comm.id)


@router.get("/lineups/{share_slug}")
def get_shared_lineup(share_slug: str, db: Session = Depends(get_db)):
    return room_service.get_shared_lineup(db, share_slug)
