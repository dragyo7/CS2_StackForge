from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import (
    AuditEvent,
    Community,
    CommunityPlayer,
    Player,
    PlayerAlias,
    PlayerStatSnapshot,
    ProviderSnapshot,
)
from app.optimizer.normalizer import PlayerInput, normalize_player
from app.providers.external import FaceitProvider, LeetifyProvider
from app.providers.steam import SteamProvider
from app.schemas import (
    AliasOut,
    BulkImportEntryResult,
    BulkImportRequest,
    BulkImportResponse,
    PlayerCardOut,
    PlayerCardSettingsUpdate,
    PlayerCompareOut,
    PlayerCreate,
    PlayerOut,
    PlayerProfileOut,
    PlayerUpdate,
    ProviderStatusOut,
    RefreshProfileResponse,
    StatSnapshotCreate,
    StatSnapshotOut,
)
from app.services.humour_engine import CardMetricContext, generate_player_card
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
    return [_stat_to_out(st) for st in rows]


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


def to_player_out(db: Session, cp: CommunityPlayer) -> PlayerOut:
    p = cp.player
    map_ratings: dict[str, float] = {}
    if cp.map_ratings_json:
        try:
            map_ratings = json.loads(cp.map_ratings_json)
        except json.JSONDecodeError:
            map_ratings = {}

    norm = normalize_player(
        PlayerInput(
            community_player_id=cp.id,
            display_name=cp.display_name,
            steam_id64=p.steam_id64,
            identity_status=p.identity_status,
            manual_rating=cp.manual_rating,
            premier_rating=cp.premier_rating,
            premier_source=cp.premier_source,
            premier_season=cp.premier_season,
            faceit_elo=cp.faceit_elo,
            leetify_rating=cp.leetify_rating,
            recent_form=cp.recent_form,
            primary_role=cp.primary_role,
            secondary_role=cp.secondary_role,
            map_ratings=map_ratings,
        )
    )
    aliases = _aliases_for_player(db, p.id)
    stats_list = _stats_for_player(db, p.id)
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
        leetify_rating=cp.leetify_rating,
        recent_form=cp.recent_form,
        primary_role=cp.primary_role,
        secondary_role=cp.secondary_role,
        notes=cp.notes,
        is_seeded=cp.is_seeded,
        normalized_strength=norm.normalized_strength,
        confidence=norm.confidence,
        strength_band=norm.strength_band,
        missing_sources=norm.missing_sources,
        provider_statuses=_latest_snapshots_map(db, p.id),
        aliases=aliases,
        latest_stats=stats_list[0] if stats_list else None,
        card=card,
        created_at=cp.created_at,
        updated_at=cp.updated_at,
    )


def list_players(db: Session, community_id: str, query: str | None = None) -> list[PlayerOut]:
    stmt = (
        select(CommunityPlayer)
        .options(joinedload(CommunityPlayer.player).joinedload(Player.aliases))
        .where(CommunityPlayer.community_id == community_id, CommunityPlayer.is_active.is_(True))
        .order_by(CommunityPlayer.display_name.asc())
    )
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
    return [to_player_out(db, cp) for cp in rows]


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


def create_player(db: Session, community_id: str, payload: PlayerCreate, is_seeded: bool = False) -> PlayerOut:
    steam_id64, steam_url, vanity, identity_status = _resolve_steam_fields(
        payload.steam_id64, payload.steam_profile_url
    )

    global_player: Player | None = None
    if steam_id64:
        global_player = db.scalar(select(Player).where(Player.steam_id64 == steam_id64))
        if global_player:
            existing_cp = db.scalar(
                select(CommunityPlayer).where(
                    CommunityPlayer.community_id == community_id,
                    CommunityPlayer.player_id == global_player.id,
                    CommunityPlayer.is_active.is_(True),
                )
            )
            if existing_cp:
                raise HTTPException(
                    status_code=409,
                    detail=f"Duplicate SteamID64 {steam_id64}: already registered as '{existing_cp.display_name}'.",
                )

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
    cp = _get_cp_or_404(db, community_id, community_player_id)
    db.delete(cp)
    db.commit()


def get_player_profile(db: Session, community_id: str, community_player_id: str) -> PlayerProfileOut:
    cp = _get_cp_or_404(db, community_id, community_player_id)
    p_out = to_player_out(db, cp)
    stats_list = _stats_for_player(db, cp.player_id)
    return PlayerProfileOut(
        player=p_out,
        stat_snapshots=stats_list,
        aliases=p_out.aliases,
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
    steam_provider: SteamProvider | None = None,
    faceit_provider: FaceitProvider | None = None,
    leetify_provider: LeetifyProvider | None = None,
) -> RefreshProfileResponse:
    """
    Cache-TTL-aware profile refresh.
    - Tracks last_refresh_attempt_at and last_successful_refresh_at separately.
    - Records append-only PlayerAlias when Steam display name changes.
    - Never erases last-known valid profile/stats on provider failure.
    """
    cp = _get_cp_or_404(db, community_id, community_player_id)
    player = cp.player
    settings = get_settings()
    now = datetime.now(timezone.utc)

    last_ok = _ensure_utc(player.last_successful_refresh_at)
    if (
        not force
        and last_ok is not None
        and player.refresh_status == "OK"
        and (now - last_ok) < timedelta(seconds=settings.provider_cache_ttl_seconds)
    ):
        return RefreshProfileResponse(
            profile=get_player_profile(db, community_id, community_player_id),
            cache_hit=True,
            alias_changed=False,
            message="Served from cache (within refresh TTL).",
        )

    steam = steam_provider or SteamProvider()
    faceit = faceit_provider or FaceitProvider()
    leetify = leetify_provider or LeetifyProvider()

    player.last_refresh_attempt_at = now
    alias_changed = False

    if not player.steam_id64 and player.vanity_name:
        resolved_sid, van_status = await steam.resolve_vanity_url(player.vanity_name)
        if resolved_sid:
            conflict = db.scalar(select(Player).where(Player.steam_id64 == resolved_sid, Player.id != player.id))
            if not conflict:
                player.steam_id64 = resolved_sid
                player.steam_profile_url = f"https://steamcommunity.com/profiles/{resolved_sid}"
                player.identity_status = "STEAM_RESOLVED"

    if not player.steam_id64:
        player.refresh_status = "NOT_LINKED"
        player.refresh_error = "No SteamID64 linked to refresh external providers."
        db.add(
            ProviderSnapshot(
                player_id=player.id,
                provider="steam_profile",
                status="NOT_LINKED",
                summary_text="Manual-only profile (no SteamID64 linked).",
                fetched_at=now,
            )
        )
        db.commit()
        return RefreshProfileResponse(
            profile=get_player_profile(db, community_id, community_player_id),
            cache_hit=False,
            alias_changed=False,
            message="No SteamID64 linked; manual profile retained.",
        )

    sid = player.steam_id64
    summaries = await steam.fetch_summaries([sid])
    bans = await steam.fetch_bans([sid])
    s_res = summaries.get(sid)
    b_res = bans.get(sid)

    if s_res:
        db.add(
            ProviderSnapshot(
                player_id=player.id,
                provider="steam_profile",
                status=s_res.status,
                summary_text=s_res.summary,
                payload_json=json.dumps(s_res.data) if s_res.data else None,
                fetched_at=now,
            )
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
            # Keep previous valid persona/avatar intact!
            player.refresh_status = s_res.status
            player.refresh_error = s_res.summary

    if b_res:
        db.add(
            ProviderSnapshot(
                player_id=player.id,
                provider="steam_bans",
                status=b_res.status,
                summary_text=b_res.summary,
                payload_json=json.dumps(b_res.data) if b_res.data else None,
                fetched_at=now,
            )
        )

    f_res = await faceit.fetch_by_steam_id64(sid)
    db.add(
        ProviderSnapshot(
            player_id=player.id,
            provider="faceit",
            status=f_res.status,
            summary_text=f_res.summary,
            payload_json=json.dumps(f_res.data) if f_res.data else None,
            fetched_at=now,
        )
    )
    if f_res.status == "OK" and f_res.data:
        if f_res.data.get("faceit_elo") is not None:
            cp.faceit_elo = int(f_res.data["faceit_elo"])
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

    l_res = await leetify.fetch_by_steam_id64(sid)
    db.add(
        ProviderSnapshot(
            player_id=player.id,
            provider="leetify",
            status=l_res.status,
            summary_text=l_res.summary,
            payload_json=json.dumps(l_res.data) if l_res.data else None,
            fetched_at=now,
        )
    )
    if l_res.status == "OK" and l_res.data:
        if l_res.data.get("leetify_rating") is not None:
            cp.leetify_rating = float(l_res.data["leetify_rating"])
        if l_res.data.get("premier_rating") is not None:
            cp.premier_rating = int(l_res.data["premier_rating"])
            cp.premier_source = "leetify_public_api"
        cstats = l_res.data.get("combat_stats") or {}
        if cstats:
            db.add(
                PlayerStatSnapshot(
                    player_id=player.id,
                    provider="leetify",
                    scope="recent",
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
                    utility_damage_per_round=cstats.get("utility_damage_per_round"),
                    flash_assists_per_round=cstats.get("flash_assists_per_round"),
                    clutch_win_pct=cstats.get("clutch_win_pct"),
                    freshness="FRESH",
                    captured_at=now,
                )
            )

    db.commit()
    msg = (
        "Profile refreshed; Steam username change recorded in alias history."
        if alias_changed
        else (
            "Profile refreshed from Steam/external providers."
            if player.refresh_status == "OK"
            else f"Refresh unavailable ({player.refresh_status}): preserved last known profile."
        )
    )
    return RefreshProfileResponse(
        profile=get_player_profile(db, community_id, community_player_id),
        cache_hit=False,
        alias_changed=alias_changed,
        message=msg,
    )


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
    """Non-blocking preflight across Steam, FACEIT, and Leetify."""
    cps = db.scalars(
        select(CommunityPlayer)
        .options(joinedload(CommunityPlayer.player))
        .where(
            CommunityPlayer.community_id == community_id,
            CommunityPlayer.id.in_(community_player_ids),
            CommunityPlayer.is_active.is_(True),
        )
    ).all()

    steam = SteamProvider()
    faceit = FaceitProvider()
    leetify = LeetifyProvider()

    steam_ids = [cp.player.steam_id64 for cp in cps if cp.player.steam_id64]
    summaries = await steam.fetch_summaries(steam_ids)
    bans = await steam.fetch_bans(steam_ids)

    now = datetime.now(timezone.utc)
    for cp in cps:
        sid = cp.player.steam_id64
        if not sid:
            db.add(
                ProviderSnapshot(
                    player_id=cp.player_id,
                    provider="steam_profile",
                    status="NOT_LINKED",
                    summary_text="Manual-only profile (no SteamID64 linked).",
                    fetched_at=now,
                )
            )
            continue

        cp.player.last_refresh_attempt_at = now
        s_res = summaries.get(sid)
        if s_res:
            if s_res.status == "OK" and s_res.data:
                record_alias_if_changed(db, cp.player, s_res.data.get("persona_name"), source="steam_web_api")
                if s_res.data.get("avatar_url"):
                    cp.player.avatar_url = s_res.data["avatar_url"]
                cp.player.identity_status = "STEAM_RESOLVED"
                cp.player.last_successful_refresh_at = now
                cp.player.refresh_status = "OK"
                cp.player.refresh_error = None
            else:
                cp.player.refresh_status = s_res.status
                cp.player.refresh_error = s_res.summary
            db.add(
                ProviderSnapshot(
                    player_id=cp.player_id,
                    provider="steam_profile",
                    status=s_res.status,
                    summary_text=s_res.summary,
                    payload_json=json.dumps(s_res.data) if s_res.data else None,
                    fetched_at=now,
                )
            )

        b_res = bans.get(sid)
        if b_res:
            db.add(
                ProviderSnapshot(
                    player_id=cp.player_id,
                    provider="steam_bans",
                    status=b_res.status,
                    summary_text=b_res.summary,
                    payload_json=json.dumps(b_res.data) if b_res.data else None,
                    fetched_at=now,
                )
            )

        f_res = await faceit.fetch_by_steam_id64(sid)
        if f_res.status == "OK" and f_res.data.get("faceit_elo"):
            cp.faceit_elo = int(f_res.data["faceit_elo"])
        db.add(
            ProviderSnapshot(
                player_id=cp.player_id,
                provider="faceit",
                status=f_res.status,
                summary_text=f_res.summary,
                payload_json=json.dumps(f_res.data) if f_res.data else None,
                fetched_at=now,
            )
        )

        l_res = await leetify.fetch_by_steam_id64(sid)
        if l_res.status == "OK":
            if l_res.data.get("leetify_rating") is not None:
                cp.leetify_rating = float(l_res.data["leetify_rating"])
            if l_res.data.get("premier_rating") is not None:
                cp.premier_rating = int(l_res.data["premier_rating"])
                cp.premier_source = "leetify_public_api"
        db.add(
            ProviderSnapshot(
                player_id=cp.player_id,
                provider="leetify",
                status=l_res.status,
                summary_text=l_res.summary,
                payload_json=json.dumps(l_res.data) if l_res.data else None,
                fetched_at=now,
            )
        )

    db.commit()
    return [to_player_out(db, cp) for cp in cps]


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
