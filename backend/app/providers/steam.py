from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings
from app.providers.base import ProviderResult


class SteamProvider:
    """Server-side Steam Web API adapter with bounded timeouts and non-blocking failure."""

    BASE_URL = "https://api.steampowered.com"

    def __init__(self, api_key: str | None = None, timeout: float | None = None):
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.steam_api_key
        self.timeout = timeout if timeout is not None else settings.provider_timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def resolve_vanity_url(self, vanity_name: str) -> tuple[str | None, str]:
        if not self.api_key:
            return None, "NOT_CONFIGURED"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/ISteamUser/ResolveVanityURL/v1/",
                    params={"key": self.api_key, "vanityurl": vanity_name},
                )
            if resp.status_code != 200:
                return None, "UNAVAILABLE"
            payload = resp.json().get("response", {})
            if payload.get("success") == 1 and payload.get("steamid"):
                return str(payload["steamid"]), "OK"
            return None, "NOT_FOUND"
        except Exception:
            return None, "UNAVAILABLE"

    async def fetch_summaries(self, steam_ids: list[str]) -> dict[str, ProviderResult]:
        if not steam_ids:
            return {}
        if not self.api_key:
            return {
                sid: ProviderResult(
                    provider="steam_profile",
                    status="NOT_CONFIGURED",
                    summary="Steam API key not configured (manual/cached mode active).",
                )
                for sid in steam_ids
            }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/ISteamUser/GetPlayerSummaries/v2/",
                    params={"key": self.api_key, "steamids": ",".join(steam_ids[:100])},
                )
            if resp.status_code != 200:
                return {
                    sid: ProviderResult(
                        provider="steam_profile",
                        status="UNAVAILABLE",
                        summary=f"Steam summaries unavailable (HTTP {resp.status_code}).",
                    )
                    for sid in steam_ids
                }
            players = resp.json().get("response", {}).get("players", [])
            by_id = {str(p.get("steamid")): p for p in players if p.get("steamid")}
            results: dict[str, ProviderResult] = {}
            for sid in steam_ids:
                p = by_id.get(sid)
                if not p:
                    results[sid] = ProviderResult(
                        provider="steam_profile",
                        status="UNKNOWN",
                        summary="Steam profile not returned for SteamID64.",
                    )
                else:
                    visibility = p.get("communityvisibilitystate")
                    vis_label = "Public" if visibility == 3 else "Private/Limited"
                    results[sid] = ProviderResult(
                        provider="steam_profile",
                        status="OK",
                        summary=f"{p.get('personaname', 'Unknown')} ({vis_label} profile)",
                        data={
                            "persona_name": p.get("personaname"),
                            "avatar_url": p.get("avatarfull") or p.get("avatarmedium"),
                            "profile_url": p.get("profileurl"),
                            "visibility": vis_label,
                        },
                    )
            return results
        except Exception:
            return {
                sid: ProviderResult(
                    provider="steam_profile",
                    status="UNAVAILABLE",
                    summary="Steam summaries request timed out or failed.",
                )
                for sid in steam_ids
            }

    async def fetch_bans(self, steam_ids: list[str]) -> dict[str, ProviderResult]:
        """
        Fetches Steam ban fields. Never labels an account 'clean',
        and never claims a generic game ban count is a CS2 cheat conviction.
        """
        if not steam_ids:
            return {}
        if not self.api_key:
            return {
                sid: ProviderResult(
                    provider="steam_bans",
                    status="NOT_CONFIGURED",
                    summary="Steam API key not configured; ban status not checked.",
                )
                for sid in steam_ids
            }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/ISteamUser/GetPlayerBans/v1/",
                    params={"key": self.api_key, "steamids": ",".join(steam_ids[:100])},
                )
            if resp.status_code != 200:
                return {
                    sid: ProviderResult(
                        provider="steam_bans",
                        status="UNAVAILABLE",
                        summary=f"Steam bans endpoint unavailable (HTTP {resp.status_code}).",
                    )
                    for sid in steam_ids
                }
            players = resp.json().get("players", [])
            by_id: dict[str, dict[str, Any]] = {str(p.get("SteamId")): p for p in players if p.get("SteamId")}
            results: dict[str, ProviderResult] = {}
            for sid in steam_ids:
                b = by_id.get(sid)
                if not b:
                    results[sid] = ProviderResult(
                        provider="steam_bans",
                        status="UNKNOWN",
                        summary="No ban entry returned by Steam at check time.",
                    )
                    continue
                vac_count = int(b.get("NumberOfVACBans", 0) or 0)
                game_count = int(b.get("NumberOfGameBans", 0) or 0)
                days_since = b.get("DaysSinceLastBan")
                econ = b.get("EconomyBan", "none")
                comm = bool(b.get("CommunityBanned", False))
                has_ban = vac_count > 0 or game_count > 0 or comm or (econ and econ != "none")
                if has_ban:
                    parts = []
                    if vac_count > 0:
                        parts.append(f"{vac_count} VAC ban(s)")
                    if game_count > 0:
                        parts.append(f"{game_count} game ban(s) (game context unavailable from endpoint)")
                    if comm:
                        parts.append("community ban")
                    if econ and econ != "none":
                        parts.append(f"economy ban: {econ}")
                    if days_since is not None and (vac_count > 0 or game_count > 0):
                        parts.append(f"last ban {days_since}d ago")
                    summary = "Steam reports: " + ", ".join(parts) + "."
                    status = "FLAGGED"
                else:
                    summary = "No Steam VAC/game ban record found by Steam API at check time."
                    status = "OK"
                results[sid] = ProviderResult(
                    provider="steam_bans",
                    status=status,
                    summary=summary,
                    data={
                        "vac_banned": bool(b.get("VACBanned", False)),
                        "number_of_vac_bans": vac_count,
                        "number_of_game_bans": game_count,
                        "days_since_last_ban": days_since,
                        "community_banned": comm,
                        "economy_ban": econ,
                    },
                )
            return results
        except Exception:
            return {
                sid: ProviderResult(
                    provider="steam_bans",
                    status="UNAVAILABLE",
                    summary="Steam bans request timed out or failed.",
                )
                for sid in steam_ids
            }
