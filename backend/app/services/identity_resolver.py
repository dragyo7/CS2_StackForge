from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import CommunityPlayer, Player, PlayerAlias, PlayerExternalIdentity
from app.providers.cswatch import CSWatchProvider
from app.providers.external import FaceitProvider, LeetifyProvider
from app.providers.steam import SteamProvider
from app.services.steam_parser import detect_universal_identifier


def upsert_external_identity(
    db: Session,
    player_id: str,
    provider: str,
    external_id: str,
    profile_url: str | None = None,
    verification_state: str = "VERIFIED",
    confidence: float = 1.0,
    metadata: dict[str, Any] | None = None,
) -> PlayerExternalIdentity:
    existing = db.scalar(
        select(PlayerExternalIdentity).where(
            PlayerExternalIdentity.provider == provider,
            PlayerExternalIdentity.external_id == external_id,
        )
    )
    if existing:
        if existing.player_id == player_id:
            if profile_url:
                existing.profile_url = profile_url
            existing.verification_state = verification_state
            existing.confidence = confidence
            if metadata is not None:
                existing.metadata_json = json.dumps(metadata)
            return existing
        # Different player already owns this verified provider ID; do not merge silently!
        raise HTTPException(
            status_code=409,
            detail=f"{provider} identity '{external_id}' is already linked to another player.",
        )

    rec = PlayerExternalIdentity(
        player_id=player_id,
        provider=provider,
        external_id=external_id,
        profile_url=profile_url,
        verification_state=verification_state,
        confidence=confidence,
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    db.add(rec)
    return rec


async def resolve_identifier(
    db: Session,
    community_id: str,
    raw_query: str,
    discover_providers: bool = True,
    steam_provider: SteamProvider | None = None,
    leetify_provider: LeetifyProvider | None = None,
    faceit_provider: FaceitProvider | None = None,
    cswatch_provider: CSWatchProvider | None = None,
) -> dict[str, Any]:
    """
    Universal player identity resolver.
    Detects input type, resolves stable SteamID64 / provider IDs where authorized,
    discovers cross-provider identities, and never auto-merges by display name alone.
    """
    det = detect_universal_identifier(raw_query)
    steam = steam_provider or SteamProvider()
    leetify = leetify_provider or LeetifyProvider()
    faceit = faceit_provider or FaceitProvider()
    cswatch = cswatch_provider or CSWatchProvider()

    resolved_steam_id64 = det.steam_id64
    provider_discoveries: list[dict[str, Any]] = []
    confidence_state = "UNRESOLVED"
    message = ""

    # 1. Vanity URL resolution via Steam Web API (if configured)
    if det.identifier_type == "steam_vanity_url" and det.vanity_name:
        sid, status = await steam.resolve_vanity_url(det.vanity_name)
        if sid:
            resolved_steam_id64 = sid
            confidence_state = "VERIFIED"
            message = f"Resolved vanity '{det.vanity_name}' to SteamID64 {sid}."
        else:
            message = (
                "Steam API key not configured to resolve vanity URL."
                if status == "NOT_CONFIGURED"
                else f"Could not resolve Steam vanity URL '{det.vanity_name}' ({status})."
            )

    # 2. FACEIT profile URL -> resolve via FACEIT Data API if configured
    elif det.identifier_type == "faceit_url" and det.faceit_nickname:
        f_res = await faceit.fetch_by_nickname(det.faceit_nickname)
        provider_discoveries.append(
            {
                "provider": "faceit",
                "status": f_res.status,
                "summary": f_res.summary,
                "external_id": (f_res.data or {}).get("faceit_player_id"),
                "profile_url": det.profile_url,
                "steam_id64": (f_res.data or {}).get("steam_id64"),
            }
        )
        if f_res.status == "OK" and (f_res.data or {}).get("steam_id64"):
            resolved_steam_id64 = str(f_res.data["steam_id64"])
            confidence_state = "VERIFIED"
            message = f"Resolved FACEIT '{det.faceit_nickname}' to SteamID64 {resolved_steam_id64}."
        else:
            message = f_res.summary

    elif resolved_steam_id64:
        confidence_state = "VERIFIED"
        message = f"Canonical SteamID64 {resolved_steam_id64} extracted from {det.identifier_type}."

    # 3. Search existing community players (canonical SteamID64 + nickname/alias candidates)
    cps = db.scalars(
        select(CommunityPlayer)
        .options(
            joinedload(CommunityPlayer.player).joinedload(Player.aliases),
            joinedload(CommunityPlayer.player).joinedload(Player.external_identities),
        )
        .where(CommunityPlayer.community_id == community_id, CommunityPlayer.is_active.is_(True))
    ).unique().all()

    matched_existing: list[dict[str, Any]] = []
    if resolved_steam_id64:
        for cp in cps:
            if cp.player.steam_id64 == resolved_steam_id64:
                matched_existing.append(
                    {
                        "community_player_id": cp.id,
                        "display_name": cp.display_name,
                        "steam_id64": cp.player.steam_id64,
                        "match_reason": "Canonical SteamID64 match",
                        "confidence_state": "VERIFIED",
                    }
                )
    else:
        q_low = det.normalized_value.strip().lower()
        for cp in cps:
            p = cp.player
            if not q_low:
                continue
            reasons = []
            if q_low in cp.display_name.lower():
                reasons.append("Community nickname")
            if p.steam_persona_name and q_low in p.steam_persona_name.lower():
                reasons.append("Steam persona")
            if p.vanity_name and q_low == p.vanity_name.lower():
                reasons.append("Steam vanity")
            if any(q_low in a.alias_name.lower() for a in p.aliases):
                reasons.append("Historical alias")
            if reasons:
                matched_existing.append(
                    {
                        "community_player_id": cp.id,
                        "display_name": cp.display_name,
                        "steam_id64": p.steam_id64,
                        "match_reason": ", ".join(reasons) + " (display name match is CANDIDATE only)",
                        "confidence_state": "CANDIDATE",
                    }
                )
        if matched_existing:
            confidence_state = "CANDIDATE"
            message = f"Found {len(matched_existing)} candidate player(s) by name/alias. Confirm manually — names alone never auto-merge."
        elif not message:
            message = "Unresolved identifier. Provide a SteamID64, Steam /profiles/ URL, or CSStats/Leetify URL."

    # 4. Cross-provider discovery when we have a verified SteamID64
    if resolved_steam_id64 and discover_providers:
        provider_discoveries.append(
            {
                "provider": "steam",
                "status": "VERIFIED_ID",
                "summary": f"SteamID64 {resolved_steam_id64}",
                "external_id": resolved_steam_id64,
                "profile_url": f"https://steamcommunity.com/profiles/{resolved_steam_id64}",
            }
        )
        provider_discoveries.append(
            {
                "provider": "csstats",
                "status": "LINK_ONLY",
                "summary": "CSStats profile link (no public API; manual/CSV only)",
                "external_id": resolved_steam_id64,
                "profile_url": f"https://csstats.gg/player/{resolved_steam_id64}",
            }
        )

        lt = await leetify.fetch_by_steam_id64(resolved_steam_id64, include_matches=False)
        provider_discoveries.append(
            {
                "provider": "leetify",
                "status": lt.status,
                "summary": lt.summary,
                "external_id": (lt.data or {}).get("leetify_id") or resolved_steam_id64,
                "profile_url": (lt.data or {}).get("profile_url") or f"https://leetify.com/app/profile/{resolved_steam_id64}",
                "persona_name": (lt.data or {}).get("persona_name"),
                "premier_rating": (lt.data or {}).get("premier_rating"),
                "leetify_rating": (lt.data or {}).get("leetify_rating"),
                "faceit_elo": (lt.data or {}).get("faceit_elo"),
            }
        )

        cw = await cswatch.fetch_player(resolved_steam_id64)
        provider_discoveries.append(
            {
                "provider": "cswatch",
                "status": cw.status,
                "summary": cw.summary,
                "external_id": resolved_steam_id64,
                "profile_url": (cw.data or {}).get("profile_url") or f"https://cswatch.gg/player/{resolved_steam_id64}",
                "persona_name": (cw.data or {}).get("persona_name"),
                "avatar_url": (cw.data or {}).get("avatar_url"),
                "reputation_score": (cw.data or {}).get("reputation_score"),
                "risk_level": (cw.data or {}).get("risk_level"),
            }
        )

        fc = await faceit.fetch_by_steam_id64(resolved_steam_id64)
        provider_discoveries.append(
            {
                "provider": "faceit",
                "status": fc.status,
                "summary": fc.summary,
                "external_id": (fc.data or {}).get("faceit_player_id"),
                "profile_url": (fc.data or {}).get("profile_url"),
                "faceit_elo": (fc.data or {}).get("faceit_elo"),
            }
        )

    return {
        "raw_input": raw_query,
        "identifier_type": det.identifier_type,
        "confidence_state": confidence_state,
        "resolved_steam_id64": resolved_steam_id64,
        "message": message,
        "matched_existing": matched_existing,
        "provider_discoveries": provider_discoveries,
    }


def confirm_identity_link(
    db: Session,
    community_id: str,
    community_player_id: str,
    provider: str,
    external_id: str,
    profile_url: str | None = None,
    steam_id64: str | None = None,
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

    if steam_id64:
        conflict = db.scalar(
            select(Player).where(Player.steam_id64 == steam_id64, Player.id != cp.player_id)
        )
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"SteamID64 {steam_id64} is already bound to another player.",
            )
        cp.player.steam_id64 = steam_id64
        cp.player.steam_profile_url = f"https://steamcommunity.com/profiles/{steam_id64}"
        cp.player.identity_status = "STEAM_RESOLVED"

    rec = upsert_external_identity(
        db=db,
        player_id=cp.player_id,
        provider=provider,
        external_id=external_id,
        profile_url=profile_url,
        verification_state="VERIFIED",
        confidence=1.0,
    )
    db.commit()
    db.refresh(rec)
    return {
        "id": rec.id,
        "provider": rec.provider,
        "external_id": rec.external_id,
        "profile_url": rec.profile_url,
        "verification_state": rec.verification_state,
        "confidence": rec.confidence,
    }
