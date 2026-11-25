from __future__ import annotations

import httpx

from app.config import get_settings
from app.providers.base import ProviderResult


def _safe_float(val) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(str(val).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> int | None:
    f = _safe_float(val)
    return int(round(f)) if f is not None else None


class FaceitProvider:
    """Authorized FACEIT Data API v4 adapter (non-blocking, server-side key only)."""

    BASE_URL = "https://open.faceit.com/data/v4"

    def __init__(self, api_key: str | None = None, timeout: float | None = None):
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.faceit_api_key
        self.timeout = timeout if timeout is not None else settings.provider_timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def fetch_by_steam_id64(self, steam_id64: str | None) -> ProviderResult:
        if not steam_id64:
            return ProviderResult(
                provider="faceit",
                status="NOT_LINKED",
                summary="No SteamID64 linked for FACEIT lookup.",
            )
        if not self.api_key:
            return ProviderResult(
                provider="faceit",
                status="NOT_CONFIGURED",
                summary="FACEIT API key not configured.",
            )
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/players",
                    params={"game": "cs2", "game_player_id": steam_id64},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if resp.status_code == 404:
                    return ProviderResult(
                        provider="faceit",
                        status="NOT_LINKED",
                        summary="No public FACEIT CS2 profile found for this SteamID64.",
                    )
                if resp.status_code != 200:
                    return ProviderResult(
                        provider="faceit",
                        status="UNAVAILABLE",
                        summary=f"FACEIT API unavailable (HTTP {resp.status_code}).",
                    )
                payload = resp.json()
                player_id = payload.get("player_id")
                cs2 = (payload.get("games") or {}).get("cs2") or {}
                elo = cs2.get("faceit_elo")
                level = cs2.get("skill_level")

                combat_stats: dict = {}
                if player_id:
                    stats_resp = await client.get(
                        f"{self.BASE_URL}/players/{player_id}/stats/cs2",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
                    if stats_resp.status_code == 200:
                        lifetime = stats_resp.json().get("lifetime") or {}
                        combat_stats = {
                            "matches_played": _safe_int(lifetime.get("Matches")),
                            "win_rate": _safe_float(lifetime.get("Win Rate %")),
                            "kd_ratio": _safe_float(lifetime.get("Average K/D Ratio")),
                            "hs_pct": _safe_float(lifetime.get("Average Headshots %")),
                            "adr": _safe_float(lifetime.get("ADR")),
                        }

            return ProviderResult(
                provider="faceit",
                status="OK",
                summary=f"FACEIT Lv {level or '?'} ({elo or '?'} ELO)" if elo else "FACEIT profile linked.",
                data={
                    "faceit_player_id": player_id,
                    "nickname": payload.get("nickname"),
                    "faceit_elo": elo,
                    "skill_level": level,
                    "combat_stats": combat_stats,
                },
            )
        except Exception:
            return ProviderResult(
                provider="faceit",
                status="UNAVAILABLE",
                summary="FACEIT request timed out or failed.",
            )


class LeetifyProvider:
    """Leetify Public CS API adapter (non-blocking, server-side key only)."""

    BASE_URL = "https://api-public.cs-prod.leetify.com"

    def __init__(self, api_key: str | None = None, timeout: float | None = None):
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.leetify_api_key
        self.timeout = timeout if timeout is not None else settings.provider_timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def fetch_by_steam_id64(self, steam_id64: str | None) -> ProviderResult:
        if not steam_id64:
            return ProviderResult(
                provider="leetify",
                status="NOT_LINKED",
                summary="No SteamID64 linked for Leetify lookup.",
            )
        if not self.api_key:
            return ProviderResult(
                provider="leetify",
                status="NOT_CONFIGURED",
                summary="Leetify API key not configured.",
            )
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/v3/profile",
                    params={"steam64_id": steam_id64},
                    headers={"_leetify_key": self.api_key},
                )
            if resp.status_code == 404:
                return ProviderResult(
                    provider="leetify",
                    status="NOT_LINKED",
                    summary="No public Leetify profile found for this SteamID64.",
                )
            if resp.status_code != 200:
                return ProviderResult(
                    provider="leetify",
                    status="UNAVAILABLE",
                    summary=f"Leetify API unavailable (HTTP {resp.status_code}).",
                )
            payload = resp.json()
            ranks = payload.get("ranks") or {}
            rating = payload.get("rating") or {}
            stats = payload.get("stats") or {}
            leetify_val = ranks.get("leetify") if isinstance(ranks, dict) else None
            premier = ranks.get("premier") if isinstance(ranks, dict) else None

            combat_stats = {}
            if isinstance(stats, dict) and stats:
                combat_stats = {
                    "matches_played": _safe_int(payload.get("total_matches")),
                    "win_rate": _safe_float(payload.get("winrate")),
                    "kd_ratio": _safe_float(stats.get("kd_ratio")),
                    "adr": _safe_float(stats.get("dpr") or stats.get("adr")),
                    "kast": _safe_float(stats.get("kast")),
                    "hs_pct": _safe_float(stats.get("hs_pct")),
                    "opening_duel_pct": _safe_float(stats.get("opening_duel_success_pct")),
                    "utility_damage_per_round": _safe_float(stats.get("he_foes_damage_avg")),
                    "flash_assists_per_round": _safe_float(stats.get("flash_assist")),
                    "clutch_win_pct": _safe_float(stats.get("clutch_win_pct")),
                }

            return ProviderResult(
                provider="leetify",
                status="OK",
                summary="Leetify profile fetched.",
                data={
                    "leetify_rating": leetify_val,
                    "premier_rating": premier,
                    "raw_rating": rating,
                    "combat_stats": combat_stats,
                },
            )
        except Exception:
            return ProviderResult(
                provider="leetify",
                status="UNAVAILABLE",
                summary="Leetify request timed out or failed.",
            )
