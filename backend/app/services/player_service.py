from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import (
    ActivityEvent,
    AuditEvent,
    Community,
    CommunityPlayer,
    Player,
    PlayerAlias,
    PlayerExternalIdentity,
    PlayerMatchRecord,
    PlayerStatSnapshot,
    ProviderSnapshot,
    TrustSignal,
    WatchlistEntry,
)
from app.optimizer.normalizer import PlayerInput, normalize_player
from app.providers.cswatch import CSWatchProvider
from app.providers.external import FaceitProvider, LeetifyProvider
from app.providers.steam import SteamProvider
from app.schemas import (
    AliasOut,
    BulkImportEntryResult,
    BulkImportRequest,
    BulkImportResponse,
    ExternalIdentityOut,
    MatchRecordOut,
    PlayerCardOut,
    PlayerCardSettingsUpdate,
    PlayerCompareOut,
    PlayerCreate,
    PlayerOut,
    PlayerProfileOut,
    PlayerUpdate,
    ProviderRefreshResultOut,
    ProviderStatusOut,
    RefreshProfileResponse,
    StatSnapshotCreate,
    StatSnapshotOut,
    TrustSummaryOut,
)
from app.services.humour_engine import CardMetricContext, generate_player_card
from app.services.refresh_coordinator import (
    freshness_for_timestamp,
    is_provider_fresh,
    is_retry_eligible_status,
    normalize_v2_status,
    run_single_flight,
    throttle_provider,
)


def _add_provider_snapshot(
    db: Session,
    *,
    player_id: str,
    provider: str,
    status: str,
    summary_text: str,
    fetched_at: datetime,
    endpoint_category: str = "profile",
    player_identity: str | None = None,
    failure_reason: str | None = None,
    retry_eligible: bool | None = None,
    payload: dict | None = None,
) -> None:
    norm = normalize_v2_status(status)
    db.add(
        ProviderSnapshot(
            player_id=player_id,
            provider=provider,
            endpoint_category=endpoint_category,
            player_identity=player_identity,
            status=status,
            normalized_status=norm,
            summary_text=summary_text[:255],
            failure_reason=failure_reason[:300] if failure_reason else None,
            retry_eligible=is_retry_eligible_status(status) if retry_eligible is None else retry_eligible,
            data_freshness=freshness_for_timestamp(fetched_at, "steam" if provider.startswith("steam") else provider),
            last_successful_at=fetched_at if norm in ("SUCCESS", "PARTIAL") else None,
            payload_json=json.dumps(payload) if payload else None,
            fetched_at=fetched_at,
        )
    )
from app.services.steam_parser import is_valid_steam_id64, normalize_steam_url_or_id, parse_import_line

DEFAULT_COMMUNITY_SLUG = "main-stack"


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def get_or_create_default_community(db: Session) -> Community:
    comm = db.scalar(select(Community).where(Community.slug == DEFAULT_COMMUNITY_SLUG))
    if comm:
        return comm
    comm = Community(name="Main CS2 Stack", slug=DEFAULT_COMMUNITY_SLUG)
    db.add(comm)
    db.commit()
    db.refresh(comm)
    return comm


def _latest_snapshots_map(db: Session, player_id: str) -> list[ProviderStatusOut]:
    rows = db.scalars(
        select(ProviderSnapshot)
        .where(ProviderSnapshot.player_id == player_id)
        .order_by(ProviderSnapshot.fetched_at.desc())
    ).all()
    seen: set[str] = set()
    out: list[ProviderStatusOut] = []
    for row in rows:
        if row.provider in seen:
            continue
        seen.add(row.provider)
        out.append(
            ProviderStatusOut(
                provider=row.provider,
                status=row.status,
                summary=row.summary_text,
                fetched_at=row.fetched_at,
            )
        )
    return out


def _stat_to_out(st: PlayerStatSnapshot) -> StatSnapshotOut:
    return StatSnapshotOut(
        id=st.id,
        provider=st.provider,
        scope=st.scope,
        game_mode=st.game_mode,
        season=st.season,
        sample_size=st.sample_size,
        raw_rating_label=st.raw_rating_label,
        raw_rating_value=st.raw_rating_value,
        matches_played=st.matches_played,
        win_rate=st.win_rate,
        kd_ratio=st.kd_ratio,
        adr=st.adr,
        kast=st.kast,
        hs_pct=st.hs_pct,
        opening_duel_pct=st.opening_duel_pct,
        trade_kills_per_match=st.trade_kills_per_match,
        utility_damage_per_round=st.utility_damage_per_round,
        flash_assists_per_round=st.flash_assists_per_round,
        clutch_win_pct=st.clutch_win_pct,
        multi_kill_rate=st.multi_kill_rate,
        consistency_score=st.consistency_score,
        aim_rating=st.aim_rating,
        utility_rating=st.utility_rating,
        positioning_rating=st.positioning_rating,
        preaim=st.preaim,
        reaction_time_ms=st.reaction_time_ms,
        spotted_accuracy=st.spotted_accuracy,
        spray_accuracy=st.spray_accuracy,
        enemies_flashed_per_round=st.enemies_flashed_per_round,
        traded_deaths_pct=st.traded_deaths_pct,
        freshness=st.freshness,
        is_sample_demo=st.is_sample_demo,
        captured_at=st.captured_at,
    )


def _aliases_for_player(db: Session, player_id: str) -> list[AliasOut]:
    rows = db.scalars(
        select(PlayerAlias)
        .where(PlayerAlias.player_id == player_id)
        .order_by(PlayerAlias.observed_at.desc())
    ).all()
    return [
        AliasOut(
            id=a.id,
            alias_name=a.alias_name,
            previous_name=a.previous_name,
            source=a.source,
            observed_at=a.observed_at,
        )
        for a in rows
    ]


def _stats_for_player(db: Session, player_id: str) -> list[StatSnapshotOut]:
    rows = db.scalars(
        select(PlayerStatSnapshot)
        .where(PlayerStatSnapshot.player_id == player_id)
        .order_by(PlayerStatSnapshot.captured_at.desc())
    ).all()
    scope_rank = {"recent": 0, "season": 1, "lifetime": 2}
    rows_sorted = sorted(
        rows,
        key=lambda st: (
            -(_ensure_utc(st.captured_at) or datetime.min.replace(tzinfo=timezone.utc)).timestamp(),
            scope_rank.get(st.scope, 3),
        ),
    )
    return [_stat_to_out(st) for st in rows_sorted]


def select_effective_player_stats(db: Session, player_id: str) -> dict:
    """
    Explicitly selects recent and lifetime snapshots:
    - Prefers `recent` for recent-form metrics (ADR, recent K/D, win rate, flash assists, sample size).
    - Prefers `lifetime` for lifetime metrics (opening duels, trade kills, clutch %, consistency, utility).
    Preserves None when missing; marks stale when age >= 14 days or freshness == 'STALE'.
    """
    rows = db.scalars(
        select(PlayerStatSnapshot)
        .where(PlayerStatSnapshot.player_id == player_id)
        .order_by(PlayerStatSnapshot.captured_at.desc())
    ).all()
    recent_snap = next((r for r in rows if r.scope == "recent" and r.freshness != "STALE"), None) or next(
        (r for r in rows if r.scope == "recent"), None
    )
    lifetime_snap = next((r for r in rows if r.scope == "lifetime" and r.freshness != "STALE"), None) or next(
        (r for r in rows if r.scope == "lifetime"), None
    )
    fallback_snap = rows[0] if rows else None

    primary = recent_snap or lifetime_snap or fallback_snap
    lifetime_or_fb = lifetime_snap or fallback_snap
    recent_or_fb = recent_snap or lifetime_snap or fallback_snap

    def _pick(attr: str, prefer_recent: bool):
        order = (recent_snap, lifetime_snap, fallback_snap) if prefer_recent else (lifetime_snap, recent_snap, fallback_snap)
        for snap in order:
            if snap is not None:
                val = getattr(snap, attr, None)
                if val is not None:
                    return val
        return None

    now = datetime.now(timezone.utc)
    stats_stale = False
    if primary and not primary.is_sample_demo:
        cap = _ensure_utc(primary.captured_at)
        if primary.freshness == "STALE" or (cap is not None and (now - cap).days >= 14):
            stats_stale = True

    sample_src = recent_snap or lifetime_snap or fallback_snap
    sample_size = (sample_src.sample_size or sample_src.matches_played or 0) if sample_src else 0

    return {
        "recent_snapshot": recent_snap,
        "lifetime_snapshot": lifetime_snap,
        "primary_snapshot": primary,
        "adr": _pick("adr", prefer_recent=True),
        "kd_ratio": _pick("kd_ratio", prefer_recent=True),
        "kast": _pick("kast", prefer_recent=True),
        "hs_pct": _pick("hs_pct", prefer_recent=True),
        "win_rate": _pick("win_rate", prefer_recent=True),
        "preaim": _pick("preaim", prefer_recent=True),
        "reaction_time_ms": _pick("reaction_time_ms", prefer_recent=True),
        "spotted_accuracy": _pick("spotted_accuracy", prefer_recent=True),
        "spray_accuracy": _pick("spray_accuracy", prefer_recent=True),
        "flash_assists_per_round": _pick("flash_assists_per_round", prefer_recent=True),
        "enemies_flashed_per_round": _pick("enemies_flashed_per_round", prefer_recent=True),
        "aim_rating": _pick("aim_rating", prefer_recent=False),
        "utility_rating": _pick("utility_rating", prefer_recent=False),
        "positioning_rating": _pick("positioning_rating", prefer_recent=False),
        "opening_duel_pct": _pick("opening_duel_pct", prefer_recent=False),
        "trade_kills_per_match": _pick("trade_kills_per_match", prefer_recent=False),
        "traded_deaths_pct": _pick("traded_deaths_pct", prefer_recent=False),
        "utility_damage_per_round": _pick("utility_damage_per_round", prefer_recent=False),
        "clutch_win_pct": _pick("clutch_win_pct", prefer_recent=False),
        "consistency_score": _pick("consistency_score", prefer_recent=False),
        "stats_sample_size": sample_size,
        "stats_stale": stats_stale,
        "has_recent_or_lifetime": (recent_or_fb is not None or lifetime_or_fb is not None),
    }


def build_player_input(db: Session, cp: CommunityPlayer) -> tuple[PlayerInput, dict]:
    """Shared normalized PlayerInput builder used identically by Registry and Optimizer (ignores manual_rating)."""
    p = cp.player
    map_ratings: dict[str, float] = {}
    if cp.map_ratings_json:
        try:
            map_ratings = json.loads(cp.map_ratings_json)
        except json.JSONDecodeError:
            map_ratings = {}
    eff = select_effective_player_stats(db, p.id)
    eff["aim_rating"] = eff["aim_rating"] if eff["aim_rating"] is not None else cp.aim_rating
    eff["utility_rating"] = eff["utility_rating"] if eff["utility_rating"] is not None else cp.utility_rating
    eff["positioning_rating"] = (
        eff["positioning_rating"] if eff["positioning_rating"] is not None else cp.positioning_rating
    )
    pin = PlayerInput(
        community_player_id=cp.id,
        display_name=cp.display_name,
        steam_id64=p.steam_id64,
        identity_status=p.identity_status,
        manual_rating=None,
        premier_rating=cp.premier_rating,
        premier_source=cp.premier_source,
        premier_season=cp.premier_season,
        faceit_elo=cp.faceit_elo,
        faceit_level=cp.faceit_level,
        leetify_rating=cp.leetify_rating,
        aim_rating=eff["aim_rating"],
        utility_rating=eff["utility_rating"],
        positioning_rating=eff["positioning_rating"],
        recent_form=cp.recent_form,
        primary_role=cp.primary_role,
        secondary_role=cp.secondary_role,
        map_ratings=map_ratings,
        adr=eff["adr"],
        kd_ratio=eff["kd_ratio"],
        kast=eff["kast"],
        hs_pct=eff["hs_pct"],
        preaim=eff["preaim"],
        reaction_time_ms=eff["reaction_time_ms"],
        spotted_accuracy=eff["spotted_accuracy"],
        spray_accuracy=eff["spray_accuracy"],
        opening_duel_pct=eff["opening_duel_pct"],
        trade_kills_per_match=eff["trade_kills_per_match"],
        traded_deaths_pct=eff["traded_deaths_pct"],
        utility_damage_per_round=eff["utility_damage_per_round"],
        flash_assists_per_round=eff["flash_assists_per_round"],
        enemies_flashed_per_round=eff["enemies_flashed_per_round"],
        clutch_win_pct=eff["clutch_win_pct"],
        consistency_score=eff["consistency_score"],
        win_rate=eff["win_rate"],
        stats_sample_size=eff["stats_sample_size"],
        stats_stale=eff["stats_stale"],
    )
    return pin, eff


def _trust_summary_for_player(db: Session, community_id: str, player_id: str) -> TrustSummaryOut | None:
    watch = (
        db.scalar(
            select(WatchlistEntry)
            .where(
                WatchlistEntry.community_id == community_id,
                WatchlistEntry.player_id == player_id,
                WatchlistEntry.status == "WATCHING",
            )
            .order_by(WatchlistEntry.updated_at.desc())
            .limit(1)
        )
        or db.scalar(
            select(WatchlistEntry)
            .where(WatchlistEntry.community_id == community_id, WatchlistEntry.player_id == player_id)
            .order_by(WatchlistEntry.updated_at.desc())
            .limit(1)
        )
    )
    cw_sig = db.scalar(
        select(TrustSignal)
        .where(
            TrustSignal.community_id == community_id,
            TrustSignal.player_id == player_id,
            TrustSignal.provider == "cswatch",
        )
        .order_by(TrustSignal.observed_at.desc())
        .limit(1)
    )
    cw_snap = None if cw_sig else db.scalar(
        select(ProviderSnapshot)
        .where(ProviderSnapshot.player_id == player_id, ProviderSnapshot.provider == "cswatch")
        .order_by(ProviderSnapshot.fetched_at.desc())
        .limit(1)
    )
    if not watch and not cw_sig and not cw_snap:
        return None

    cw_status = cw_sig.status if cw_sig else (cw_snap.status if cw_snap else None)
    cw_summary = cw_sig.summary if cw_sig else (cw_snap.summary_text if cw_snap else None)
    payload_raw = cw_sig.payload_json if cw_sig else (cw_snap.payload_json if cw_snap else None)
    risk_level = None
    rep_score = None
    if payload_raw:
        try:
            pdata = json.loads(payload_raw)
            risk_level = pdata.get("risk_level")
            rep_score = pdata.get("reputation_score")
        except json.JSONDecodeError:
            pass

    return TrustSummaryOut(
        cswatch_status=cw_status,
        cswatch_risk_level=risk_level,
        cswatch_reputation_score=rep_score,
        cswatch_summary=cw_summary,
        watchlist_status=watch.status if watch else None,
        watchlist_reason=watch.reason if watch else None,
    )


def _build_card_for_cp(
    cp: CommunityPlayer,
    norm_strength: float,
    strength_band: str,
    stats_list: list[StatSnapshotOut],
) -> PlayerCardOut:
    # Prefer non-manual stats with largest sample size
    best = next((s for s in stats_list if (s.sample_size or s.matches_played or 0) > 0), None)
    hidden_badges: list[str] = []
    if cp.hidden_badges_json:
        try:
            hidden_badges = json.loads(cp.hidden_badges_json)
        except json.JSONDecodeError:
            hidden_badges = []

    sample = (best.sample_size or best.matches_played or 0) if best else 0
    ctx = CardMetricContext(
        display_name=cp.display_name,
        primary_role=cp.primary_role,
        normalized_strength=norm_strength,
        strength_band=strength_band,
        sample_size=sample,
        provider_label=best.provider if best else None,
        win_rate=best.win_rate if best else None,
        kd_ratio=best.kd_ratio if best else None,
        adr=best.adr if best else None,
        kast=best.kast if best else None,
        hs_pct=best.hs_pct if best else None,
        opening_duel_pct=best.opening_duel_pct if best else None,
        utility_damage_per_round=best.utility_damage_per_round if best else None,
        flash_assists_per_round=best.flash_assists_per_round if best else None,
        clutch_win_pct=best.clutch_win_pct if best else None,
        trade_kills_per_match=best.trade_kills_per_match if best else None,
        multi_kill_rate=best.multi_kill_rate if best else None,
    )
    card_dict = generate_player_card(
        ctx=ctx,
        humour_enabled=cp.humour_enabled,
        humour_intensity=cp.humour_intensity,
        hidden_badges=hidden_badges,
        variant=cp.card_tagline_variant,
    )
    return PlayerCardOut(**card_dict)


def record_alias_if_changed(
    db: Session,
    player: Player,
    new_name: str | None,
    source: str = "steam_web_api",
) -> bool:
    """
    Append-only alias observation when a player's Steam persona/name changes.
    Prevents duplicate consecutive aliases and never duplicates the Player row.
    """
    cleaned = (new_name or "").strip()
    if not cleaned:
        return False

    latest = db.scalar(
        select(PlayerAlias)
        .where(PlayerAlias.player_id == player.id)
        .order_by(PlayerAlias.observed_at.desc())
        .limit(1)
    )
    prev = player.steam_persona_name

    if prev and prev == cleaned:
        return False
    if latest and latest.alias_name == cleaned:
        player.steam_persona_name = cleaned
        return False

    db.add(
        PlayerAlias(
            player_id=player.id,
            alias_name=cleaned,
            previous_name=prev,
            source=source,
            observed_at=datetime.now(timezone.utc),
        )
    )
    player.steam_persona_name = cleaned
    return prev is not None and prev != cleaned


def _external_identities_for_player(db: Session, player_id: str) -> list[ExternalIdentityOut]:
    rows = db.scalars(
        select(PlayerExternalIdentity).where(PlayerExternalIdentity.player_id == player_id)
    ).all()
    return [
        ExternalIdentityOut(
            id=r.id,
            provider=r.provider,
            external_id=r.external_id,
            profile_url=r.profile_url,
            verification_state=r.verification_state,
            confidence=r.confidence,
        )
        for r in rows
    ]


def _match_records_for_player(db: Session, player_id: str) -> list[MatchRecordOut]:
    rows = db.scalars(
        select(PlayerMatchRecord)
        .where(PlayerMatchRecord.player_id == player_id)
        .order_by(PlayerMatchRecord.played_at.desc())
        .limit(20)
    ).all()
    return [
        MatchRecordOut(
            id=m.id,
            provider=m.provider,
            external_match_id=m.external_match_id,
            map_name=m.map_name,
            game_mode=m.game_mode,
            outcome=m.outcome,
            score_text=m.score_text,
            kd_ratio=m.kd_ratio,
            adr=m.adr,
            hs_pct=m.hs_pct,
            leetify_rating=m.leetify_rating,
            source_url=m.source_url,
            played_at=m.played_at,
        )
        for m in rows
    ]


def to_player_out(db: Session, cp: CommunityPlayer) -> PlayerOut:
    p = cp.player
    pin, eff = build_player_input(db, cp)
    norm = normalize_player(pin)

    aliases = _aliases_for_player(db, p.id)
    stats_list = _stats_for_player(db, p.id)
    ext_ids = _external_identities_for_player(db, p.id)
    card = _build_card_for_cp(cp, norm.normalized_strength, norm.strength_band, stats_list)

    return PlayerOut(
        id=cp.id,
        player_id=p.id,
        community_id=cp.community_id,
        display_name=cp.display_name,
        steam_id64=p.steam_id64,
        steam_profile_url=p.steam_profile_url,
        vanity_name=p.vanity_name,
        steam_persona_name=p.steam_persona_name,
        avatar_url=p.avatar_url,
        identity_status=p.identity_status,
        last_successful_refresh_at=p.last_successful_refresh_at,
        last_refresh_attempt_at=p.last_refresh_attempt_at,
        refresh_status=p.refresh_status,
        refresh_error=p.refresh_error,
        profile_visibility=p.profile_visibility,
        stats_visibility=cp.stats_visibility,
        manual_rating=cp.manual_rating,
        premier_rating=cp.premier_rating,
        premier_source=cp.premier_source,
        premier_season=cp.premier_season,
        faceit_elo=cp.faceit_elo,
        faceit_level=cp.faceit_level,
        leetify_rating=cp.leetify_rating,
        aim_rating=eff["aim_rating"],
        utility_rating=eff["utility_rating"],
        positioning_rating=eff["positioning_rating"],
        recent_form=cp.recent_form,
        primary_role=cp.primary_role,
        secondary_role=cp.secondary_role,
        notes=cp.notes,
        is_seeded=cp.is_seeded,
        is_archived=cp.is_archived,
        stats_stale=eff["stats_stale"],
        data_status=norm.data_status,
        normalized_strength=norm.normalized_strength,
        confidence=norm.confidence,
        strength_band=norm.strength_band,
        missing_sources=norm.missing_sources,
        provider_statuses=_latest_snapshots_map(db, p.id),
        aliases=aliases,
        external_identities=ext_ids,
        latest_stats=stats_list[0] if stats_list else None,
        trust_summary=_trust_summary_for_player(db, cp.community_id, p.id),
        card=card,
        created_at=cp.created_at,
        updated_at=cp.updated_at,
    )


def list_players(
    db: Session,
    community_id: str,
    query: str | None = None,
    include_archived: bool = False,
    sort_by: str = "strength",
) -> list[PlayerOut]:
    stmt = (
        select(CommunityPlayer)
        .options(joinedload(CommunityPlayer.player).joinedload(Player.aliases))
        .where(CommunityPlayer.community_id == community_id, CommunityPlayer.is_active.is_(True))
        .order_by(CommunityPlayer.display_name.asc())
    )
    if not include_archived:
        stmt = stmt.where(CommunityPlayer.is_archived.is_(False))
    rows = db.scalars(stmt).unique().all()
    if query and query.strip():
        q = query.strip().lower()
        filtered: list[CommunityPlayer] = []
        for cp in rows:
            p = cp.player
            alias_match = any(
                q in a.alias_name.lower() or (a.previous_name and q in a.previous_name.lower())
                for a in p.aliases
            )
            if (
                q in cp.display_name.lower()
                or (p.steam_id64 and q in p.steam_id64.lower())
                or (cp.primary_role and q in cp.primary_role.lower())
                or (p.steam_persona_name and q in p.steam_persona_name.lower())
                or (p.vanity_name and q in p.vanity_name.lower())
                or alias_match
            ):
                filtered.append(cp)
        rows = filtered
    out = [to_player_out(db, cp) for cp in rows]
    if sort_by == "name":
        out.sort(key=lambda x: x.display_name.lower())
    else:
        out.sort(
            key=lambda x: (
                0 if x.normalized_strength is not None else 1,
                -(x.normalized_strength if x.normalized_strength is not None else -1.0),
                -x.confidence,
                x.display_name.lower(),
            )
        )
    return out


def _resolve_steam_fields(
    steam_id64: str | None, steam_profile_url: str | None
) -> tuple[str | None, str | None, str | None, str]:
    cleaned_sid = steam_id64.strip() if steam_id64 and steam_id64.strip() else None
    cleaned_url = steam_profile_url.strip() if steam_profile_url and steam_profile_url.strip() else None

    if cleaned_sid:
        if not is_valid_steam_id64(cleaned_sid):
            raise HTTPException(
                status_code=422,
                detail="Invalid SteamID64 format. Expected a 17-digit SteamID64 starting with 7656119.",
            )
        canonical_url = cleaned_url or f"https://steamcommunity.com/profiles/{cleaned_sid}"
        return cleaned_sid, canonical_url, None, "STEAM_PARSED"

    if cleaned_url:
        parsed_sid, canonical_url, vanity = normalize_steam_url_or_id(cleaned_url)
        if parsed_sid:
            return parsed_sid, canonical_url, None, "STEAM_PARSED"
        if vanity:
            return None, canonical_url, vanity, "MANUAL_ONLY"
        raise HTTPException(
            status_code=422,
            detail="Unsupported Steam profile URL. Use https://steamcommunity.com/profiles/<SteamID64> or /id/<vanity>.",
        )

    return None, None, None, "MANUAL_ONLY"


async def create_player_with_resolution(
    db: Session,
    community_id: str,
    payload: PlayerCreate,
    steam_provider: SteamProvider | None = None,
) -> PlayerOut:
    """Resolves vanity URLs via Steam before running canonical duplicate checks and insertion."""
    steam_id64, steam_url, vanity, _status = _resolve_steam_fields(
        payload.steam_id64, payload.steam_profile_url
    )
    resolved_payload = payload
    if not steam_id64 and vanity:
        steam = steam_provider or SteamProvider()
        resolved_sid, van_status = await steam.resolve_vanity_url(vanity)
        if resolved_sid:
            resolved_payload = payload.model_copy(
                update={
                    "steam_id64": resolved_sid,
                    "steam_profile_url": f"https://steamcommunity.com/profiles/{resolved_sid}",
                }
            )
            created = create_player(db, community_id, resolved_payload)
            cp = _get_cp_or_404(db, community_id, created.id)
            cp.player.vanity_name = vanity
            cp.player.identity_status = "STEAM_RESOLVED"
            db.commit()
            return to_player_out(db, cp)
        raise HTTPException(
            status_code=422,
            detail=f"Vanity URL '{vanity}' could not be resolved to a SteamID64 ({van_status}).",
        )
    return create_player(db, community_id, resolved_payload)


def create_player(db: Session, community_id: str, payload: PlayerCreate, is_seeded: bool = False) -> PlayerOut:
    steam_id64, steam_url, vanity, identity_status = _resolve_steam_fields(
        payload.steam_id64, payload.steam_profile_url
    )

    global_player: Player | None = None
    if steam_id64:
        global_player = db.scalar(select(Player).where(Player.steam_id64 == steam_id64))
        if not global_player:
            ext = db.scalar(
                select(PlayerExternalIdentity).where(
                    PlayerExternalIdentity.provider == "steam",
                    PlayerExternalIdentity.external_id == steam_id64,
                )
            )
            if ext:
                global_player = db.scalar(select(Player).where(Player.id == ext.player_id))
    elif vanity:
        global_player = db.scalar(select(Player).where(Player.vanity_name == vanity))

    if global_player:
        existing_cp = db.scalar(
            select(CommunityPlayer).where(
                CommunityPlayer.community_id == community_id,
                CommunityPlayer.player_id == global_player.id,
            )
        )
        if existing_cp and existing_cp.is_active:
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate identity ({steam_id64 or vanity}): already registered as '{existing_cp.display_name}'.",
            )
        if existing_cp and not existing_cp.is_active:
            # Reactivate previously removed community membership without duplicating global Player
            existing_cp.is_active = True
            existing_cp.is_archived = False
            existing_cp.display_name = payload.display_name.strip()
            existing_cp.manual_rating = payload.manual_rating
            db.commit()
            db.refresh(existing_cp)
            return to_player_out(db, existing_cp)

    if not global_player:
        global_player = Player(
            steam_id64=steam_id64,
            steam_profile_url=steam_url,
            vanity_name=vanity,
            avatar_url=payload.avatar_url,
            identity_status=identity_status,
        )
        db.add(global_player)
        db.flush()
    else:
        if payload.avatar_url and not global_player.avatar_url:
            global_player.avatar_url = payload.avatar_url
        if steam_url and not global_player.steam_profile_url:
            global_player.steam_profile_url = steam_url
        if vanity and not global_player.vanity_name:
            global_player.vanity_name = vanity

    cp = CommunityPlayer(
        community_id=community_id,
        player_id=global_player.id,
        display_name=payload.display_name.strip(),
        manual_rating=payload.manual_rating,
        premier_rating=payload.premier_rating,
        premier_source=payload.premier_source or ("manual_entry" if payload.premier_rating is not None else None),
        premier_season=payload.premier_season,
        faceit_elo=payload.faceit_elo,
        leetify_rating=payload.leetify_rating,
        recent_form=payload.recent_form,
        primary_role=payload.primary_role,
        secondary_role=payload.secondary_role,
        notes=payload.notes.strip() if payload.notes else None,
        is_seeded=is_seeded,
    )
    db.add(cp)
    db.add(
        AuditEvent(
            community_id=community_id,
            event_type="PLAYER_CREATED",
            payload_json=json.dumps({"display_name": cp.display_name, "steam_id64": steam_id64, "is_seeded": is_seeded}),
        )
    )
    db.commit()
    db.refresh(cp)
    return to_player_out(db, cp)


def _get_cp_or_404(db: Session, community_id: str, community_player_id: str) -> CommunityPlayer:
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
    return cp


def update_player(db: Session, community_id: str, community_player_id: str, payload: PlayerUpdate) -> PlayerOut:
    cp = _get_cp_or_404(db, community_id, community_player_id)

    if payload.display_name is not None:
        new_nick = payload.display_name.strip()
        if new_nick and new_nick != cp.display_name:
            db.add(
                PlayerAlias(
                    player_id=cp.player_id,
                    alias_name=new_nick,
                    previous_name=cp.display_name,
                    source="community_nickname",
                )
            )
            cp.display_name = new_nick
    if payload.manual_rating is not None:
        cp.manual_rating = payload.manual_rating
    if payload.clear_premier:
        cp.premier_rating = None
        cp.premier_source = None
        cp.premier_season = None
    elif payload.premier_rating is not None:
        cp.premier_rating = payload.premier_rating
        cp.premier_source = payload.premier_source or cp.premier_source or "manual_entry"
        cp.premier_season = payload.premier_season or cp.premier_season
    if payload.clear_faceit:
        cp.faceit_elo = None
    elif payload.faceit_elo is not None:
        cp.faceit_elo = payload.faceit_elo
    if payload.clear_leetify:
        cp.leetify_rating = None
    elif payload.leetify_rating is not None:
        cp.leetify_rating = payload.leetify_rating
    if payload.recent_form is not None:
        cp.recent_form = payload.recent_form
    if payload.clear_primary_role:
        cp.primary_role = None
    elif payload.primary_role is not None:
        cp.primary_role = payload.primary_role
    if payload.secondary_role is not None:
        cp.secondary_role = payload.secondary_role
    if payload.notes is not None:
        cp.notes = payload.notes.strip() or None

    if payload.steam_id64 is not None or payload.steam_profile_url is not None:
        sid, url, vanity, status = _resolve_steam_fields(
            payload.steam_id64 if payload.steam_id64 is not None else cp.player.steam_id64,
            payload.steam_profile_url if payload.steam_profile_url is not None else cp.player.steam_profile_url,
        )
        if sid and sid != cp.player.steam_id64:
            conflict = db.scalar(select(Player).where(Player.steam_id64 == sid, Player.id != cp.player_id))
            if conflict:
                raise HTTPException(status_code=409, detail=f"SteamID64 {sid} already belongs to another player.")
        cp.player.steam_id64 = sid
        cp.player.steam_profile_url = url
        if vanity:
            cp.player.vanity_name = vanity
        if cp.player.identity_status != "STEAM_RESOLVED" or sid is None:
            cp.player.identity_status = status

    if payload.avatar_url is not None:
        cp.player.avatar_url = payload.avatar_url.strip() or None

    db.commit()
    db.refresh(cp)
    return to_player_out(db, cp)


def delete_player(db: Session, community_id: str, community_player_id: str) -> None:
    """Removes player from the community without deleting global Player identity or match history."""
    cp = _get_cp_or_404(db, community_id, community_player_id)
    cp.is_active = False
    db.commit()


def archive_player(db: Session, community_id: str, community_player_id: str, archived: bool = True) -> PlayerOut:
    cp = _get_cp_or_404(db, community_id, community_player_id)
    cp.is_archived = archived
    db.commit()
    return to_player_out(db, cp)


def get_player_profile(db: Session, community_id: str, community_player_id: str) -> PlayerProfileOut:
    cp = _get_cp_or_404(db, community_id, community_player_id)
    p_out = to_player_out(db, cp)
    stats_list = _stats_for_player(db, cp.player_id)
    return PlayerProfileOut(
        player=p_out,
        stat_snapshots=stats_list,
        aliases=p_out.aliases,
        external_identities=p_out.external_identities,
        match_records=_match_records_for_player(db, cp.player_id),
        provider_statuses=p_out.provider_statuses,
        card=p_out.card or _build_card_for_cp(cp, p_out.normalized_strength, p_out.strength_band, stats_list),
    )


def add_stat_snapshot(
    db: Session, community_id: str, community_player_id: str, payload: StatSnapshotCreate
) -> PlayerProfileOut:
    cp = _get_cp_or_404(db, community_id, community_player_id)
    st = PlayerStatSnapshot(
        player_id=cp.player_id,
        provider=payload.provider,
        scope=payload.scope,
        game_mode=payload.game_mode,
        season=payload.season,
        sample_size=payload.sample_size or payload.matches_played,
        matches_played=payload.matches_played or payload.sample_size,
        win_rate=payload.win_rate,
        kd_ratio=payload.kd_ratio,
        adr=payload.adr,
        kast=payload.kast,
        hs_pct=payload.hs_pct,
        opening_duel_pct=payload.opening_duel_pct,
        trade_kills_per_match=payload.trade_kills_per_match,
        utility_damage_per_round=payload.utility_damage_per_round,
        flash_assists_per_round=payload.flash_assists_per_round,
        clutch_win_pct=payload.clutch_win_pct,
        multi_kill_rate=payload.multi_kill_rate,
        consistency_score=payload.consistency_score,
        freshness="FRESH",
        is_sample_demo=False,
    )
    db.add(st)
    db.commit()
    return get_player_profile(db, community_id, community_player_id)


def update_card_settings(
    db: Session, community_id: str, community_player_id: str, payload: PlayerCardSettingsUpdate
) -> PlayerProfileOut:
    cp = _get_cp_or_404(db, community_id, community_player_id)
    if payload.humour_enabled is not None:
        cp.humour_enabled = payload.humour_enabled
    if payload.humour_intensity is not None:
        cp.humour_intensity = payload.humour_intensity
    if payload.hidden_badges is not None:
        cp.hidden_badges_json = json.dumps(payload.hidden_badges)
    if payload.regenerate_tagline:
        cp.card_tagline_variant += 1
    if payload.stats_visibility is not None:
        cp.stats_visibility = payload.stats_visibility
    if payload.profile_visibility is not None:
        cp.player.profile_visibility = payload.profile_visibility
    db.commit()
    return get_player_profile(db, community_id, community_player_id)


def compare_players(
    db: Session, community_id: str, player_a_id: str, player_b_id: str
) -> PlayerCompareOut:
    return PlayerCompareOut(
        player_a=get_player_profile(db, community_id, player_a_id),
        player_b=get_player_profile(db, community_id, player_b_id),
    )


async def refresh_player_profile(
    db: Session,
    community_id: str,
    community_player_id: str,
    force: bool = False,
    provider: str | None = None,
    steam_provider: SteamProvider | None = None,
    faceit_provider: FaceitProvider | None = None,
    leetify_provider: LeetifyProvider | None = None,
    cswatch_provider: CSWatchProvider | None = None,
) -> RefreshProfileResponse:
    """
    Single-player, single-flight deduplicated, provider-TTL-aware refresh.
    - Supports refreshing a specific provider (`steam`, `leetify`, `faceit`, `cswatch`) or `all`.
    - Respects per-provider TTLs, rate limits, timeouts, and exponential backoff.
    - Never erases last-known valid profile/stats on provider failure.
    - Returns itemized per-provider statuses (`SUCCESS`, `PARTIAL`, `PRIVATE`, `NOT_LINKED`,
      `NOT_CONFIGURED`, `RATE_LIMITED`, `UNAVAILABLE`, `FAILED`).
    """
    scope = (provider or "all").strip().lower()
    if scope not in ("all", "steam", "leetify", "faceit", "cswatch"):
        raise HTTPException(status_code=422, detail=f"Unsupported provider '{provider}'.")

    # Quick existence check before entering single-flight key
    _get_cp_or_404(db, community_id, community_player_id)

    async def _execute() -> RefreshProfileResponse:
        cp = _get_cp_or_404(db, community_id, community_player_id)
        player = cp.player
        settings = get_settings()
        now = datetime.now(timezone.utc)
        latest_map = {s.provider: s for s in _latest_snapshots_map(db, player.id)}

        def _should_skip(prov_snap_key: str, ttl_key: str) -> bool:
            if force:
                return False
            snap = latest_map.get(prov_snap_key)
            if not snap:
                return False
            if snap.status not in ("OK", "SUCCESS", "PARTIAL", "NOT_LINKED", "PRIVATE", "NOT_CONFIGURED"):
                return False
            max_age = settings.provider_cache_ttl_seconds if ttl_key == "steam" else None
            return is_provider_fresh(snap.fetched_at, ttl_key, max_age_seconds=max_age)

        # Fast-path full cache hit when all requested providers are fresh
        want_steam = scope in ("all", "steam")
        want_faceit = scope in ("all", "faceit")
        want_leetify = scope in ("all", "leetify")
        want_cswatch = scope in ("all", "cswatch") and not (
            steam_provider is not None and steam_provider.is_configured and cswatch_provider is None and scope != "cswatch"
        )

        if not force and player.steam_id64:
            all_cached = (
                (not want_steam or _should_skip("steam_profile", "steam"))
                and (not want_faceit or _should_skip("faceit", "faceit"))
                and (not want_leetify or _should_skip("leetify", "leetify"))
                and (not want_cswatch or _should_skip("cswatch", "cswatch"))
            )
            if all_cached and player.refresh_status == "OK":
                cached_results = [
                    ProviderRefreshResultOut(
                        provider=p_key,
                        status=normalize_v2_status(latest_map[p_key].status) if p_key in latest_map else "UNAVAILABLE",
                        summary=f"Cached (within TTL): {latest_map[p_key].summary}" if p_key in latest_map else "Cached",
                        cache_hit=True,
                        fetched_at=latest_map[p_key].fetched_at if p_key in latest_map else None,
                    )
                    for p_key in ("steam_profile", "leetify", "faceit", "cswatch")
                    if p_key in latest_map
                ]
                return RefreshProfileResponse(
                    profile=get_player_profile(db, community_id, community_player_id),
                    status="SUCCESS",
                    cache_hit=True,
                    alias_changed=False,
                    message="Served from cache (all requested providers within TTL).",
                    provider_results=cached_results,
                )

        steam = steam_provider or SteamProvider()
        faceit = faceit_provider or FaceitProvider()
        leetify = leetify_provider or LeetifyProvider()

        player.last_refresh_attempt_at = now
        alias_changed = False
        prov_results: list[ProviderRefreshResultOut] = []

        if not player.steam_id64 and player.vanity_name:
            if steam_provider is None:
                await throttle_provider("steam")
            resolved_sid, _ = await steam.resolve_vanity_url(player.vanity_name)
            if resolved_sid:
                conflict = db.scalar(select(Player).where(Player.steam_id64 == resolved_sid, Player.id != player.id))
                if not conflict:
                    player.steam_id64 = resolved_sid
                    player.steam_profile_url = f"https://steamcommunity.com/profiles/{resolved_sid}"
                    player.identity_status = "STEAM_RESOLVED"

        if not player.steam_id64:
            player.refresh_status = "NOT_LINKED"
            player.refresh_error = "No SteamID64 linked to refresh external providers."
            _add_provider_snapshot(
                db,
                player_id=player.id,
                provider="steam_profile",
                status="NOT_LINKED",
                endpoint_category="profile",
                summary_text="No SteamID64 linked.",
                fetched_at=now,
            )
            db.commit()
            return RefreshProfileResponse(
                profile=get_player_profile(db, community_id, community_player_id),
                status="NOT_LINKED",
                cache_hit=False,
                alias_changed=False,
                message="No SteamID64 linked; external providers cannot be queried.",
                provider_results=[
                    ProviderRefreshResultOut(
                        provider="steam_profile",
                        status="NOT_LINKED",
                        summary="No SteamID64 linked.",
                        cache_hit=False,
                        fetched_at=now,
                    )
                ],
            )

        sid = player.steam_id64

        # 1. Steam profile & official bans
        if want_steam:
            if _should_skip("steam_profile", "steam"):
                snap = latest_map["steam_profile"]
                prov_results.append(
                    ProviderRefreshResultOut(
                        provider="steam_profile",
                        status=normalize_v2_status(snap.status),
                        summary=f"Cached: {snap.summary}",
                        cache_hit=True,
                        fetched_at=snap.fetched_at,
                    )
                )
            else:
                try:
                    if steam_provider is None:
                        await throttle_provider("steam")
                    summaries = await steam.fetch_summaries([sid])
                    bans = await steam.fetch_bans([sid])
                    s_res = summaries.get(sid)
                    b_res = bans.get(sid)
                    if s_res:
                        _add_provider_snapshot(
                            db,
                            player_id=player.id,
                            provider="steam_profile",
                            status=s_res.status,
                            endpoint_category="profile",
                            player_identity=sid,
                            failure_reason=s_res.failure_reason,
                            retry_eligible=s_res.retry_eligible,
                            summary_text=s_res.summary,
                            payload=s_res.data,
                            fetched_at=now,
                        )
                        if s_res.status == "OK":
                            persona = (s_res.data or {}).get("persona_name")
                            if persona:
                                alias_changed = record_alias_if_changed(db, player, persona, source="steam_web_api")
                            avatar = (s_res.data or {}).get("avatar_url")
                            if avatar:
                                player.avatar_url = avatar
                            player.identity_status = "STEAM_RESOLVED"
                            player.last_successful_refresh_at = now
                            player.refresh_status = "OK"
                            player.refresh_error = None
                        else:
                            player.refresh_status = s_res.status
                            player.refresh_error = s_res.summary
                        prov_results.append(
                            ProviderRefreshResultOut(
                                provider="steam_profile",
                                status=normalize_v2_status(s_res.status),
                                summary=s_res.summary,
                                cache_hit=False,
                                fetched_at=now,
                            )
                        )
                    if b_res:
                        _add_provider_snapshot(
                            db,
                            player_id=player.id,
                            provider="steam_bans",
                            status=b_res.status,
                            endpoint_category="bans",
                            player_identity=sid,
                            failure_reason=b_res.failure_reason,
                            retry_eligible=b_res.retry_eligible,
                            summary_text=b_res.summary,
                            payload=b_res.data,
                            fetched_at=now,
                        )
                        prov_results.append(
                            ProviderRefreshResultOut(
                                provider="steam_bans",
                                status=normalize_v2_status(b_res.status),
                                summary=b_res.summary,
                                cache_hit=False,
                                fetched_at=now,
                            )
                        )
                except Exception as exc:
                    prov_results.append(
                        ProviderRefreshResultOut(
                            provider="steam_profile",
                            status="FAILED",
                            summary=f"Steam refresh error: {exc}",
                            cache_hit=False,
                            fetched_at=now,
                        )
                    )

        # 2. FACEIT Data API v4
        if want_faceit:
            if _should_skip("faceit", "faceit"):
                snap = latest_map["faceit"]
                prov_results.append(
                    ProviderRefreshResultOut(
                        provider="faceit",
                        status=normalize_v2_status(snap.status),
                        summary=f"Cached: {snap.summary}",
                        cache_hit=True,
                        fetched_at=snap.fetched_at,
                    )
                )
            else:
                try:
                    if faceit_provider is None and faceit.is_configured:
                        await throttle_provider("faceit")
                    f_res = await faceit.fetch_by_steam_id64(sid)
                    _add_provider_snapshot(
                        db,
                        player_id=player.id,
                        provider="faceit",
                        status=f_res.status,
                        endpoint_category="profile_and_stats",
                        player_identity=sid,
                        failure_reason=f_res.failure_reason,
                        retry_eligible=f_res.retry_eligible,
                        summary_text=f_res.summary,
                        payload=f_res.data,
                        fetched_at=now,
                    )
                    if f_res.status == "OK" and f_res.data:
                        if f_res.data.get("faceit_elo") is not None:
                            cp.faceit_elo = int(f_res.data["faceit_elo"])
                        if f_res.data.get("skill_level") is not None:
                            cp.faceit_level = int(f_res.data["skill_level"])
                        cstats = f_res.data.get("combat_stats") or {}
                        if cstats:
                            db.add(
                                PlayerStatSnapshot(
                                    player_id=player.id,
                                    provider="faceit",
                                    scope="lifetime",
                                    game_mode="FACEIT CS2",
                                    sample_size=cstats.get("matches_played"),
                                    raw_rating_label="FACEIT ELO",
                                    raw_rating_value=float(f_res.data["faceit_elo"]) if f_res.data.get("faceit_elo") else None,
                                    matches_played=cstats.get("matches_played"),
                                    win_rate=cstats.get("win_rate"),
                                    kd_ratio=cstats.get("kd_ratio"),
                                    adr=cstats.get("adr"),
                                    hs_pct=cstats.get("hs_pct"),
                                    freshness="FRESH",
                                    captured_at=now,
                                )
                            )
                    prov_results.append(
                        ProviderRefreshResultOut(
                            provider="faceit",
                            status=normalize_v2_status(f_res.status),
                            summary=f_res.summary,
                            cache_hit=False,
                            fetched_at=now,
                        )
                    )
                except Exception as exc:
                    prov_results.append(
                        ProviderRefreshResultOut(
                            provider="faceit",
                            status="FAILED",
                            summary=f"FACEIT refresh error: {exc}",
                            cache_hit=False,
                            fetched_at=now,
                        )
                    )

        # 3. Leetify Public CS API v3
        if want_leetify:
            if _should_skip("leetify", "leetify"):
                snap = latest_map["leetify"]
                prov_results.append(
                    ProviderRefreshResultOut(
                        provider="leetify",
                        status=normalize_v2_status(snap.status),
                        summary=f"Cached: {snap.summary}",
                        cache_hit=True,
                        fetched_at=snap.fetched_at,
                    )
                )
            else:
                try:
                    if leetify_provider is None:
                        await throttle_provider("leetify")
                    l_res = await leetify.fetch_by_steam_id64(sid)
                    _add_provider_snapshot(
                        db,
                        player_id=player.id,
                        provider="leetify",
                        status=l_res.status,
                        endpoint_category="profile_and_matches",
                        player_identity=sid,
                        failure_reason=l_res.failure_reason,
                        retry_eligible=l_res.retry_eligible,
                        summary_text=l_res.summary,
                        payload=l_res.data,
                        fetched_at=now,
                    )
                    if l_res.status in ("OK", "PARTIAL") and l_res.data:
                        if l_res.data.get("leetify_rating") is not None:
                            cp.leetify_rating = float(l_res.data["leetify_rating"])
                        if l_res.data.get("premier_rating") is not None:
                            cp.premier_rating = int(l_res.data["premier_rating"])
                            cp.premier_source = "leetify_public_api"
                        if l_res.data.get("faceit_elo") is not None and cp.faceit_elo is None:
                            cp.faceit_elo = int(l_res.data["faceit_elo"])
                        if l_res.data.get("faceit_level") is not None and cp.faceit_level is None:
                            cp.faceit_level = int(l_res.data["faceit_level"])
                        if l_res.data.get("aim_rating") is not None:
                            cp.aim_rating = float(l_res.data["aim_rating"])
                        if l_res.data.get("utility_rating") is not None:
                            cp.utility_rating = float(l_res.data["utility_rating"])
                        if l_res.data.get("positioning_rating") is not None:
                            cp.positioning_rating = float(l_res.data["positioning_rating"])
                        if l_res.data.get("recent_form") is not None:
                            cp.recent_form = float(l_res.data["recent_form"])
                        if l_res.data.get("map_deltas"):
                            cp.map_ratings_json = json.dumps(l_res.data["map_deltas"])
                        if l_res.data.get("persona_name"):
                            if record_alias_if_changed(db, player, l_res.data["persona_name"], source="leetify_public_api"):
                                alias_changed = True

                        lt_ext_id = str(l_res.data.get("leetify_id") or sid)
                        existing_lt = db.scalar(
                            select(PlayerExternalIdentity).where(
                                PlayerExternalIdentity.provider == "leetify",
                                PlayerExternalIdentity.external_id == lt_ext_id,
                            )
                        )
                        if not existing_lt:
                            db.add(
                                PlayerExternalIdentity(
                                    player_id=player.id,
                                    provider="leetify",
                                    external_id=lt_ext_id,
                                    profile_url=l_res.data.get("profile_url") or f"https://leetify.com/app/profile/{sid}",
                                    verification_state="VERIFIED",
                                    confidence=1.0,
                                )
                            )

                        for scope_key, cstats_key in (("recent", "combat_stats_recent10"), ("lifetime", "combat_stats_lifetime")):
                            cstats = l_res.data.get(cstats_key) or (l_res.data.get("combat_stats") if scope_key == "recent" else None) or {}
                            if cstats:
                                db.add(
                                    PlayerStatSnapshot(
                                        player_id=player.id,
                                        provider="leetify",
                                        scope=scope_key,
                                        game_mode="Leetify CS2",
                                        sample_size=cstats.get("matches_played"),
                                        raw_rating_label="Leetify Rating",
                                        raw_rating_value=float(l_res.data["leetify_rating"]) if l_res.data.get("leetify_rating") is not None else None,
                                        matches_played=cstats.get("matches_played"),
                                        win_rate=cstats.get("win_rate"),
                                        kd_ratio=cstats.get("kd_ratio"),
                                        adr=cstats.get("adr"),
                                        kast=cstats.get("kast"),
                                        hs_pct=cstats.get("hs_pct"),
                                        opening_duel_pct=cstats.get("opening_duel_pct"),
                                        trade_kills_per_match=cstats.get("trade_kills_per_match"),
                                        utility_damage_per_round=cstats.get("utility_damage_per_round"),
                                        flash_assists_per_round=cstats.get("flash_assists_per_round"),
                                        clutch_win_pct=cstats.get("clutch_win_pct"),
                                        multi_kill_rate=cstats.get("multi_kill_rate"),
                                        consistency_score=cstats.get("consistency_score"),
                                        aim_rating=cstats.get("aim_rating"),
                                        utility_rating=cstats.get("utility_rating"),
                                        positioning_rating=cstats.get("positioning_rating"),
                                        preaim=cstats.get("preaim"),
                                        reaction_time_ms=cstats.get("reaction_time_ms"),
                                        spotted_accuracy=cstats.get("spotted_accuracy"),
                                        spray_accuracy=cstats.get("spray_accuracy"),
                                        enemies_flashed_per_round=cstats.get("enemies_flashed_per_round"),
                                        traded_deaths_pct=cstats.get("traded_deaths_pct"),
                                        freshness="FRESH",
                                        captured_at=now,
                                    )
                                )

                        for m in l_res.data.get("recent_matches") or []:
                            ext_mid = m.get("external_match_id")
                            if not ext_mid:
                                continue
                            exists_m = db.scalar(
                                select(PlayerMatchRecord).where(
                                    PlayerMatchRecord.player_id == player.id,
                                    PlayerMatchRecord.provider == "leetify",
                                    PlayerMatchRecord.external_match_id == ext_mid,
                                )
                            )
                            if not exists_m:
                                played_dt = now
                                if m.get("played_at"):
                                    try:
                                        played_dt = datetime.fromisoformat(str(m["played_at"]).replace("Z", "+00:00"))
                                    except ValueError:
                                        played_dt = now
                                db.add(
                                    PlayerMatchRecord(
                                        player_id=player.id,
                                        provider="leetify",
                                        external_match_id=ext_mid,
                                        map_name=m.get("map_name"),
                                        game_mode=m.get("game_mode"),
                                        outcome=m.get("outcome"),
                                        score_text=m.get("score_text"),
                                        kd_ratio=m.get("kd_ratio"),
                                        adr=m.get("adr"),
                                        hs_pct=m.get("hs_pct"),
                                        leetify_rating=m.get("leetify_rating"),
                                        source_url=f"https://leetify.com/app/match-details/{ext_mid}",
                                        played_at=played_dt,
                                    )
                                )

                        if player.refresh_status != "OK":
                            player.last_successful_refresh_at = now
                            player.refresh_status = "OK"
                            player.refresh_error = None
                    prov_results.append(
                        ProviderRefreshResultOut(
                            provider="leetify",
                            status=normalize_v2_status(l_res.status),
                            summary=l_res.summary,
                            cache_hit=False,
                            fetched_at=now,
                        )
                    )
                except Exception as exc:
                    prov_results.append(
                        ProviderRefreshResultOut(
                            provider="leetify",
                            status="FAILED",
                            summary=f"Leetify refresh error: {exc}",
                            cache_hit=False,
                            fetched_at=now,
                        )
                    )

        # 4. CSWatch third-party trust & reputation (never alters skill rating)
        if want_cswatch:
            if _should_skip("cswatch", "cswatch"):
                snap = latest_map["cswatch"]
                prov_results.append(
                    ProviderRefreshResultOut(
                        provider="cswatch",
                        status=normalize_v2_status(snap.status),
                        summary=f"Cached: {snap.summary}",
                        cache_hit=True,
                        fetched_at=snap.fetched_at,
                    )
                )
            else:
                try:
                    if cswatch_provider is None:
                        await throttle_provider("cswatch")
                    cw = cswatch_provider or CSWatchProvider()
                    cw_res = await cw.fetch_player(sid)
                    _add_provider_snapshot(
                        db,
                        player_id=player.id,
                        provider="cswatch",
                        status=cw_res.status,
                        endpoint_category="reputation",
                        player_identity=sid,
                        failure_reason=cw_res.failure_reason,
                        retry_eligible=cw_res.retry_eligible,
                        summary_text=cw_res.summary,
                        payload=cw_res.data,
                        fetched_at=now,
                    )
                    if cw_res.data:
                        if cw_res.data.get("avatar_url") and not player.avatar_url:
                            player.avatar_url = cw_res.data["avatar_url"]
                        if cw_res.data.get("persona_name"):
                            if record_alias_if_changed(db, player, cw_res.data["persona_name"], source="cswatch_public_api"):
                                alias_changed = True
                        latest_cw_sig = db.scalar(
                            select(TrustSignal)
                            .where(
                                TrustSignal.community_id == community_id,
                                TrustSignal.player_id == player.id,
                                TrustSignal.provider == "cswatch",
                            )
                            .order_by(TrustSignal.observed_at.desc())
                            .limit(1)
                        )
                        latest_obs = _ensure_utc(latest_cw_sig.observed_at) if latest_cw_sig else None
                        if (
                            latest_cw_sig
                            and latest_cw_sig.status == cw_res.status
                            and latest_cw_sig.summary == cw_res.summary
                            and latest_obs is not None
                            and (now - latest_obs) < timedelta(hours=6)
                        ):
                            latest_cw_sig.observed_at = now
                            latest_cw_sig.payload_json = json.dumps(cw_res.data)
                        else:
                            db.add(
                                TrustSignal(
                                    community_id=community_id,
                                    player_id=player.id,
                                    category="THIRD_PARTY_REPUTATION",
                                    provider="cswatch",
                                    status=cw_res.status,
                                    summary=cw_res.summary,
                                    limitations="Third-party reputation from cswatch.gg — NOT an official Valve verdict.",
                                    source_url=cw_res.data.get("profile_url") or f"https://cswatch.gg/player/{sid}",
                                    payload_json=json.dumps(cw_res.data),
                                    observed_at=now,
                                )
                            )
                    prov_results.append(
                        ProviderRefreshResultOut(
                            provider="cswatch",
                            status=normalize_v2_status(cw_res.status),
                            summary=cw_res.summary,
                            cache_hit=False,
                            fetched_at=now,
                        )
                    )
                except Exception as exc:
                    prov_results.append(
                        ProviderRefreshResultOut(
                            provider="cswatch",
                            status="FAILED",
                            summary=f"CSWatch refresh error: {exc}",
                            cache_hit=False,
                            fetched_at=now,
                        )
                    )

        db.commit()

        statuses = [pr.status for pr in prov_results]
        if any(s == "SUCCESS" for s in statuses) and any(s in ("PARTIAL", "RATE_LIMITED", "UNAVAILABLE", "FAILED", "PRIVATE") for s in statuses):
            overall_status = "PARTIAL"
        elif any(s == "SUCCESS" for s in statuses):
            overall_status = "SUCCESS"
        elif statuses and all(s == "NOT_CONFIGURED" for s in statuses):
            overall_status = "NOT_CONFIGURED"
        elif "RATE_LIMITED" in statuses:
            overall_status = "RATE_LIMITED"
        elif "PRIVATE" in statuses:
            overall_status = "PRIVATE"
        elif "FAILED" in statuses:
            overall_status = "FAILED"
        else:
            overall_status = statuses[0] if statuses else normalize_v2_status(player.refresh_status)

        all_cached_out = bool(prov_results) and all(pr.cache_hit for pr in prov_results)
        msg = (
            "Profile refreshed; Steam username change recorded in alias history."
            if alias_changed
            else (
                f"Refreshed {cp.display_name}: "
                + ", ".join(f"{pr.provider}={pr.status}" for pr in prov_results)
            )
            if prov_results
            else f"Refresh finished ({overall_status})."
        )
        return RefreshProfileResponse(
            profile=get_player_profile(db, community_id, community_player_id),
            status=overall_status,
            cache_hit=all_cached_out,
            alias_changed=alias_changed,
            message=msg,
            provider_results=prov_results,
        )

    res, dedup_hit = await run_single_flight((community_player_id, scope), _execute)
    if dedup_hit and not res.cache_hit:
        res.cache_hit = True
    return res


async def refresh_all_players(
    db: Session,
    community_id: str,
    force: bool = False,
) -> dict:
    """Refreshes active players sequentially with TTL skips, single-flight safety, and error isolation."""
    import asyncio as _asyncio

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
    results = []
    for idx, cp in enumerate(cps):
        try:
            res = await refresh_player_profile(db, community_id, cp.id, force=force)
            results.append(
                {
                    "id": cp.id,
                    "display_name": cp.display_name,
                    "steam_id64": cp.player.steam_id64,
                    "status": res.status,
                    "refresh_status": res.profile.player.refresh_status,
                    "cache_hit": res.cache_hit,
                    "alias_changed": res.alias_changed,
                    "message": res.message,
                    "provider_results": [pr.model_dump() for pr in res.provider_results],
                }
            )
            if not res.cache_hit and cp.player.steam_id64 and idx < len(cps) - 1:
                await _asyncio.sleep(0.8)
        except Exception as exc:
            results.append(
                {
                    "id": cp.id,
                    "display_name": cp.display_name,
                    "steam_id64": cp.player.steam_id64,
                    "status": "FAILED",
                    "refresh_status": cp.player.refresh_status,
                    "cache_hit": False,
                    "alias_changed": False,
                    "message": f"Refresh failed cleanly without overwriting data: {exc}",
                    "provider_results": [],
                }
            )
    from app.services import scheduler as _scheduler

    failed_items = [r for r in results if r.get("status") in ("FAILED", "UNAVAILABLE")]
    _scheduler.record_refresh_telemetry(
        full_refresh=True,
        had_failure=bool(failed_items),
        failure_reason=failed_items[0]["message"] if failed_items else None,
    )
    return {"total": len(results), "results": results}


async def bulk_import_players(
    db: Session, community_id: str, request: BulkImportRequest
) -> BulkImportResponse:
    steam_provider = SteamProvider()
    lines = [ln.strip() for ln in request.text.splitlines() if ln.strip()]

    entries: list[BulkImportEntryResult] = []
    created_count = 0
    duplicate_count = 0
    unresolved_count = 0
    invalid_count = 0

    existing_cps = db.scalars(
        select(CommunityPlayer)
        .options(joinedload(CommunityPlayer.player))
        .where(CommunityPlayer.community_id == community_id, CommunityPlayer.is_active.is_(True))
    ).all()

    seen_steam_ids: dict[str, CommunityPlayer] = {
        cp.player.steam_id64: cp for cp in existing_cps if cp.player.steam_id64
    }
    seen_vanities: dict[str, CommunityPlayer] = {
        cp.player.vanity_name.lower(): cp for cp in existing_cps if cp.player.vanity_name
    }
    seen_manual_names: dict[str, CommunityPlayer] = {
        cp.display_name.strip().lower(): cp for cp in existing_cps if not cp.player.steam_id64
    }

    for line in lines:
        parsed = parse_import_line(line)
        if parsed.kind == "INVALID":
            invalid_count += 1
            entries.append(
                BulkImportEntryResult(
                    line=line,
                    status="INVALID",
                    message=parsed.error or "Invalid entry.",
                )
            )
            continue

        resolved_sid = parsed.steam_id64
        resolved_url = parsed.steam_profile_url
        identity_status = "STEAM_PARSED" if resolved_sid else "MANUAL_ONLY"

        if parsed.kind == "STEAM_VANITY" and parsed.vanity_name:
            if parsed.vanity_name.lower() in seen_vanities:
                duplicate_count += 1
                existing = seen_vanities[parsed.vanity_name.lower()]
                entries.append(
                    BulkImportEntryResult(
                        line=line,
                        status="DUPLICATE",
                        message=f"Duplicate vanity URL ({parsed.vanity_name}) — already saved as '{existing.display_name}'.",
                        player=to_player_out(db, existing),
                    )
                )
                continue

            sid, vanity_status = await steam_provider.resolve_vanity_url(parsed.vanity_name)
            if sid:
                resolved_sid = sid
                resolved_url = f"https://steamcommunity.com/profiles/{sid}"
                identity_status = "STEAM_RESOLVED"
            else:
                unresolved_count += 1
                reason = (
                    "Steam API key not configured; paste SteamID64 or /profiles/ URL instead."
                    if vanity_status == "NOT_CONFIGURED"
                    else f"Vanity URL '{parsed.vanity_name}' could not be resolved ({vanity_status})."
                )
                entries.append(
                    BulkImportEntryResult(
                        line=line,
                        status="UNRESOLVED",
                        message=reason,
                    )
                )
                continue

        if resolved_sid:
            if resolved_sid in seen_steam_ids:
                duplicate_count += 1
                existing = seen_steam_ids[resolved_sid]
                entries.append(
                    BulkImportEntryResult(
                        line=line,
                        status="DUPLICATE",
                        message=f"Duplicate SteamID64 ({resolved_sid}) — already saved as '{existing.display_name}'.",
                        player=to_player_out(db, existing),
                    )
                )
                continue

            display_name = parsed.display_name or f"Player {resolved_sid[-4:]}"
            created = create_player(
                db,
                community_id,
                PlayerCreate(
                    display_name=display_name,
                    steam_id64=resolved_sid,
                    steam_profile_url=resolved_url,
                    manual_rating=parsed.manual_rating or request.default_manual_rating,
                    primary_role=parsed.primary_role,  # type: ignore[arg-type]
                ),
            )
            created_cp = db.scalar(
                select(CommunityPlayer).options(joinedload(CommunityPlayer.player)).where(CommunityPlayer.id == created.id)
            )
            if created_cp:
                seen_steam_ids[resolved_sid] = created_cp
                if parsed.vanity_name:
                    created_cp.player.vanity_name = parsed.vanity_name
                if identity_status == "STEAM_RESOLVED":
                    created_cp.player.identity_status = "STEAM_RESOLVED"
                db.commit()
            created_count += 1
            entries.append(
                BulkImportEntryResult(
                    line=line,
                    status="CREATED_STEAM",
                    message=f"Imported with canonical SteamID64 {resolved_sid}.",
                    player=created,
                )
            )
            continue

        if not request.allow_manual_names:
            unresolved_count += 1
            entries.append(
                BulkImportEntryResult(
                    line=line,
                    status="UNRESOLVED",
                    message="Plain display name not treated as a Steam identity (enable manual-only import to save).",
                )
            )
            continue

        assert parsed.display_name is not None
        name_key = parsed.display_name.strip().lower()
        if name_key in seen_manual_names:
            duplicate_count += 1
            existing = seen_manual_names[name_key]
            entries.append(
                BulkImportEntryResult(
                    line=line,
                    status="DUPLICATE",
                    message=f"Manual-only player '{existing.display_name}' already exists.",
                    player=to_player_out(db, existing),
                )
            )
            continue

        created = create_player(
            db,
            community_id,
            PlayerCreate(
                display_name=parsed.display_name,
                manual_rating=parsed.manual_rating or request.default_manual_rating,
                primary_role=parsed.primary_role,  # type: ignore[arg-type]
            ),
        )
        created_cp = db.scalar(
            select(CommunityPlayer).options(joinedload(CommunityPlayer.player)).where(CommunityPlayer.id == created.id)
        )
        if created_cp:
            seen_manual_names[name_key] = created_cp
        created_count += 1
        entries.append(
            BulkImportEntryResult(
                line=line,
                status="CREATED_MANUAL",
                message="Saved as manual-only profile (no SteamID64 linked; not a verified Steam identity).",
                player=created,
            )
        )

    return BulkImportResponse(
        created_count=created_count,
        duplicate_count=duplicate_count,
        unresolved_count=unresolved_count,
        invalid_count=invalid_count,
        entries=entries,
    )


async def run_preflight_for_players(db: Session, community_id: str, community_player_ids: list[str]) -> list[PlayerOut]:
    """
    Pre-match refresh for selected room players via refresh_player_profile:
    - Refreshes Steam persona/avatar, Leetify profile + stats + recent matches,
      CSWatch reputation/trust signals, and FACEIT (when configured).
    - Respects provider TTL caching, timeouts, and rate-limit pacing.
    - Preserves last known stored data if any provider fails.
    """
    import asyncio as _asyncio

    cps = db.scalars(
        select(CommunityPlayer)
        .options(joinedload(CommunityPlayer.player))
        .where(
            CommunityPlayer.community_id == community_id,
            CommunityPlayer.id.in_(community_player_ids),
            CommunityPlayer.is_active.is_(True),
        )
    ).all()
    by_id = {cp.id: cp for cp in cps}
    ordered_cps = [by_id[pid] for pid in community_player_ids if pid in by_id]

    out: list[PlayerOut] = []
    for idx, cp in enumerate(ordered_cps):
        res = await refresh_player_profile(db, community_id, cp.id, force=False)
        out.append(res.profile.player)
        if not res.cache_hit and cp.player.steam_id64 and idx < len(ordered_cps) - 1:
            await _asyncio.sleep(0.6)
    return out


DEMO_PLAYERS = [
    ("Kairo [DEMO]", 82.0, "AWPer", 19500, 1980, None, "Demo seeded player — high AWP impact",
     {"matches": 24, "win_rate": 58.3, "kd": 1.32, "adr": 88.4, "kast": 74.5, "hs": 42.0, "open": 56.0, "util": 12.1, "flash": 0.14, "clutch": 31.5}),
    ("Vexen [DEMO]", 78.0, "IGL", 18200, 1840, None, "Demo seeded player — caller & utility",
     {"matches": 24, "win_rate": 56.0, "kd": 1.06, "adr": 76.2, "kast": 73.1, "hs": 48.0, "open": 47.0, "util": 22.8, "flash": 0.29, "clutch": 21.0}),
    ("Mako [DEMO]", 74.0, "Entry", 16400, None, 0.04, "Demo seeded player — aggressive entry",
     {"matches": 22, "win_rate": 52.0, "kd": 1.11, "adr": 86.5, "kast": 69.0, "hs": 57.5, "open": 58.4, "util": 10.4, "flash": 0.11, "clutch": 16.0}),
    ("Nori [DEMO]", 71.0, "Rifler", 15600, None, None, "Demo seeded player",
     {"matches": 18, "win_rate": 50.0, "kd": 1.04, "adr": 77.8, "kast": 71.2, "hs": 52.0, "open": 49.0, "util": 14.2, "flash": 0.17, "clutch": 19.0}),
    ("Sora [DEMO]", 67.0, "Support", None, 1520, None, "Demo seeded player — FACEIT & flash support",
     {"matches": 20, "win_rate": 51.0, "kd": 0.96, "adr": 71.0, "kast": 75.4, "hs": 44.0, "open": 43.0, "util": 21.4, "flash": 0.34, "clutch": 18.0}),
    ("Dax [DEMO]", 63.0, "Lurker", 13200, None, -0.01, "Demo seeded player — late-round lurker",
     {"matches": 16, "win_rate": 49.0, "kd": 1.26, "adr": 75.4, "kast": 64.5, "hs": 49.0, "open": 44.0, "util": 11.2, "flash": 0.09, "clutch": 26.5}),
    ("Riven [DEMO]", 59.0, "Entry", None, None, None, "Demo seeded player — fearless entry",
     {"matches": 14, "win_rate": 46.5, "kd": 0.89, "adr": 69.2, "kast": 66.0, "hs": 45.0, "open": 39.2, "util": 9.8, "flash": 0.10, "clutch": 12.0}),
    ("Taro [DEMO]", 54.0, "AWPer", None, None, None, "Demo seeded player — secondary AWP",
     None),
    ("Juno [DEMO]", 49.0, "Support", 10400, None, None, "Demo seeded player",
     {"matches": 12, "win_rate": 44.0, "kd": 0.74, "adr": 55.2, "kast": 62.0, "hs": 38.0, "open": 36.0, "util": 15.0, "flash": 0.18, "clutch": 11.0}),
    ("Kip [DEMO]", 43.0, "Rifler", None, None, None, "Demo seeded player — manual rating only",
     None),
]


def seed_demo_players(db: Session, community_id: str) -> list[PlayerOut]:
    existing = db.scalars(
        select(CommunityPlayer).where(
            CommunityPlayer.community_id == community_id,
            CommunityPlayer.is_active.is_(True),
        )
    ).all()
    existing_names = {cp.display_name.lower() for cp in existing}
    created: list[PlayerOut] = []
    for idx, (name, rating, role, premier, faceit, leetify, note, stats) in enumerate(DEMO_PLAYERS):
        if name.lower() in existing_names:
            continue
        p_out = create_player(
            db,
            community_id,
            PlayerCreate(
                display_name=name,
                manual_rating=rating,
                primary_role=role,  # type: ignore[arg-type]
                premier_rating=premier,
                premier_source="demo_sample" if premier else None,
                faceit_elo=faceit,
                leetify_rating=leetify,
                notes=note,
            ),
            is_seeded=True,
        )
        if stats:
            db.add(
                PlayerStatSnapshot(
                    player_id=p_out.player_id,
                    provider="community_match",
                    scope="recent",
                    game_mode="Demo 5v5 Sample",
                    sample_size=stats["matches"],
                    matches_played=stats["matches"],
                    win_rate=stats["win_rate"],
                    kd_ratio=stats["kd"],
                    adr=stats["adr"],
                    kast=stats["kast"],
                    hs_pct=stats["hs"],
                    opening_duel_pct=stats["open"],
                    utility_damage_per_round=stats["util"],
                    flash_assists_per_round=stats["flash"],
                    clutch_win_pct=stats["clutch"],
                    freshness="DEMO_SAMPLE",
                    is_sample_demo=True,
                )
            )
        if idx == 0:
            db.add(
                PlayerAlias(
                    player_id=p_out.player_id,
                    alias_name="Kairo [DEMO]",
                    previous_name="kairo_awp_2025",
                    source="demo_sample",
                )
            )
        elif idx == 2:
            db.add(
                PlayerAlias(
                    player_id=p_out.player_id,
                    alias_name="Mako [DEMO]",
                    previous_name="mako_wkey",
                    source="demo_sample",
                )
            )
        db.commit()
        created.append(to_player_out(db, _get_cp_or_404(db, community_id, p_out.id)))
    return created
