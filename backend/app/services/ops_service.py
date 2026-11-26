from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, joinedload

from app.models import CommunityPlayer, MatchResult, MatchRoom, Player, ProviderSnapshot
from app.providers.external import FaceitProvider, LeetifyProvider
from app.providers.steam import SteamProvider
from app.services import player_service, scheduler, secrets_service
from app.services.refresh_coordinator import AUTO_STALE_SECONDS, normalize_v2_status


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def get_operational_overview(db: Session, community_id: str) -> dict:
    """
    Produces truthful operational & data-quality telemetry across SQLite, scheduler, and providers.
    Never marks an unconfigured or failing provider green simply because code/config exists.
    """
    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(seconds=AUTO_STALE_SECONDS)

    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

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

    total_players = len(cps)
    verified_steam = sum(1 for cp in cps if cp.player.steam_id64)
    unresolved_identity = sum(1 for cp in cps if not cp.player.steam_id64)

    stale_players: list[dict] = []
    insufficient_players: list[dict] = []

    for cp in cps:
        p = cp.player
        last_ok = _to_utc(p.last_successful_refresh_at)
        out = player_service.to_player_out(db, cp)
        if last_ok is None or last_ok < stale_cutoff:
            stale_players.append(
                {
                    "id": cp.id,
                    "display_name": cp.display_name,
                    "steam_id64": p.steam_id64,
                    "refresh_status": p.refresh_status,
                    "last_successful_refresh_at": last_ok.isoformat() if last_ok else None,
                }
            )
        if out.data_status == "INSUFFICIENT_DATA":
            insufficient_players.append(
                {
                    "id": cp.id,
                    "display_name": cp.display_name,
                    "steam_id64": p.steam_id64,
                    "data_status": out.data_status,
                    "refresh_status": p.refresh_status,
                    "last_successful_refresh_at": last_ok.isoformat() if last_ok else None,
                }
            )

    player_ids = [cp.player_id for cp in cps]
    all_snaps = (
        db.scalars(
            select(ProviderSnapshot)
            .where(ProviderSnapshot.player_id.in_(player_ids))
            .order_by(ProviderSnapshot.fetched_at.desc())
        ).all()
        if player_ids
        else []
    )

    latest_per_player_prov: dict[tuple[str, str], ProviderSnapshot] = {}
    for s in all_snaps:
        k = (s.player_id, s.provider)
        if k not in latest_per_player_prov:
            latest_per_player_prov[k] = s

    steam_ok_cfg = SteamProvider().is_configured
    faceit_ok_cfg = FaceitProvider().is_configured
    leetify_has_key = bool(LeetifyProvider().api_key)

    provider_meta = (
        ("steam_profile", "Steam Profile (?xml=1 / Web API)", "keyless_or_keyed", True),
        ("steam_bans", "Steam Official Bans (GetPlayerBans)", "keyed_only", steam_ok_cfg),
        ("leetify", "Leetify CS API v3", "configured_key" if leetify_has_key else "keyless_public", True),
        ("faceit", "FACEIT Data API v4", "keyed_only", faceit_ok_cfg),
        ("cswatch", "CSWatch Public Reputation API", "keyless_public", True),
    )

    provider_stats = []
    for prov_key, label, mode, available in provider_meta:
        prov_snaps = [s for s in all_snaps if s.provider == prov_key]
        latest_for_prov = [s for (pid, pk), s in latest_per_player_prov.items() if pk == prov_key]

        ok_latest = sum(1 for s in latest_for_prov if normalize_v2_status(s.status) in ("SUCCESS", "PARTIAL"))
        rate_limited_hist = sum(1 for s in prov_snaps if normalize_v2_status(s.status) == "RATE_LIMITED")
        private_unlinked_latest = sum(
            1 for s in latest_for_prov if normalize_v2_status(s.status) in ("PRIVATE", "NOT_LINKED", "NOT_FOUND")
        )
        not_configured_latest = sum(
            1 for s in latest_for_prov if normalize_v2_status(s.status) == "NOT_CONFIGURED"
        )
        last_ok_dt = next(
            (_to_utc(s.fetched_at) for s in prov_snaps if normalize_v2_status(s.status) in ("SUCCESS", "PARTIAL")),
            None,
        )
        last_fail_dt = next(
            (
                _to_utc(s.fetched_at)
                for s in prov_snaps
                if normalize_v2_status(s.status) in ("RATE_LIMITED", "UNAVAILABLE", "FAILED")
            ),
            None,
        )
        success_rate = round((ok_latest / total_players) * 100.0, 1) if total_players > 0 else 0.0

        # Honest health label: NEVER green solely because configured
        if not available or (latest_for_prov and not_configured_latest == len(latest_for_prov)):
            health_state = "NOT_CONFIGURED"
        elif ok_latest == 0:
            health_state = "DEGRADED"
        elif ok_latest < verified_steam and (private_unlinked_latest > 0 or rate_limited_hist > 0):
            health_state = "PARTIAL_COVERAGE"
        else:
            health_state = "HEALTHY"

        provider_stats.append(
            {
                "provider": prov_key,
                "label": label,
                "mode": mode,
                "configured": available,
                "health_state": health_state,
                "active_players_ok": ok_latest,
                "success_rate_pct": success_rate,
                "total_historical_attempts": len(prov_snaps),
                "rate_limit_events": rate_limited_hist,
                "private_or_unlinked_players": private_unlinked_latest,
                "last_successful_at": last_ok_dt.isoformat() if last_ok_dt else None,
                "last_failed_at": last_fail_dt.isoformat() if last_fail_dt else None,
            }
        )

    rooms_total = db.scalar(select(func.count()).select_from(MatchRoom).where(MatchRoom.community_id == community_id)) or 0
    results_total = db.scalar(select(func.count()).select_from(MatchResult).where(MatchResult.community_id == community_id)) or 0
    sched = scheduler.get_scheduler_health()

    return {
        "backend_status": "ok",
        "database": {
            "status": "ok" if db_ok else "error",
            "engine": "sqlite",
            "players_active": total_players,
            "steam_verified": verified_steam,
            "unresolved_identities": unresolved_identity,
            "match_rooms_total": rooms_total,
            "match_results_recorded": results_total,
        },
        "scheduler": sched,
        "stale_players_count": len(stale_players),
        "stale_players": stale_players,
        "insufficient_data_count": len(insufficient_players),
        "insufficient_data_players": insufficient_players,
        "providers": provider_stats,
        "credentials": secrets_service.list_credentials_status(),
        "demo_queue": {
            "status": "design_ready_not_enabled",
            "pending_jobs": 0,
        },
    }
