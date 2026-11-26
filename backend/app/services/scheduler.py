from __future__ import annotations

import asyncio
import os
import random
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models import CommunityPlayer, Player
from app.services import player_service
from app.services.refresh_coordinator import AUTO_STALE_SECONDS

_scheduler_task: asyncio.Task | None = None
_login_tasks: set[asyncio.Task] = set()


def _scheduler_disabled() -> bool:
    if os.getenv("STACKFORGE_DISABLE_SCHEDULER") == "1":
        return True
    return "pytest" in sys.modules


def _stale_player_ids(db, community_id: str, max_age_seconds: int = AUTO_STALE_SECONDS) -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
    cps = db.scalars(
        select(CommunityPlayer)
        .options(joinedload(CommunityPlayer.player))
        .where(
            CommunityPlayer.community_id == community_id,
            CommunityPlayer.is_active.is_(True),
            CommunityPlayer.is_archived.is_(False),
        )
        .order_by(CommunityPlayer.display_name.asc())
    ).all()
    stale_ids: list[str] = []
    for cp in cps:
        p = cp.player
        if not p.steam_id64 and not p.vanity_name:
            continue
        last_ok = p.last_successful_refresh_at
        if last_ok is None:
            stale_ids.append(cp.id)
            continue
        last_ok_utc = last_ok if last_ok.tzinfo is not None else last_ok.replace(tzinfo=timezone.utc)
        if last_ok_utc < cutoff:
            stale_ids.append(cp.id)
    return stale_ids


async def run_stale_refresh_cycle(max_players: int = 20) -> int:
    """Refreshes only stale players gently with randomized spacing and TTL preservation."""
    with SessionLocal() as db:
        comm = player_service.get_or_create_default_community(db)
        stale_ids = _stale_player_ids(db, comm.id)[:max_players]
        comm_id = comm.id

    refreshed = 0
    for idx, cpid in enumerate(stale_ids):
        try:
            with SessionLocal() as db:
                await player_service.refresh_player_profile(db, comm_id, cpid, force=False)
                refreshed += 1
        except Exception:
            # Never crash scheduler on transient external failure
            pass
        if idx < len(stale_ids) - 1:
            await asyncio.sleep(random.uniform(1.2, 2.8))
    return refreshed


async def _scheduler_loop() -> None:
    try:
        # Polite startup jitter so backend boot does not burst all providers simultaneously
        await asyncio.sleep(random.uniform(6.0, 12.0))
        while True:
            await run_stale_refresh_cycle()
            # Sleep 24h +/- tiny jitter before next automated stale sweep
            await asyncio.sleep(AUTO_STALE_SECONDS + random.uniform(30.0, 180.0))
    except asyncio.CancelledError:
        return


def start_background_scheduler() -> None:
    """Ensures at most one background scheduler task is active."""
    global _scheduler_task
    if _scheduler_disabled():
        return
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _scheduler_task = asyncio.create_task(_scheduler_loop(), name="stackforge-refresh-scheduler")


async def stop_background_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
    _scheduler_task = None
    for t in list(_login_tasks):
        if not t.done():
            t.cancel()
    _login_tasks.clear()


def schedule_stale_refresh_for_login(linked_steam_id64: str | None) -> bool:
    """
    Triggered on login when the signed-in user's linked SteamID64 maps to a stale community player.
    Deduplicated via refresh_coordinator single-flight and 24h staleness threshold.
    """
    if not linked_steam_id64 or _scheduler_disabled():
        return False

    with SessionLocal() as db:
        comm = player_service.get_or_create_default_community(db)
        cp = db.scalar(
            select(CommunityPlayer)
            .join(Player, CommunityPlayer.player_id == Player.id)
            .where(
                CommunityPlayer.community_id == comm.id,
                CommunityPlayer.is_active.is_(True),
                CommunityPlayer.is_archived.is_(False),
                Player.steam_id64 == linked_steam_id64,
            )
        )
        if not cp:
            return False
        stale = cp.id in set(_stale_player_ids(db, comm.id))
        if not stale:
            return False
        comm_id, cp_id = comm.id, cp.id

    async def _run():
        try:
            await asyncio.sleep(random.uniform(0.2, 0.8))
            with SessionLocal() as db:
                await player_service.refresh_player_profile(db, comm_id, cp_id, force=False)
        except Exception:
            pass

    task = asyncio.create_task(_run(), name=f"login-stale-refresh-{cp_id}")
    _login_tasks.add(task)
    task.add_done_callback(lambda t: _login_tasks.discard(t))
    return True
