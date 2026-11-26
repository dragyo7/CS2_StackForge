from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    AuditEvent,
    CommunityPlayer,
    FinalizedLineup,
    MatchResult,
    MatchRoom,
    TeamGeneration,
)
from app.schemas import MatchResultCreate, MatchResultOut

# Active-duty CS2 map names strictly for post-match recording (never for pre-match picking/veto)
VALID_CS2_MAPS = (
    "de_mirage",
    "de_inferno",
    "de_nuke",
    "de_overpass",
    "de_ancient",
    "de_anubis",
    "de_dust2",
    "de_train",
    "de_vertigo",
)


def to_match_result_out(res: MatchResult) -> MatchResultOut:
    return MatchResultOut(
        id=res.id,
        room_id=res.room_id,
        generation_id=res.generation_id,
        share_slug=res.share_slug,
        map_played=res.map_played,
        team_a_score=res.team_a_score,
        team_b_score=res.team_b_score,
        winner_side=res.winner_side,
        external_match_url=res.external_match_url,
        demo_reference=res.demo_reference,
        result_source=res.result_source,
        validation_status=res.validation_status,
        model_version=res.model_version,
        normalizer_version=res.normalizer_version,
        notes=res.notes,
        recorded_by=res.recorded_by,
        played_at=res.played_at,
        created_at=res.created_at,
    )


def mark_room_played(db: Session, community_id: str, room_id: str) -> MatchRoom:
    room = db.scalar(
        select(MatchRoom).where(MatchRoom.id == room_id, MatchRoom.community_id == community_id)
    )
    if not room:
        raise HTTPException(status_code=404, detail="Match room not found.")
    if room.status not in ("FINALIZED", "PLAYED"):
        raise HTTPException(status_code=409, detail="Finalize a 5v5 proposal before marking the match played.")
    room.status = "PLAYED"
    room.version += 1
    db.add(
        AuditEvent(
            community_id=community_id,
            room_id=room.id,
            event_type="MATCH_MARKED_PLAYED",
            payload_json=json.dumps({"generation_id": room.finalized_proposal_id}),
        )
    )
    db.commit()
    db.refresh(room)
    return room


def record_match_result(
    db: Session,
    community_id: str,
    room_id: str,
    payload: MatchResultCreate,
) -> MatchResultOut:
    """
    Records the post-match outcome of a finalized 5v5 match.
    - Preserves finalized Team A / Team B assignments & exact input snapshot.
    - Records which random map was played (never selects a map pre-match).
    - Never mutates external Premier CSR, FACEIT ELO, or Leetify Rating.
    """
    room = db.scalar(
        select(MatchRoom).where(MatchRoom.id == room_id, MatchRoom.community_id == community_id)
    )
    if not room:
        raise HTTPException(status_code=404, detail="Match room not found.")
    if room.status not in ("FINALIZED", "PLAYED", "RESULT_RECORDED", "ANALYZED"):
        raise HTTPException(
            status_code=409,
            detail="Only a finalized match room can record a post-match result.",
        )

    fin = db.scalar(select(FinalizedLineup).where(FinalizedLineup.room_id == room.id))
    if not fin:
        raise HTTPException(status_code=409, detail="Finalized lineup snapshot not found for this room.")

    prop = db.scalar(select(TeamGeneration).where(TeamGeneration.id == fin.generation_id))
    if not prop:
        raise HTTPException(status_code=409, detail="Finalized team generation record not found.")

    raw_map = payload.map_played.strip().lower()
    if not raw_map.startswith("de_"):
        raw_map = f"de_{raw_map}"
    if raw_map not in VALID_CS2_MAPS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported map '{payload.map_played}'. Expected one of: {', '.join(VALID_CS2_MAPS)}.",
        )

    if payload.team_a_score > payload.team_b_score:
        inferred_winner = "A"
    elif payload.team_b_score > payload.team_a_score:
        inferred_winner = "B"
    else:
        inferred_winner = "TIE"

    winner = payload.winner_side or inferred_winner
    if winner != inferred_winner and payload.winner_side is not None:
        # Enforce score-winner consistency unless explicitly overridden with matching score
        raise HTTPException(
            status_code=422,
            detail=f"Winner '{winner}' conflicts with score {payload.team_a_score}-{payload.team_b_score} ({inferred_winner}).",
        )

    now = datetime.now(timezone.utc)
    played_at = payload.played_at or now
    existing = db.scalar(select(MatchResult).where(MatchResult.room_id == room.id))

    if existing:
        existing.map_played = raw_map
        existing.team_a_score = payload.team_a_score
        existing.team_b_score = payload.team_b_score
        existing.winner_side = winner
        existing.external_match_url = payload.external_match_url
        existing.demo_reference = payload.demo_reference
        existing.result_source = payload.result_source
        existing.notes = payload.notes.strip() if payload.notes else None
        existing.recorded_by = payload.recorded_by.strip()
        existing.played_at = played_at
        res_row = existing
    else:
        res_row = MatchResult(
            room_id=room.id,
            community_id=community_id,
            generation_id=prop.id,
            share_slug=fin.share_slug,
            map_played=raw_map,
            team_a_score=payload.team_a_score,
            team_b_score=payload.team_b_score,
            winner_side=winner,
            external_match_url=payload.external_match_url,
            demo_reference=payload.demo_reference,
            result_source=payload.result_source,
            validation_status="CONFIRMED",
            model_version=prop.algorithm_version,
            normalizer_version=prop.normalizer_version,
            lineup_snapshot_json=fin.lineup_snapshot_json,
            notes=payload.notes.strip() if payload.notes else None,
            recorded_by=payload.recorded_by.strip(),
            played_at=played_at,
        )
        db.add(res_row)

    room.status = "ANALYZED" if payload.demo_reference else "RESULT_RECORDED"
    room.version += 1
    db.add(
        AuditEvent(
            community_id=community_id,
            room_id=room.id,
            event_type="MATCH_RESULT_RECORDED",
            actor=payload.recorded_by.strip(),
            payload_json=json.dumps(
                {
                    "map_played": raw_map,
                    "score": f"{payload.team_a_score}-{payload.team_b_score}",
                    "winner_side": winner,
                    "result_source": payload.result_source,
                }
            ),
        )
    )
    db.commit()
    db.refresh(res_row)
    return to_match_result_out(res_row)


def get_community_standings(db: Session, community_id: str) -> dict:
    """
    Aggregates private 5v5 match outcomes into a separate community-internal leaderboard.
    Never modifies or overwrites external Valve Premier CSR, FACEIT ELO, or Leetify Rating.
    """
    results = db.scalars(
        select(MatchResult)
        .where(MatchResult.community_id == community_id)
        .order_by(MatchResult.played_at.asc(), MatchResult.created_at.asc())
    ).all()

    cps = db.scalars(
        select(CommunityPlayer)
        .options(joinedload(CommunityPlayer.player))
        .where(
            CommunityPlayer.community_id == community_id,
            CommunityPlayer.is_active.is_(True),
            CommunityPlayer.is_archived.is_(False),
        )
    ).all()
    cp_map = {cp.id: cp for cp in cps}

    stats: dict[str, dict] = {}
    recent_matches: list[dict] = []

    def _slot(pid: str, display_name: str, steam_id64: str | None) -> dict:
        if pid not in stats:
            cp = cp_map.get(pid)
            stats[pid] = {
                "community_player_id": pid,
                "display_name": cp.display_name if cp else display_name,
                "steam_id64": (cp.player.steam_id64 if cp else steam_id64),
                "avatar_url": (cp.player.avatar_url if cp else None),
                "matches": 0,
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "rounds_won": 0,
                "rounds_lost": 0,
                "community_internal_rating": 1000.0,
                "streak": 0,
                "last_map": None,
                "last_played_at": None,
            }
        return stats[pid]

    for r in results:
        snap = json.loads(r.lineup_snapshot_json)
        team_a = snap.get("team_a", [])
        team_b = snap.get("team_b", [])

        for side, members, rf, ra in (
            ("A", team_a, r.team_a_score, r.team_b_score),
            ("B", team_b, r.team_b_score, r.team_a_score),
        ):
            for m in members:
                rec = _slot(m["id"], m.get("display_name", m["id"]), m.get("steam_id64"))
                rec["matches"] += 1
                rec["rounds_won"] += rf
                rec["rounds_lost"] += ra
                rec["last_map"] = r.map_played
                rec["last_played_at"] = r.played_at.isoformat()
                if r.winner_side == "TIE":
                    rec["ties"] += 1
                    rec["streak"] = 0
                elif r.winner_side == side:
                    rec["wins"] += 1
                    rec["community_internal_rating"] = round(rec["community_internal_rating"] + 18.0, 1)
                    rec["streak"] = rec["streak"] + 1 if rec["streak"] >= 0 else 1
                else:
                    rec["losses"] += 1
                    rec["community_internal_rating"] = round(rec["community_internal_rating"] - 18.0, 1)
                    rec["streak"] = rec["streak"] - 1 if rec["streak"] <= 0 else -1

        recent_matches.append(
            {
                "id": r.id,
                "room_id": r.room_id,
                "share_slug": r.share_slug,
                "map_played": r.map_played,
                "team_a_score": r.team_a_score,
                "team_b_score": r.team_b_score,
                "winner_side": r.winner_side,
                "result_source": r.result_source,
                "played_at": r.played_at.isoformat(),
            }
        )

    standings = []
    for rec in stats.values():
        m = rec["matches"]
        rec["win_pct"] = round((rec["wins"] / m) * 100.0, 1) if m > 0 else 0.0
        rec["round_diff"] = rec["rounds_won"] - rec["rounds_lost"]
        standings.append(rec)

    standings.sort(
        key=lambda x: (-x["community_internal_rating"], -x["wins"], -x["round_diff"], x["display_name"])
    )
    return {
        "total_matches_recorded": len(results),
        "separation_note": "Community match standings & internal ratings track private 5v5 rooms only and never alter Valve Premier, FACEIT, or Leetify ratings.",
        "standings": standings,
        "recent_matches": list(reversed(recent_matches[-10:])),
    }
