from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    ActivityEvent,
    CommunityPlayer,
    Player,
    TrustSignal,
    WatchlistEntry,
)
from app.providers.cswatch import CSWatchProvider
from app.providers.steam import SteamProvider


def _emit_activity_dedup(
    db: Session,
    community_id: str,
    event_type: str,
    player_id: str | None,
    title: str,
    detail: str,
    dedup_key: str,
) -> None:
    existing = db.scalar(
        select(ActivityEvent).where(
            ActivityEvent.community_id == community_id,
            ActivityEvent.dedup_key == dedup_key,
        )
    )
    if existing:
        return
    db.add(
        ActivityEvent(
            community_id=community_id,
            event_type=event_type,
            player_id=player_id,
            title=title[:200],
            detail=detail,
            dedup_key=dedup_key[:120],
        )
    )


async def run_trust_check_for_player(
    db: Session,
    community_id: str,
    community_player_id: str,
    steam_provider: SteamProvider | None = None,
    cswatch_provider: CSWatchProvider | None = None,
) -> list[dict[str, Any]]:
    """
    Runs separated trust checks:
    1. Official Enforcement (Steam Web API GetPlayerBans when configured)
    2. Third-Party Reputation (CSWatch public JSON API with explicit attribution)
    Never merges third-party scores into official Valve verdicts.
    """
    cp = db.scalar(
        select(CommunityPlayer)
        .options(joinedload(CommunityPlayer.player))
        .where(
            CommunityPlayer.id == community_player_id,
            CommunityPlayer.community_id == community_id,
            CommunityPlayer.is_active.is_(True),
        )
    )
    if not cp:
        raise HTTPException(status_code=404, detail="Player not found.")

    sid = cp.player.steam_id64
    if not sid:
        raise HTTPException(status_code=422, detail="Player has no SteamID64 linked for trust monitoring.")

    steam = steam_provider or SteamProvider()
    cswatch = cswatch_provider or CSWatchProvider()
    now = datetime.now(timezone.utc)
    created_signals: list[TrustSignal] = []

    # 1. Official Steam enforcement
    bans_map = await steam.fetch_bans([sid])
    b_res = bans_map.get(sid)
    if b_res:
        sig_steam = TrustSignal(
            community_id=community_id,
            player_id=cp.player_id,
            category="OFFICIAL_ENFORCEMENT",
            provider="steam_bans",
            status=b_res.status,
            summary=b_res.summary,
            limitations="Steam GetPlayerBans count does not disclose CS2 cheat reason; no ban record does not prove clean.",
            source_url=f"https://steamcommunity.com/profiles/{sid}",
            payload_json=json.dumps(b_res.data) if b_res.data else None,
            observed_at=now,
        )
        db.add(sig_steam)
        created_signals.append(sig_steam)

        if b_res.status == "FLAGGED":
            _emit_activity_dedup(
                db,
                community_id,
                "BAN_SIGNAL",
                cp.player_id,
                f"Official Steam enforcement record for {cp.display_name}",
                b_res.summary,
                f"steam_ban:{cp.player_id}:{b_res.summary[:60]}",
            )

    # 2. CSWatch third-party reputation (with attribution & separate category)
    cw_res = await cswatch.fetch_player(sid)
    sig_cw = TrustSignal(
        community_id=community_id,
        player_id=cp.player_id,
        category="THIRD_PARTY_REPUTATION",
        provider="cswatch",
        status=cw_res.status,
        summary=cw_res.summary,
        limitations="Third-party community/reputation signal from cswatch.gg — NOT an official Valve enforcement verdict.",
        source_url=(cw_res.data or {}).get("profile_url") or f"https://cswatch.gg/player/{sid}",
        payload_json=json.dumps(cw_res.data) if cw_res.data else None,
        observed_at=now,
    )
    db.add(sig_cw)
    created_signals.append(sig_cw)

    if cw_res.status == "OK" and cw_res.data:
        if cw_res.data.get("avatar_url") and not cp.player.avatar_url:
            cp.player.avatar_url = cw_res.data["avatar_url"]
        if cw_res.data.get("persona_name") and not cp.player.steam_persona_name:
            cp.player.steam_persona_name = cw_res.data["persona_name"]
    elif cw_res.status == "FLAGGED":
        _emit_activity_dedup(
            db,
            community_id,
            "THIRD_PARTY_SIGNAL",
            cp.player_id,
            f"CSWatch signal flagged for {cp.display_name}",
            cw_res.summary,
            f"cswatch:{cp.player_id}:{cw_res.summary[:60]}",
        )

    db.commit()
    return [_signal_to_dict(s) for s in created_signals]


def _signal_to_dict(s: TrustSignal) -> dict[str, Any]:
    return {
        "id": s.id,
        "player_id": s.player_id,
        "category": s.category,
        "provider": s.provider,
        "status": s.status,
        "summary": s.summary,
        "limitations": s.limitations,
        "source_url": s.source_url,
        "payload": json.loads(s.payload_json) if s.payload_json else None,
        "observed_at": s.observed_at,
    }


def add_community_trust_report(
    db: Session,
    community_id: str,
    community_player_id: str,
    summary: str,
    source_url: str | None = None,
    category: str = "COMMUNITY_REPORT",
) -> dict[str, Any]:
    cp = db.scalar(
        select(CommunityPlayer).where(
            CommunityPlayer.id == community_player_id,
            CommunityPlayer.community_id == community_id,
        )
    )
    if not cp:
        raise HTTPException(status_code=404, detail="Player not found.")

    sig = TrustSignal(
        community_id=community_id,
        player_id=cp.player_id,
        category=category,
        provider="community_moderator",
        status="PENDING_REVIEW",
        summary=summary.strip(),
        limitations="Community-submitted observation; requires human review and is not a cheat conviction.",
        source_url=source_url.strip() if source_url else None,
    )
    db.add(sig)
    db.add(
        ActivityEvent(
            community_id=community_id,
            event_type="TRUST_REPORT",
            player_id=cp.player_id,
            title=f"Trust observation logged for {cp.display_name}",
            detail=summary.strip(),
        )
    )
    db.commit()
    db.refresh(sig)
    return _signal_to_dict(sig)


def add_watchlist_entry(
    db: Session,
    community_id: str,
    community_player_id: str,
    reason: str,
    source_url: str | None = None,
) -> dict[str, Any]:
    cp = db.scalar(
        select(CommunityPlayer)
        .options(joinedload(CommunityPlayer.player))
        .where(
            CommunityPlayer.id == community_player_id,
            CommunityPlayer.community_id == community_id,
            CommunityPlayer.is_active.is_(True),
        )
    )
    if not cp:
        raise HTTPException(status_code=404, detail="Player not found.")

    entry = WatchlistEntry(
        community_id=community_id,
        player_id=cp.player_id,
        status="WATCHING",
        reason=reason.strip(),
        source_url=source_url.strip() if source_url else None,
    )
    db.add(entry)
    db.add(
        ActivityEvent(
            community_id=community_id,
            event_type="WATCHLIST_ADDED",
            player_id=cp.player_id,
            title=f"Added {cp.display_name} to private Trust Watch",
            detail=reason.strip(),
        )
    )
    db.commit()
    db.refresh(entry)
    return get_trust_overview(db, community_id)


def review_watchlist_entry(
    db: Session,
    community_id: str,
    entry_id: str,
    status: str,
    review_note: str | None = None,
    reviewed_by: str = "Host",
) -> dict[str, Any]:
    entry = db.scalar(
        select(WatchlistEntry).where(
            WatchlistEntry.id == entry_id,
            WatchlistEntry.community_id == community_id,
        )
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Watchlist entry not found.")
    entry.status = status
    entry.review_note = review_note.strip() if review_note else entry.review_note
    entry.reviewed_by = reviewed_by
    db.add(
        TrustSignal(
            community_id=community_id,
            player_id=entry.player_id,
            category="HUMAN_REVIEW",
            provider="community_reviewer",
            status=status,
            summary=f"Reviewer {reviewed_by} marked watchlist concern {status}: {entry.review_note or entry.reason}",
            limitations="Private community moderation decision; appeal/correction supported.",
        )
    )
    db.commit()
    return get_trust_overview(db, community_id)


def get_trust_overview(db: Session, community_id: str) -> dict[str, Any]:
    cps = db.scalars(
        select(CommunityPlayer)
        .options(joinedload(CommunityPlayer.player))
        .where(CommunityPlayer.community_id == community_id, CommunityPlayer.is_active.is_(True))
    ).all()
    cp_by_player_id = {cp.player_id: cp for cp in cps}

    watchlist = db.scalars(
        select(WatchlistEntry)
        .where(WatchlistEntry.community_id == community_id)
        .order_by(WatchlistEntry.updated_at.desc())
    ).all()

    signals = db.scalars(
        select(TrustSignal)
        .where(TrustSignal.community_id == community_id)
        .order_by(TrustSignal.observed_at.desc())
        .limit(80)
    ).all()

    activities = db.scalars(
        select(ActivityEvent)
        .where(ActivityEvent.community_id == community_id)
        .order_by(ActivityEvent.created_at.desc())
        .limit(30)
    ).all()

    return {
        "watchlist": [
            {
                "id": w.id,
                "player_id": w.player_id,
                "community_player_id": cp_by_player_id[w.player_id].id if w.player_id in cp_by_player_id else None,
                "display_name": cp_by_player_id[w.player_id].display_name if w.player_id in cp_by_player_id else "Unknown",
                "steam_id64": cp_by_player_id[w.player_id].player.steam_id64 if w.player_id in cp_by_player_id else None,
                "status": w.status,
                "reason": w.reason,
                "source_url": w.source_url,
                "review_note": w.review_note,
                "reviewed_by": w.reviewed_by,
                "created_at": w.created_at,
                "updated_at": w.updated_at,
            }
            for w in watchlist
        ],
        "signals": [
            {
                **_signal_to_dict(s),
                "display_name": cp_by_player_id[s.player_id].display_name if s.player_id in cp_by_player_id else "Unknown",
                "community_player_id": cp_by_player_id[s.player_id].id if s.player_id in cp_by_player_id else None,
            }
            for s in signals
        ],
        "activity": [
            {
                "id": a.id,
                "event_type": a.event_type,
                "player_id": a.player_id,
                "title": a.title,
                "detail": a.detail,
                "created_at": a.created_at,
            }
            for a in activities
        ],
    }
