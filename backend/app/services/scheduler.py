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

_telemetry: dict[str, object] = {
    "started_at": None,
    "last_cycle_at": None,
    "last_cycle_status": "NEVER_RUN",
    "last_cycle_refreshed": 0,
    "last_cycle_error": None,
    "cycles_completed": 0,
    "last_full_refresh_at": None,
    "last_failed_refresh_at": None,
    "last_failed_refresh_reason": None,
}


def _scheduler_disabled_reason() -> str | None:
    if os.getenv("STACKFORGE_DISABLE_SCHEDULER") == "1":
        return "disabled_by_env"
    if "pytest" in sys.modules:
        return "disabled_in_tests"
    return None


def _scheduler_disabled() -> bool:
    return _scheduler_disabled_reason() is not None


def record_refresh_telemetry(
    *,
    full_refresh: bool = False,
    had_failure: bool = False,
    failure_reason: str | None = None,
) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    if full_refresh:
        _telemetry["last_full_refresh_at"] = now_iso
    if had_failure:
        _telemetry["last_failed_refresh_at"] = now_iso
        _telemetry["last_failed_refresh_reason"] = failure_reason[:300] if failure_reason else "Refresh error"


def get_scheduler_health() -> dict[str, object]:
    disabled_reason = _scheduler_disabled_reason()
    active = _scheduler_task is not None and not _scheduler_task.done()
    state = "active" if active else (disabled_reason or "inactive")
    return {
        "status": "active" if active else "inactive",
        "state": state,
        "enabled": disabled_reason is None,
        "disabled_reason": disabled_reason,
        "singleton_running": active,
        "stale_threshold_hours": round(AUTO_STALE_SECONDS / 3600.0, 1),
        "started_at": _telemetry["started_at"],
        "last_cycle_at": _telemetry["last_cycle_at"],
        "last_cycle_status": _telemetry["last_cycle_status"],
        "last_cycle_refreshed": _telemetry["last_cycle_refreshed"],
        "last_cycle_error": _telemetry["last_cycle_error"],
        "cycles_completed": _telemetry["cycles_completed"],
        "last_full_refresh_at": _telemetry["last_full_refresh_at"],
        "last_failed_refresh_at": _telemetry["last_failed_refresh_at"],
        "last_failed_refresh_reason": _telemetry["last_failed_refresh_reason"],
    }


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
    had_error = False
    last_err: str | None = None
    for idx, cpid in enumerate(stale_ids):
        try:
            with SessionLocal() as db:
                await player_service.refresh_player_profile(db, comm_id, cpid, force=False)
                refreshed += 1
        except Exception as exc:
            had_error = True
            last_err = str(exc)
        if idx < len(stale_ids) - 1:
            await asyncio.sleep(random.uniform(1.2, 2.8))

    _telemetry["last_cycle_at"] = datetime.now(timezone.utc).isoformat()
    _telemetry["last_cycle_refreshed"] = refreshed
    _telemetry["cycles_completed"] = int(_telemetry["cycles_completed"] or 0) + 1
    if had_error:
        _telemetry["last_cycle_status"] = "PARTIAL"
        _telemetry["last_cycle_error"] = last_err
        record_refresh_telemetry(had_failure=True, failure_reason=last_err)
    else:
        _telemetry["last_cycle_status"] = "OK"
        _telemetry["last_cycle_error"] = None
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
    _telemetry["started_at"] = datetime.now(timezone.utc).isoformat()
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
