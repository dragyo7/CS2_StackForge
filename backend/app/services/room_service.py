from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    AuditEvent,
    CommunityPlayer,
    FinalizedLineup,
    GenerationFeedback,
    MatchRoom,
    MatchRoomPlayer,
    PlayerStatSnapshot,
    TeamConstraint,
    TeamGeneration,
)
from app.optimizer.engine import (
    ALGORITHM_VERSION,
    MAP_POOL_VERSION,
    AllSplitsExhaustedError,
    TeamConstraints,
    UnsatisfiableConstraintsError,
    build_explanation,
    evaluate_split,
    optimize_teams,
)
from app.optimizer.normalizer import NORMALIZER_VERSION, PlayerInput, normalize_player
from app.schemas import (
    FeedbackCreate,
    FeedbackOut,
    FeedbackResolve,
    FinalizedLineupOut,
    FinalizeRequest,
    MatchRoomOut,
    PairConstraintCreate,
    PairConstraintOut,
    ProposalAlternativeOut,
    ProposalOut,
    RoomPlayerOut,
    SwapCommitRequest,
    SwapPreviewRequest,
    SwapPreviewResponse,
)
from app.services.player_service import build_player_input, to_player_out


def _load_room(db: Session, community_id: str, room_id: str) -> MatchRoom:
    db.expire_all()
    room = db.scalar(
        select(MatchRoom)
        .options(
            joinedload(MatchRoom.roster_entries)
            .joinedload(MatchRoomPlayer.community_player)
            .joinedload(CommunityPlayer.player),
            joinedload(MatchRoom.constraints),
            joinedload(MatchRoom.proposals).joinedload(TeamGeneration.feedback_items),
        )
        .where(MatchRoom.id == room_id, MatchRoom.community_id == community_id)
        .execution_options(populate_existing=True)
    )
    if not room:
        raise HTTPException(status_code=404, detail="Match room not found.")
    return room


def _to_proposal_out(gen: TeamGeneration) -> ProposalOut:
    return ProposalOut(
        id=gen.id,
        room_id=gen.room_id,
        proposal_number=gen.proposal_number,
        parent_generation_id=gen.parent_generation_id,
        action_type=gen.action_type,
        algorithm_version=gen.algorithm_version,
        normalizer_version=gen.normalizer_version,
        map_pool_version=gen.map_pool_version,
        seed=gen.seed,
        partition_key=gen.partition_key,
        team_a_ids=json.loads(gen.team_a_ids_json),
        team_b_ids=json.loads(gen.team_b_ids_json),
        team_a_strength=gen.team_a_strength,
        team_b_strength=gen.team_b_strength,
        strength_diff=gen.strength_diff,
        objective_score=gen.objective_score,
        objective_components=json.loads(gen.objective_components_json),
        explanation=json.loads(gen.explanation_json),
        alternatives=[ProposalAlternativeOut(**a) for a in json.loads(gen.alternatives_json)],
        input_snapshot=json.loads(gen.input_snapshot_json),
        constraints_snapshot=json.loads(gen.constraints_snapshot_json),
        feedback=[
            FeedbackOut(
                id=fb.id,
                generation_id=fb.generation_id,
                community_player_id=fb.community_player_id,
                target_player_id=fb.target_player_id,
                feedback_type=fb.feedback_type,
                reason=fb.reason,
                status=fb.status,
                host_note=fb.host_note,
                created_at=fb.created_at,
                resolved_at=fb.resolved_at,
            )
            for fb in gen.feedback_items
        ],
        created_at=gen.created_at,
    )


def _to_finalized_out(fin: FinalizedLineup, prop: TeamGeneration) -> FinalizedLineupOut:
    snap = json.loads(fin.lineup_snapshot_json)
    return FinalizedLineupOut(
        id=fin.id,
        room_id=fin.room_id,
        generation_id=fin.generation_id,
        proposal_number=prop.proposal_number,
        share_slug=fin.share_slug,
        team_a=snap["team_a"],
        team_b=snap["team_b"],
        team_a_strength=snap["team_a_strength"],
        team_b_strength=snap["team_b_strength"],
        strength_diff=snap["strength_diff"],
        discord_text=fin.discord_text,
        finalized_by=fin.finalized_by,
        finalized_at=fin.finalized_at,
    )


def to_room_out(db: Session, room: MatchRoom) -> MatchRoomOut:
    roster = [
        RoomPlayerOut(
            slot_order=entry.slot_order,
            locked_team=entry.locked_team,
            player=to_player_out(db, entry.community_player),
        )
        for entry in sorted(room.roster_entries, key=lambda r: r.slot_order)
    ]
    constraints = [
        PairConstraintOut(
            id=c.id,
            constraint_type=c.constraint_type,
            player_a_id=c.player_a_id,
            player_b_id=c.player_b_id,
        )
        for c in room.constraints
    ]
    proposals = [_to_proposal_out(g) for g in sorted(room.proposals, key=lambda g: g.proposal_number, reverse=True)]
    fin_out: FinalizedLineupOut | None = None
    fin = db.scalar(select(FinalizedLineup).where(FinalizedLineup.room_id == room.id))
    if fin:
        prop = next((p for p in room.proposals if p.id == fin.generation_id), None)
        if prop:
            fin_out = _to_finalized_out(fin, prop)

    return MatchRoomOut(
        id=room.id,
        community_id=room.community_id,
        title=room.title,
        status=room.status,
        version=room.version,
        share_slug=room.share_slug,
        finalized_proposal_id=room.finalized_proposal_id,
        selected_count=len(roster),
        roster=roster,
        constraints=constraints,
        proposals=proposals,
        finalized_lineup=fin_out,
        created_at=room.created_at,
        updated_at=room.updated_at,
    )


def list_rooms(db: Session, community_id: str) -> list[MatchRoomOut]:
    rooms = db.scalars(
        select(MatchRoom)
        .options(
            joinedload(MatchRoom.roster_entries)
            .joinedload(MatchRoomPlayer.community_player)
            .joinedload(CommunityPlayer.player),
            joinedload(MatchRoom.constraints),
            joinedload(MatchRoom.proposals).joinedload(TeamGeneration.feedback_items),
        )
        .where(MatchRoom.community_id == community_id)
        .order_by(MatchRoom.updated_at.desc())
    ).unique().all()
    return [to_room_out(db, r) for r in rooms]


def create_room(db: Session, community_id: str, title: str) -> MatchRoomOut:
    slug = secrets.token_urlsafe(6).replace("_", "").replace("-", "")[:10]
    room = MatchRoom(community_id=community_id, title=title.strip(), status="DRAFT", share_slug=slug)
    db.add(room)
    db.flush()
    db.add(
        AuditEvent(
            community_id=community_id,
            room_id=room.id,
            event_type="ROOM_CREATED",
            payload_json=json.dumps({"title": room.title}),
        )
    )
    db.commit()
    return to_room_out(db, _load_room(db, community_id, room.id))


def get_room(db: Session, community_id: str, room_id: str) -> MatchRoomOut:
    return to_room_out(db, _load_room(db, community_id, room_id))


def set_room_roster(db: Session, community_id: str, room_id: str, player_ids: list[str]) -> MatchRoomOut:
    room = _load_room(db, community_id, room_id)
    if room.status == "FINALIZED":
        raise HTTPException(status_code=409, detail="Room is finalized. Reopen the room before changing the roster.")

    if len(player_ids) > 10:
        raise HTTPException(status_code=422, detail="A 5v5 match room cannot have more than 10 players.")
    if len(set(player_ids)) != len(player_ids):
        raise HTTPException(status_code=422, detail="Duplicate player detected. Each player can only occupy one slot.")

    if player_ids:
        found = db.scalars(
            select(CommunityPlayer).where(
                CommunityPlayer.community_id == community_id,
                CommunityPlayer.id.in_(player_ids),
                CommunityPlayer.is_active.is_(True),
            )
        ).all()
        if len(found) != len(player_ids):
            raise HTTPException(status_code=404, detail="One or more selected players do not exist in this community.")

    existing_locks = {e.community_player_id: e.locked_team for e in room.roster_entries}
    room.roster_entries.clear()
    db.flush()

    selected_set = set(player_ids)
    # Drop pair constraints referencing removed players
    room.constraints[:] = [
        c for c in room.constraints if c.player_a_id in selected_set and c.player_b_id in selected_set
    ]

    for idx, pid in enumerate(player_ids, start=1):
        room.roster_entries.append(
            MatchRoomPlayer(
                room_id=room.id,
                community_player_id=pid,
                slot_order=idx,
                locked_team=existing_locks.get(pid),
            )
        )

    room.status = "READY_TO_GENERATE" if len(player_ids) == 10 else "DRAFT"
    room.version += 1
    db.commit()
    return to_room_out(db, _load_room(db, community_id, room.id))


def replace_room_player(
    db: Session, community_id: str, room_id: str, remove_player_id: str, add_player_id: str
) -> MatchRoomOut:
    room = _load_room(db, community_id, room_id)
    if room.status == "FINALIZED":
        raise HTTPException(status_code=409, detail="Room is finalized. Reopen the room before replacing a player.")

    current_ids = [e.community_player_id for e in sorted(room.roster_entries, key=lambda r: r.slot_order)]
    if remove_player_id not in current_ids:
        raise HTTPException(status_code=404, detail="Player to remove is not in this room.")
    if add_player_id in current_ids:
        raise HTTPException(status_code=409, detail="Replacement player is already in this room.")

    new_ids = [add_player_id if pid == remove_player_id else pid for pid in current_ids]
    return set_room_roster(db, community_id, room_id, new_ids)


def set_player_lock(
    db: Session, community_id: str, room_id: str, player_id: str, locked_team: str | None
) -> MatchRoomOut:
    room = _load_room(db, community_id, room_id)
    if room.status == "FINALIZED":
        raise HTTPException(status_code=409, detail="Room is finalized. Reopen before editing locks.")

    entry = next((e for e in room.roster_entries if e.community_player_id == player_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Player is not in this match room.")

    entry.locked_team = locked_team
    room.version += 1
    db.commit()
    return to_room_out(db, _load_room(db, community_id, room.id))


def add_pair_constraint(
    db: Session, community_id: str, room_id: str, payload: PairConstraintCreate
) -> MatchRoomOut:
    room = _load_room(db, community_id, room_id)
    if room.status == "FINALIZED":
        raise HTTPException(status_code=409, detail="Room is finalized. Reopen before editing constraints.")
    if payload.player_a_id == payload.player_b_id:
        raise HTTPException(status_code=422, detail="Pair constraint requires two different players.")

    roster_ids = {e.community_player_id for e in room.roster_entries}
    if payload.player_a_id not in roster_ids or payload.player_b_id not in roster_ids:
        raise HTTPException(status_code=422, detail="Both players must be in the match room.")

    pair_set = {payload.player_a_id, payload.player_b_id}
    for c in room.constraints:
        if {c.player_a_id, c.player_b_id} == pair_set:
            c.constraint_type = payload.constraint_type
            db.commit()
            return to_room_out(db, _load_room(db, community_id, room.id))

    room.constraints.append(
        TeamConstraint(
            room_id=room.id,
            constraint_type=payload.constraint_type,
            player_a_id=payload.player_a_id,
            player_b_id=payload.player_b_id,
        )
    )
    room.version += 1
    db.commit()
    return to_room_out(db, _load_room(db, community_id, room.id))


def remove_pair_constraint(db: Session, community_id: str, room_id: str, constraint_id: str) -> MatchRoomOut:
    room = _load_room(db, community_id, room_id)
    if room.status == "FINALIZED":
        raise HTTPException(status_code=409, detail="Room is finalized. Reopen before editing constraints.")
    room.constraints[:] = [c for c in room.constraints if c.id != constraint_id]
    room.version += 1
    db.commit()
    return to_room_out(db, _load_room(db, community_id, room.id))


def _build_player_inputs(db: Session, room: MatchRoom) -> tuple[list[PlayerInput], TeamConstraints, list[dict]]:
    inputs: list[PlayerInput] = []
    snapshot: list[dict] = []
    locked_a: set[str] = set()
    locked_b: set[str] = set()
    now = datetime.now(timezone.utc)

    for entry in sorted(room.roster_entries, key=lambda r: r.slot_order):
        cp = entry.community_player
        p = cp.player
        pin, eff = build_player_input(db, cp)
        inputs.append(pin)
        norm = normalize_player(pin)
        snapshot.append(
            {
                "id": cp.id,
                "display_name": cp.display_name,
                "steam_id64": p.steam_id64,
                "identity_status": p.identity_status,
                "manual_rating": None,
                "premier_rating": cp.premier_rating,
                "faceit_elo": cp.faceit_elo,
                "faceit_level": cp.faceit_level,
                "leetify_rating": cp.leetify_rating,
                "aim_rating": eff["aim_rating"],
                "utility_rating": eff["utility_rating"],
                "positioning_rating": eff["positioning_rating"],
                "preaim": eff["preaim"],
                "reaction_time_ms": eff["reaction_time_ms"],
                "spotted_accuracy": eff["spotted_accuracy"],
                "spray_accuracy": eff["spray_accuracy"],
                "hs_pct": eff["hs_pct"],
                "recent_form": cp.recent_form,
                "primary_role": cp.primary_role,
                "data_status": norm.data_status,
                "normalized_strength": norm.normalized_strength,
                "strength_band": norm.strength_band,
                "confidence": norm.confidence,
                "sources_used": norm.sources_used,
                "missing_sources": norm.missing_sources,
                "adr": eff["adr"],
                "kd_ratio": eff["kd_ratio"],
                "kast": eff["kast"],
                "opening_duel_pct": eff["opening_duel_pct"],
                "trade_kills_per_match": eff["trade_kills_per_match"],
                "traded_deaths_pct": eff["traded_deaths_pct"],
                "utility_damage_per_round": eff["utility_damage_per_round"],
                "flash_assists_per_round": eff["flash_assists_per_round"],
                "enemies_flashed_per_round": eff["enemies_flashed_per_round"],
                "clutch_win_pct": eff["clutch_win_pct"],
                "consistency_score": eff["consistency_score"],
                "win_rate": eff["win_rate"],
                "stats_sample_size": eff["stats_sample_size"],
                "stats_stale": eff["stats_stale"],
                "locked_team": entry.locked_team,
            }
        )
        if entry.locked_team == "A":
            locked_a.add(cp.id)
        elif entry.locked_team == "B":
            locked_b.add(cp.id)

    together = tuple((c.player_a_id, c.player_b_id) for c in room.constraints if c.constraint_type == "TOGETHER")
    opponent = tuple((c.player_a_id, c.player_b_id) for c in room.constraints if c.constraint_type == "OPPONENT")
    constraints = TeamConstraints(
        locked_a=frozenset(locked_a),
        locked_b=frozenset(locked_b),
        together_pairs=together,
        opponent_pairs=opponent,
    )
    return inputs, constraints, snapshot


def _constraints_snapshot(constraints: TeamConstraints) -> dict:
    return {
        "locked_a": sorted(constraints.locked_a),
        "locked_b": sorted(constraints.locked_b),
        "together_pairs": [list(p) for p in constraints.together_pairs],
        "opponent_pairs": [list(p) for p in constraints.opponent_pairs],
    }


def generate_proposal(
    db: Session,
    community_id: str,
    room_id: str,
    seed: int = 42,
    is_regenerate: bool = False,
    force_cycle: bool = False,
) -> MatchRoomOut:
    room = _load_room(db, community_id, room_id)
    if room.status == "FINALIZED":
        raise HTTPException(status_code=409, detail="Room is finalized. Reopen the room to generate a new proposal.")
    if len(room.roster_entries) != 10:
        raise HTTPException(
            status_code=422,
            detail=f"Exactly 10 unique players are required to generate teams (currently {len(room.roster_entries)}/10).",
        )

    inputs, constraints, input_snapshot = _build_player_inputs(db, room)
    exclude_keys: set[str] = set()
    if is_regenerate and not force_cycle:
        exclude_keys = {p.partition_key for p in room.proposals}

    try:
        result = optimize_teams(
            players=inputs,
            constraints=constraints,
            seed=seed,
            exclude_partition_keys=exclude_keys,
        )
    except UnsatisfiableConstraintsError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "CONSTRAINTS_UNSATISFIABLE", "message": exc.message, "reasons": exc.reasons},
        ) from exc
    except AllSplitsExhaustedError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "ALL_SPLITS_EXHAUSTED", "message": exc.message, "valid_count": exc.valid_count},
        ) from exc

    next_number = (max((p.proposal_number for p in room.proposals), default=0)) + 1
    parent_id = max(room.proposals, key=lambda p: p.proposal_number).id if room.proposals else None

    alternatives_payload = [
        {
            "partition_key": alt.partition_key,
            "team_a_ids": list(alt.team_a_ids),
            "team_b_ids": list(alt.team_b_ids),
            "team_a_strength": alt.team_a_strength,
            "team_b_strength": alt.team_b_strength,
            "strength_diff": alt.strength_diff,
            "objective_score": alt.objective_score,
            "role_summary": alt.role_summary,
        }
        for alt in result.alternatives
    ]

    gen = TeamGeneration(
        room_id=room.id,
        proposal_number=next_number,
        parent_generation_id=parent_id,
        action_type="REGENERATE" if is_regenerate else "INITIAL",
        algorithm_version=result.algorithm_version,
        normalizer_version=result.normalizer_version,
        map_pool_version=result.map_pool_version,
        seed=result.seed,
        partition_key=result.recommended.partition_key,
        team_a_ids_json=json.dumps(list(result.recommended.team_a_ids)),
        team_b_ids_json=json.dumps(list(result.recommended.team_b_ids)),
        team_a_strength=result.recommended.team_a_strength,
        team_b_strength=result.recommended.team_b_strength,
        strength_diff=result.recommended.strength_diff,
        objective_score=result.recommended.objective_score,
        input_snapshot_json=json.dumps(input_snapshot),
        constraints_snapshot_json=json.dumps(_constraints_snapshot(constraints)),
        objective_components_json=json.dumps(result.recommended.objective_components),
        explanation_json=json.dumps(result.explanation),
        alternatives_json=json.dumps(alternatives_payload),
    )
    db.add(gen)
    room.status = "PROPOSED"
    room.version += 1
    db.add(
        AuditEvent(
            community_id=community_id,
            room_id=room.id,
            event_type="PROPOSAL_GENERATED",
            payload_json=json.dumps({"proposal_number": next_number, "action": gen.action_type, "seed": seed}),
        )
    )
    db.commit()
    return to_room_out(db, _load_room(db, community_id, room.id))


def _snapshot_to_normalized(snapshot: list[dict]) -> tuple[dict, dict[str, PlayerInput]]:
    inputs: dict[str, PlayerInput] = {}
    normalized: dict = {}
    for item in snapshot:
        pin = PlayerInput(
            community_player_id=item["id"],
            display_name=item["display_name"],
            steam_id64=item.get("steam_id64"),
            identity_status=item.get("identity_status", "MANUAL_ONLY"),
            manual_rating=None,
            premier_rating=item.get("premier_rating"),
            faceit_elo=item.get("faceit_elo"),
            faceit_level=item.get("faceit_level"),
            leetify_rating=item.get("leetify_rating"),
            aim_rating=item.get("aim_rating"),
            utility_rating=item.get("utility_rating"),
            positioning_rating=item.get("positioning_rating"),
            preaim=item.get("preaim"),
            reaction_time_ms=item.get("reaction_time_ms"),
            spotted_accuracy=item.get("spotted_accuracy"),
            spray_accuracy=item.get("spray_accuracy"),
            hs_pct=item.get("hs_pct"),
            recent_form=item.get("recent_form"),
            primary_role=item.get("primary_role"),
            adr=item.get("adr"),
            kd_ratio=item.get("kd_ratio"),
            kast=item.get("kast"),
            opening_duel_pct=item.get("opening_duel_pct"),
            trade_kills_per_match=item.get("trade_kills_per_match"),
            traded_deaths_pct=item.get("traded_deaths_pct"),
            utility_damage_per_round=item.get("utility_damage_per_round"),
            flash_assists_per_round=item.get("flash_assists_per_round"),
            enemies_flashed_per_round=item.get("enemies_flashed_per_round"),
            clutch_win_pct=item.get("clutch_win_pct"),
            consistency_score=item.get("consistency_score"),
            win_rate=item.get("win_rate"),
            stats_sample_size=item.get("stats_sample_size") or 0,
            stats_stale=bool(item.get("stats_stale", False)),
        )
        inputs[pin.community_player_id] = pin
        normalized[pin.community_player_id] = normalize_player(pin)
    return normalized, inputs


def preview_swap(db: Session, community_id: str, room_id: str, req: SwapPreviewRequest) -> SwapPreviewResponse:
    room = _load_room(db, community_id, room_id)
    gen = next((p for p in room.proposals if p.id == req.generation_id), None)
    if not gen:
        raise HTTPException(status_code=404, detail="Proposal not found.")

    team_a = json.loads(gen.team_a_ids_json)
    team_b = json.loads(gen.team_b_ids_json)

    if req.player_a_id in team_a and req.player_b_id in team_b:
        new_a = [req.player_b_id if pid == req.player_a_id else pid for pid in team_a]
        new_b = [req.player_a_id if pid == req.player_b_id else pid for pid in team_b]
    elif req.player_b_id in team_a and req.player_a_id in team_b:
        new_a = [req.player_a_id if pid == req.player_b_id else pid for pid in team_a]
        new_b = [req.player_b_id if pid == req.player_a_id else pid for pid in team_b]
    else:
        raise HTTPException(status_code=422, detail="Swap requires one player from Team A and one player from Team B.")

    normalized, _ = _snapshot_to_normalized(json.loads(gen.input_snapshot_json))
    after = evaluate_split(tuple(new_a), tuple(new_b), normalized, gen.seed)

    return SwapPreviewResponse(
        before_team_a_strength=gen.team_a_strength,
        before_team_b_strength=gen.team_b_strength,
        before_strength_diff=gen.strength_diff,
        before_objective=gen.objective_score,
        after_team_a_strength=after.team_a_strength,
        after_team_b_strength=after.team_b_strength,
        after_strength_diff=after.strength_diff,
        after_objective=after.objective_score,
        strength_diff_delta=round(after.strength_diff - gen.strength_diff, 2),
        objective_delta=round(after.objective_score - gen.objective_score, 3),
        after_team_a_ids=list(after.team_a_ids),
        after_team_b_ids=list(after.team_b_ids),
    )


def commit_swap(db: Session, community_id: str, room_id: str, req: SwapCommitRequest) -> MatchRoomOut:
    room = _load_room(db, community_id, room_id)
    if room.status == "FINALIZED":
        raise HTTPException(status_code=409, detail="Room is finalized. Reopen before committing a swap.")
    gen = next((p for p in room.proposals if p.id == req.generation_id), None)
    if not gen:
        raise HTTPException(status_code=404, detail="Source proposal not found.")

    team_a = json.loads(gen.team_a_ids_json)
    team_b = json.loads(gen.team_b_ids_json)
    if req.player_a_id in team_a and req.player_b_id in team_b:
        new_a = [req.player_b_id if pid == req.player_a_id else pid for pid in team_a]
        new_b = [req.player_a_id if pid == req.player_b_id else pid for pid in team_b]
    elif req.player_b_id in team_a and req.player_a_id in team_b:
        new_a = [req.player_a_id if pid == req.player_b_id else pid for pid in team_a]
        new_b = [req.player_b_id if pid == req.player_a_id else pid for pid in team_b]
    else:
        raise HTTPException(status_code=422, detail="Swap requires one player from Team A and one from Team B.")

    snapshot = json.loads(gen.input_snapshot_json)
    normalized, _ = _snapshot_to_normalized(snapshot)
    after = evaluate_split(tuple(new_a), tuple(new_b), normalized, gen.seed)
    c_snap = json.loads(gen.constraints_snapshot_json)
    constraints = TeamConstraints(
        locked_a=frozenset(c_snap.get("locked_a", [])),
        locked_b=frozenset(c_snap.get("locked_b", [])),
        together_pairs=tuple(tuple(p) for p in c_snap.get("together_pairs", [])),  # type: ignore[arg-type]
        opponent_pairs=tuple(tuple(p) for p in c_snap.get("opponent_pairs", [])),  # type: ignore[arg-type]
    )
    explanation = build_explanation(after, normalized, constraints, valid_count=126, alternatives_count=0)
    p1_name = normalized[req.player_a_id].display_name
    p2_name = normalized[req.player_b_id].display_name
    swap_note = f"Manual swap from Proposal #{gen.proposal_number}: {p1_name} <-> {p2_name}."
    if req.reason:
        swap_note += f" Reason: {req.reason.strip()}"
    explanation["summary"] = swap_note + " " + explanation["summary"]

    next_number = max(p.proposal_number for p in room.proposals) + 1
    new_gen = TeamGeneration(
        room_id=room.id,
        proposal_number=next_number,
        parent_generation_id=gen.id,
        action_type="SWAP",
        algorithm_version=ALGORITHM_VERSION,
        normalizer_version=NORMALIZER_VERSION,
        map_pool_version=MAP_POOL_VERSION,
        seed=gen.seed,
        partition_key=after.partition_key,
        team_a_ids_json=json.dumps(list(after.team_a_ids)),
        team_b_ids_json=json.dumps(list(after.team_b_ids)),
        team_a_strength=after.team_a_strength,
        team_b_strength=after.team_b_strength,
        strength_diff=after.strength_diff,
        objective_score=after.objective_score,
        input_snapshot_json=gen.input_snapshot_json,
        constraints_snapshot_json=gen.constraints_snapshot_json,
        objective_components_json=json.dumps(after.objective_components),
        explanation_json=json.dumps(explanation),
        alternatives_json=gen.alternatives_json,
    )
    db.add(new_gen)
    room.status = "REVIEWING"
    room.version += 1
    db.commit()
    return to_room_out(db, _load_room(db, community_id, room.id))


def adopt_alternative(
    db: Session, community_id: str, room_id: str, generation_id: str, partition_key: str
) -> MatchRoomOut:
    room = _load_room(db, community_id, room_id)
    if room.status == "FINALIZED":
        raise HTTPException(status_code=409, detail="Room is finalized. Reopen before switching proposals.")
    gen = next((p for p in room.proposals if p.id == generation_id), None)
    if not gen:
        raise HTTPException(status_code=404, detail="Proposal not found.")

    alternatives = json.loads(gen.alternatives_json)
    chosen = next((a for a in alternatives if a["partition_key"] == partition_key), None)
    if not chosen:
        raise HTTPException(status_code=404, detail="Selected alternative was not found in this proposal.")

    normalized, _ = _snapshot_to_normalized(json.loads(gen.input_snapshot_json))
    after = evaluate_split(tuple(chosen["team_a_ids"]), tuple(chosen["team_b_ids"]), normalized, gen.seed)
    c_snap = json.loads(gen.constraints_snapshot_json)
    constraints = TeamConstraints(
        locked_a=frozenset(c_snap.get("locked_a", [])),
        locked_b=frozenset(c_snap.get("locked_b", [])),
        together_pairs=tuple(tuple(p) for p in c_snap.get("together_pairs", [])),  # type: ignore[arg-type]
        opponent_pairs=tuple(tuple(p) for p in c_snap.get("opponent_pairs", [])),  # type: ignore[arg-type]
    )
    explanation = build_explanation(after, normalized, constraints, valid_count=126, alternatives_count=len(alternatives))
    explanation["summary"] = (
        f"Selected alternative split from Proposal #{gen.proposal_number}. " + explanation["summary"]
    )

    next_number = max(p.proposal_number for p in room.proposals) + 1
    new_gen = TeamGeneration(
        room_id=room.id,
        proposal_number=next_number,
        parent_generation_id=gen.id,
        action_type="ALTERNATIVE",
        algorithm_version=ALGORITHM_VERSION,
        normalizer_version=NORMALIZER_VERSION,
        map_pool_version=MAP_POOL_VERSION,
        seed=gen.seed,
        partition_key=after.partition_key,
        team_a_ids_json=json.dumps(list(after.team_a_ids)),
        team_b_ids_json=json.dumps(list(after.team_b_ids)),
        team_a_strength=after.team_a_strength,
        team_b_strength=after.team_b_strength,
        strength_diff=after.strength_diff,
        objective_score=after.objective_score,
        input_snapshot_json=gen.input_snapshot_json,
        constraints_snapshot_json=gen.constraints_snapshot_json,
        objective_components_json=json.dumps(after.objective_components),
        explanation_json=json.dumps(explanation),
        alternatives_json=gen.alternatives_json,
    )
    db.add(new_gen)
    room.status = "REVIEWING"
    room.version += 1
    db.commit()
    return to_room_out(db, _load_room(db, community_id, room.id))


def restore_proposal(db: Session, community_id: str, room_id: str, generation_id: str) -> MatchRoomOut:
    room = _load_room(db, community_id, room_id)
    if room.status == "FINALIZED":
        raise HTTPException(status_code=409, detail="Room is finalized. Reopen before restoring a proposal.")
    target = next((p for p in room.proposals if p.id == generation_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Proposal to restore not found.")

    next_number = max(p.proposal_number for p in room.proposals) + 1
    explanation = json.loads(target.explanation_json)
    explanation["summary"] = (
        f"Restored Proposal #{target.proposal_number} as Proposal #{next_number}. " + explanation.get("summary", "")
    )
    restored = TeamGeneration(
        room_id=room.id,
        proposal_number=next_number,
        parent_generation_id=target.id,
        action_type="RESTORE",
        algorithm_version=target.algorithm_version,
        normalizer_version=target.normalizer_version,
        map_pool_version=target.map_pool_version,
        seed=target.seed,
        partition_key=target.partition_key,
        team_a_ids_json=target.team_a_ids_json,
        team_b_ids_json=target.team_b_ids_json,
        team_a_strength=target.team_a_strength,
        team_b_strength=target.team_b_strength,
        strength_diff=target.strength_diff,
        objective_score=target.objective_score,
        input_snapshot_json=target.input_snapshot_json,
        constraints_snapshot_json=target.constraints_snapshot_json,
        objective_components_json=target.objective_components_json,
        explanation_json=json.dumps(explanation),
        alternatives_json=target.alternatives_json,
    )
    db.add(restored)
    room.status = "REVIEWING"
    room.version += 1
    db.commit()
    return to_room_out(db, _load_room(db, community_id, room.id))


def add_feedback(
    db: Session, community_id: str, room_id: str, generation_id: str, payload: FeedbackCreate
) -> MatchRoomOut:
    room = _load_room(db, community_id, room_id)
    gen = next((p for p in room.proposals if p.id == generation_id), None)
    if not gen:
        raise HTTPException(status_code=404, detail="Proposal not found.")

    fb = GenerationFeedback(
        room_id=room.id,
        generation_id=gen.id,
        community_player_id=payload.community_player_id,
        target_player_id=payload.target_player_id,
        feedback_type=payload.feedback_type,
        reason=payload.reason.strip(),
        status="PENDING",
    )
    db.add(fb)
    if room.status == "PROPOSED":
        room.status = "REVIEWING"
    room.version += 1
    db.commit()
    return to_room_out(db, _load_room(db, community_id, room.id))


def resolve_feedback(
    db: Session, community_id: str, room_id: str, feedback_id: str, payload: FeedbackResolve
) -> MatchRoomOut:
    room = _load_room(db, community_id, room_id)
    fb = db.scalar(
        select(GenerationFeedback).where(
            GenerationFeedback.id == feedback_id, GenerationFeedback.room_id == room.id
        )
    )
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback entry not found.")

    fb.status = payload.status
    fb.host_note = payload.host_note.strip() if payload.host_note else None
    fb.resolved_at = datetime.now(timezone.utc)
    room.version += 1
    db.commit()
    return to_room_out(db, _load_room(db, community_id, room.id))


def _format_discord_text(
    room_title: str,
    proposal_number: int,
    team_a: list[dict],
    team_b: list[dict],
    team_a_strength: float,
    team_b_strength: float,
    strength_diff: float,
    balance_indicator: str,
    share_summary: str | None = None,
) -> str:
    def fmt_player(p: dict) -> str:
        role = f" [{p['primary_role']}]" if p.get("primary_role") else ""
        s_val = p.get("normalized_strength")
        s_str = f"Str {s_val:.1f}" if s_val is not None else "Insufficient Data"
        return f"- {p['display_name']}{role} ({s_str})"

    lines = [
        f"**StackForge 5v5 — {room_title}** (Proposal #{proposal_number} • Finalized)",
        "Map: Random (Active Pool — no map picker)",
        "",
        f"**TEAM A** (Avg {team_a_strength:.1f})",
        *[fmt_player(p) for p in team_a],
        "",
        f"**TEAM B** (Avg {team_b_strength:.1f})",
        *[fmt_player(p) for p in team_b],
        "",
        f"Balance: {balance_indicator} | Strength Diff: {strength_diff:.2f}",
    ]
    if share_summary:
        lines.append(f"Summary: {share_summary}")
    return "\n".join(lines)


def finalize_room(db: Session, community_id: str, room_id: str, req: FinalizeRequest) -> MatchRoomOut:
    room = _load_room(db, community_id, room_id)
    if room.status == "FINALIZED":
        raise HTTPException(status_code=409, detail="Room is already finalized.")
    gen = next((p for p in room.proposals if p.id == req.generation_id), None)
    if not gen:
        raise HTTPException(status_code=404, detail="Proposal not found.")

    snap_by_id = {item["id"]: item for item in json.loads(gen.input_snapshot_json)}
    team_a_ids = json.loads(gen.team_a_ids_json)
    team_b_ids = json.loads(gen.team_b_ids_json)
    team_a = [snap_by_id[pid] for pid in team_a_ids if pid in snap_by_id]
    team_b = [snap_by_id[pid] for pid in team_b_ids if pid in snap_by_id]
    explanation = json.loads(gen.explanation_json)

    discord_text = _format_discord_text(
        room_title=room.title,
        proposal_number=gen.proposal_number,
        team_a=team_a,
        team_b=team_b,
        team_a_strength=gen.team_a_strength,
        team_b_strength=gen.team_b_strength,
        strength_diff=gen.strength_diff,
        balance_indicator=explanation.get("balance_indicator", "Balanced"),
        share_summary=explanation.get("share_summary"),
    )

    lineup_snap = {
        "team_a": team_a,
        "team_b": team_b,
        "team_a_strength": gen.team_a_strength,
        "team_b_strength": gen.team_b_strength,
        "strength_diff": gen.strength_diff,
    }

    existing_fin = db.scalar(select(FinalizedLineup).where(FinalizedLineup.room_id == room.id))
    if existing_fin:
        existing_fin.generation_id = gen.id
        existing_fin.lineup_snapshot_json = json.dumps(lineup_snap)
        existing_fin.discord_text = discord_text
        existing_fin.finalized_by = req.finalized_by.strip()
        existing_fin.finalized_at = datetime.now(timezone.utc)
    else:
        db.add(
            FinalizedLineup(
                room_id=room.id,
                generation_id=gen.id,
                share_slug=room.share_slug,
                lineup_snapshot_json=json.dumps(lineup_snap),
                discord_text=discord_text,
                finalized_by=req.finalized_by.strip(),
            )
        )

    room.status = "FINALIZED"
    room.finalized_proposal_id = gen.id
    room.version += 1
    db.add(
        AuditEvent(
            community_id=community_id,
            room_id=room.id,
            event_type="LINEUP_FINALIZED",
            actor=req.finalized_by.strip(),
            payload_json=json.dumps({"generation_id": gen.id, "proposal_number": gen.proposal_number}),
        )
    )
    db.commit()
    return to_room_out(db, _load_room(db, community_id, room.id))


def reopen_room(db: Session, community_id: str, room_id: str) -> MatchRoomOut:
    room = _load_room(db, community_id, room_id)
    if room.status != "FINALIZED":
        raise HTTPException(status_code=409, detail="Only a finalized room can be reopened.")
    room.status = "REVIEWING"
    room.version += 1
    db.add(
        AuditEvent(
            community_id=community_id,
            room_id=room.id,
            event_type="ROOM_REOPENED",
            payload_json=json.dumps({"previous_finalized_proposal_id": room.finalized_proposal_id}),
        )
    )
    db.commit()
    return to_room_out(db, _load_room(db, community_id, room.id))


def get_shared_lineup(db: Session, share_slug: str) -> dict:
    fin = db.scalar(select(FinalizedLineup).where(FinalizedLineup.share_slug == share_slug))
    if not fin:
        raise HTTPException(status_code=404, detail="Shared finalized lineup not found.")
    room = db.scalar(select(MatchRoom).where(MatchRoom.id == fin.room_id))
    prop = db.scalar(select(TeamGeneration).where(TeamGeneration.id == fin.generation_id))
    if not room or not prop:
        raise HTTPException(status_code=404, detail="Lineup context not found.")
    return {
        "room_title": room.title,
        "room_status": room.status,
        "lineup": _to_finalized_out(fin, prop),
    }
