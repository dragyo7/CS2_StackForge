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
            summary = f"CSWatch reputation {rep}/100 (risk: {risk}); bans: VAC={vac}, GameBans={gb}."
            return ProviderResult(
                provider="cswatch",
                status="FLAGGED" if (vac or gb > 0 or str(risk).lower() in ("high", "critical")) else "OK",
                summary=summary,
                data={
                    "persona_name": data.get("personaName"),
                    "avatar_url": data.get("avatarUrl"),
                    "reputation_score": rep,
                    "risk_level": risk,
                    "is_cheater": data.get("isCheater"),
                    "conviction_count": data.get("convictionCount"),
                    "bans": bans,
                    "breakdown": data.get("breakdown") or [],
                    "factors": data.get("factors") or [],
                    "profile_url": data.get("cswatchProfileUrl") or f"https://cswatch.gg/player/{steam_id64}",
                },
            )
        except Exception:
            return ProviderResult(
                provider="cswatch",
                status="UNAVAILABLE",
                summary="CSWatch request timed out or failed.",
            )
