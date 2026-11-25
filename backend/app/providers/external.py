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

    async def fetch_by_nickname(self, nickname: str) -> ProviderResult:
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
                    params={"nickname": nickname},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
            if resp.status_code == 404:
                return ProviderResult(provider="faceit", status="NOT_FOUND", summary=f"FACEIT player '{nickname}' not found.")
            if resp.status_code != 200:
                return ProviderResult(provider="faceit", status="UNAVAILABLE", summary=f"FACEIT API unavailable (HTTP {resp.status_code}).")
            payload = resp.json()
            cs2 = (payload.get("games") or {}).get("cs2") or {}
            return ProviderResult(
                provider="faceit",
                status="OK",
                summary=f"FACEIT {payload.get('nickname')} (Lv {cs2.get('skill_level') or '?'} • {cs2.get('faceit_elo') or '?'} ELO)",
                data={
                    "faceit_player_id": payload.get("player_id"),
                    "nickname": payload.get("nickname"),
                    "steam_id64": payload.get("steam_id_64"),
                    "faceit_elo": cs2.get("faceit_elo"),
                    "skill_level": cs2.get("skill_level"),
                    "profile_url": payload.get("faceit_url", "").replace("{lang}", "en") if payload.get("faceit_url") else None,
                },
            )
        except Exception:
            return ProviderResult(provider="faceit", status="UNAVAILABLE", summary="FACEIT request timed out or failed.")

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
                    "profile_url": payload.get("faceit_url", "").replace("{lang}", "en") if payload.get("faceit_url") else None,
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
    """
    Leetify Public CS API v3 adapter.
    Supports keyless public lookups (with optional _leetify_key when LEETIFY_API_KEY is set).
    """

    BASE_URL = "https://api-public.cs-prod.leetify.com"

    def __init__(self, api_key: str | None = None, timeout: float | None = None):
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.leetify_api_key
        self.timeout = timeout if timeout is not None else max(settings.provider_timeout_seconds, 6.0)

    @property
    def is_configured(self) -> bool:
        return True  # Public API works keyless!

    def _headers(self) -> dict[str, str]:
        return {"_leetify_key": self.api_key} if self.api_key else {}

    async def fetch_by_steam_id64(self, steam_id64: str | None, include_matches: bool = True) -> ProviderResult:
        if not steam_id64:
            return ProviderResult(
                provider="leetify",
                status="NOT_LINKED",
                summary="No SteamID64 linked for Leetify lookup.",
            )
        try:
            import asyncio as _asyncio

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = None
                for attempt in range(3):
                    resp = await client.get(
                        f"{self.BASE_URL}/v3/profile",
                        params={"steam64_id": steam_id64},
                        headers=self._headers(),
                    )
                    if resp.status_code != 429:
                        break
                    await _asyncio.sleep(1.5 * (attempt + 1))

                assert resp is not None
                if resp.status_code == 404:
                    return ProviderResult(
                        provider="leetify",
                        status="NOT_LINKED",
                        summary="No public Leetify profile found for this SteamID64.",
                    )
                if resp.status_code == 429:
                    return ProviderResult(
                        provider="leetify",
                        status="RATE_LIMITED",
                        summary="Leetify public API rate limit reached (HTTP 429).",
                    )
                if resp.status_code != 200:
                    return ProviderResult(
                        provider="leetify",
                        status="UNAVAILABLE",
                        summary=f"Leetify API unavailable (HTTP {resp.status_code}).",
                    )
                payload = resp.json()
                privacy = payload.get("privacy_mode")
                if privacy == "private":
                    return ProviderResult(
                        provider="leetify",
                        status="PRIVATE",
                        summary="Leetify profile is set to private.",
                        data={"leetify_id": payload.get("id")},
                    )

                matches_raw: list[dict] = []
                if include_matches:
                    await _asyncio.sleep(0.35)
                    mresp = None
                    for attempt in range(3):
                        mresp = await client.get(
                            f"{self.BASE_URL}/v3/profile/matches",
                            params={"steam64_id": steam_id64},
                            headers=self._headers(),
                        )
                        if mresp.status_code != 429:
                            break
                        await _asyncio.sleep(1.2 * (attempt + 1))
                    if mresp is not None and mresp.status_code == 200 and isinstance(mresp.json(), list):
                        matches_raw = mresp.json()

            ranks = payload.get("ranks") or {}
            rating = payload.get("rating") or {}
            stats = payload.get("stats") or {}

            leetify_val = _safe_float(ranks.get("leetify")) if isinstance(ranks, dict) else None
            premier = _safe_int(ranks.get("premier")) if isinstance(ranks, dict) else None
            faceit_elo = _safe_int(ranks.get("faceit_elo")) if isinstance(ranks, dict) else None
            faceit_lvl = _safe_int(ranks.get("faceit")) if isinstance(ranks, dict) else None

            winrate_raw = _safe_float(payload.get("winrate"))
            win_pct = round(winrate_raw * 100.0, 1) if (winrate_raw is not None and winrate_raw <= 1.0) else winrate_raw

            # Opening duel avg across CT & T
            ct_open = _safe_float(stats.get("ct_opening_duel_success_percentage"))
            t_open = _safe_float(stats.get("t_opening_duel_success_percentage"))
            open_vals = [v for v in (ct_open, t_open) if v is not None]
            opening_pct = round(sum(open_vals) / len(open_vals), 1) if open_vals else None

            clutch_raw = _safe_float(rating.get("clutch"))
            clutch_pct = round(clutch_raw * 100.0, 1) if (clutch_raw is not None and clutch_raw <= 1.0) else clutch_raw

            # Aggregate real recent match stats (last 10 and up to 30 matches)
            parsed_matches: list[dict] = []
            map_perf: dict[str, list[float]] = {}
            for m in matches_raw[:30]:
                me = next((s for s in (m.get("stats") or []) if str(s.get("steam64_id")) == steam_id64), None)
                if not me:
                    continue
                kills = _safe_int(me.get("total_kills")) or 0
                hs_kills = _safe_int(me.get("total_hs_kills")) or 0
                hs_match_pct = round((hs_kills / kills) * 100.0, 1) if kills > 0 else None
                rounds = _safe_int(me.get("rounds_count")) or 0
                rounds_won = _safe_int(me.get("rounds_won")) or 0
                rounds_lost = _safe_int(me.get("rounds_lost")) or 0
                outcome = "win" if rounds_won > rounds_lost else ("loss" if rounds_lost > rounds_won else "tie")
                m_lrating = _safe_float(me.get("leetify_rating"))
                map_name = m.get("map_name")
                if map_name and m_lrating is not None:
                    map_perf.setdefault(map_name, []).append(m_lrating)

                parsed_matches.append(
                    {
                        "external_match_id": str(m.get("id")),
                        "map_name": map_name,
                        "game_mode": m.get("data_source") or "CS2",
                        "outcome": outcome,
                        "score_text": f"{rounds_won}-{rounds_lost}" if rounds else None,
                        "kd_ratio": _safe_float(me.get("kd_ratio")),
                        "adr": _safe_float(me.get("dpr")),
                        "hs_pct": hs_match_pct,
                        "flash_assist": _safe_float(me.get("flash_assist")) or 0.0,
                        "he_dmg": _safe_float(me.get("he_foes_damage_avg")),
                        "multi2k": _safe_int(me.get("multi2k")) or 0,
                        "multi3k": _safe_int(me.get("multi3k")) or 0,
                        "multi4k": _safe_int(me.get("multi4k")) or 0,
                        "multi5k": _safe_int(me.get("multi5k")) or 0,
                        "rounds": rounds,
                        "leetify_rating": m_lrating,
                        "played_at": m.get("finished_at"),
                    }
                )

            def _agg(subset: list[dict]) -> dict:
                if not subset:
                    return {}
                n = len(subset)
                wins = sum(1 for x in subset if x["outcome"] == "win")
                kds = [x["kd_ratio"] for x in subset if x["kd_ratio"] is not None]
                adrs = [x["adr"] for x in subset if x["adr"] is not None]
                hss = [x["hs_pct"] for x in subset if x["hs_pct"] is not None]
                hes = [x["he_dmg"] for x in subset if x["he_dmg"] is not None]
                total_rounds = sum(x["rounds"] for x in subset)
                total_flashes = sum(x["flash_assist"] for x in subset)
                total_multis = sum(x["multi2k"] + x["multi3k"] + x["multi4k"] + x["multi5k"] for x in subset)
                return {
                    "matches_played": n,
                    "win_rate": round((wins / n) * 100.0, 1),
                    "kd_ratio": round(sum(kds) / len(kds), 2) if kds else None,
                    "adr": round(sum(adrs) / len(adrs), 1) if adrs else None,
                    "hs_pct": round(sum(hss) / len(hss), 1) if hss else None,
                    "utility_damage_per_round": round(sum(hes) / len(hes), 1) if hes else None,
                    "flash_assists_per_round": round(total_flashes / total_rounds, 3) if total_rounds > 0 else None,
                    "multi_kill_rate": round(total_multis / n, 2),
                }

            recent10 = _agg(parsed_matches[:10])
            recent30 = _agg(parsed_matches[:30])

            # Recent form delta vs overall leetify rating
            recent_form: float | None = None
            last10_lratings = [x["leetify_rating"] for x in parsed_matches[:10] if x["leetify_rating"] is not None]
            if last10_lratings and leetify_val is not None:
                avg10 = sum(last10_lratings) / len(last10_lratings)
                baseline = leetify_val / 100.0 if abs(leetify_val) > 0.5 else leetify_val
                recent_form = round(max(-1.0, min(1.0, (avg10 - baseline) * 12.0)), 3)

            # Hidden map-pool deltas (internal only)
            map_deltas: dict[str, float] = {}
            for mname, vals in map_perf.items():
                short = mname.replace("de_", "").lower()
                avg_m = sum(vals) / len(vals)
                map_deltas[short] = round(max(-10.0, min(10.0, avg_m * 80.0)), 2)

            lifetime_stats = {
                "matches_played": _safe_int(payload.get("total_matches")),
                "win_rate": win_pct,
                "kd_ratio": recent30.get("kd_ratio"),
                "adr": recent30.get("adr"),
                "hs_pct": recent30.get("hs_pct") or _safe_float(stats.get("accuracy_head")),
                "opening_duel_pct": opening_pct,
                "trade_kills_per_match": _safe_float(stats.get("trade_kills_success_percentage")),
                "utility_damage_per_round": _safe_float(stats.get("he_foes_damage_avg")),
                "flash_assists_per_round": recent30.get("flash_assists_per_round"),
                "clutch_win_pct": clutch_pct,
                "consistency_score": _safe_float(stats.get("counter_strafing_good_shots_ratio")),
            }

            return ProviderResult(
                provider="leetify",
                status="OK",
                summary=f"Leetify synced ({payload.get('total_matches') or 0} matches; Premier {premier or 'N/A'}).",
                data={
                    "leetify_id": payload.get("id"),
                    "persona_name": payload.get("name"),
                    "leetify_rating": leetify_val,
                    "premier_rating": premier,
                    "faceit_elo": faceit_elo,
                    "faceit_level": faceit_lvl,
                    "bans": payload.get("bans") or [],
                    "recent_form": recent_form,
                    "map_deltas": map_deltas,
                    "combat_stats_lifetime": lifetime_stats,
                    "combat_stats_recent10": recent10,
                    "recent_matches": parsed_matches[:15],
                    "profile_url": f"https://leetify.com/app/profile/{steam_id64}",
                },
            )
        except Exception:
            return ProviderResult(
                provider="leetify",
                status="UNAVAILABLE",
                summary="Leetify request timed out or failed.",
            )
