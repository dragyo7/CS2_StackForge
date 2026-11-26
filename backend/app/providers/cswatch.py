from __future__ import annotations

import time
from collections import deque

import httpx

from app.providers.base import ProviderResult


class CSWatchProvider:
    """
    CSWatch public JSON API adapter (https://cswatch.gg/api/public/player/{steamId}).
    Respects fair-use rate limit (<= 30 req/min/IP) and enforces explicit attribution.
    Third-party reputation is NEVER an official Valve enforcement verdict.
    """

    BASE_URL = "https://cswatch.gg/api/public/player"
    _request_timestamps: deque[float] = deque()

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    def _within_rate_limit(self) -> bool:
        now = time.monotonic()
        while self._request_timestamps and (now - self._request_timestamps[0]) > 60.0:
            self._request_timestamps.popleft()
        if len(self._request_timestamps) >= 25:
            return False
        self._request_timestamps.append(now)
        return True

    async def fetch_player(self, steam_id64: str | None) -> ProviderResult:
        if not steam_id64:
            return ProviderResult(
                provider="cswatch",
                status="NOT_LINKED",
                summary="No SteamID64 linked for CSWatch lookup.",
            )
        if not self._within_rate_limit():
            return ProviderResult(
                provider="cswatch",
                status="RATE_LIMITED",
                summary="CSWatch fair-use rate limit reached (25/min cap); try again shortly.",
            )
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.BASE_URL}/{steam_id64}")
            if resp.status_code == 404:
                return ProviderResult(
                    provider="cswatch",
                    status="NOT_FOUND",
                    summary="No public CSWatch record found for this SteamID64.",
                )
            if resp.status_code == 429:
                return ProviderResult(
                    provider="cswatch",
                    status="RATE_LIMITED",
                    summary="CSWatch rate limit reached (HTTP 429).",
                )
            if resp.status_code != 200:
                return ProviderResult(
                    provider="cswatch",
                    status="UNAVAILABLE",
                    summary=f"CSWatch API unavailable (HTTP {resp.status_code}).",
                )
            data = resp.json()
            rep = data.get("reputationScore")
            risk = data.get("riskLevel") or "unknown"
            bans = data.get("bans") or {}
            vac = bool(bans.get("vac"))
            gb = int(bans.get("gameBans") or 0)
            stored = data.get("stored")
            stored_at = data.get("storedAt")
            stale = bool(data.get("stale", False))
            generated_at = data.get("generatedAt")
            is_cheater = bool(data.get("isCheater", False))
            conviction_count = int(data.get("convictionCount") or 0)

            is_flagged = (
                vac
                or gb > 0
                or conviction_count > 0
                or is_cheater
                or str(risk).lower() in ("high", "critical")
            )
            is_unknown = (stored is False) or (rep is None and str(risk).lower() == "unknown")

            if is_flagged:
                res_status = "FLAGGED"
                freshness = "STALE" if stale else "FRESH"
                summary = (
                    f"CSWatch reputation {rep if rep is not None else '?'}/100 (risk: {risk}; "
                    f"convictions={conviction_count}, isCheater={is_cheater}, VAC={vac}, GameBans={gb})."
                )
            elif is_unknown:
                res_status = "UNKNOWN"
                freshness = "UNKNOWN"
                summary = (
                    f"CSWatch profile unindexed or unknown for SteamID64 {steam_id64} "
                    f"(stored={stored}); missing data is not a clean verdict."
                )
            elif stale:
                res_status = "STALE"
                freshness = "STALE"
                summary = (
                    f"CSWatch reputation {rep if rep is not None else '?'}/100 (risk: {risk}; "
                    f"STALE cache storedAt={stored_at or 'unknown'} >24h — not a current clean verdict)."
                )
            else:
                res_status = "OK"
                freshness = "FRESH"
                summary = f"CSWatch reputation {rep}/100 (risk: {risk}); bans: VAC={vac}, GameBans={gb}."

            return ProviderResult(
                provider="cswatch",
                status=res_status,
                endpoint_category="reputation",
                player_identity=steam_id64,
                freshness=freshness,
                summary=summary,
                data={
                    "persona_name": data.get("personaName"),
                    "avatar_url": data.get("avatarUrl"),
                    "reputation_score": rep,
                    "risk_level": risk,
                    "stored": stored,
                    "stored_at": stored_at,
                    "stale": stale,
                    "generated_at": generated_at,
                    "is_cheater": data.get("isCheater"),
                    "conviction_count": conviction_count,
                    "ai_severity": data.get("aiSeverity"),
                    "bans": bans,
                    "breakdown": data.get("breakdown") or [],
                    "factors": data.get("factors") or [],
                    "profile_url": data.get("cswatchProfileUrl") or f"https://cswatch.gg/player/{steam_id64}",
                    "steam_profile_url": data.get("steamProfileUrl"),
                },
            )
        except Exception:
            return ProviderResult(
                provider="cswatch",
                status="UNAVAILABLE",
                summary="CSWatch request timed out or failed.",
            )
