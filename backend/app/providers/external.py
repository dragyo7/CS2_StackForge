from __future__ import annotations

import httpx

from app.config import get_settings
from app.providers.base import ProviderResult
from app.services.secrets_service import get_secret


def _clamp_range(val: float | None, low: float, high: float) -> float | None:
    if val is None:
        return None
    return val if low <= val <= high else None


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


def _retry_delay_seconds(resp: httpx.Response, attempt: int, base: float = 1.2) -> float | None:
    """Returns bounded retry delay (<= 5s) when safe; returns None to stop retrying long 429 windows."""
    ra = resp.headers.get("Retry-After")
    if ra:
        try:
            secs = float(ra)
            if secs <= 5.0:
                return max(0.3, secs)
            return None
        except ValueError:
            return None
    return min(4.0, base * (2 ** attempt))


def _pct_100(val: float | None) -> float | None:
    if val is None:
        return None
    pct = round(val * 100.0, 2) if 0.0 <= val <= 1.0 else round(val, 2)
    return _clamp_range(pct, 0.0, 100.0)


class FaceitProvider:
    """Authorized FACEIT Data API v4 adapter (non-blocking, server-side key only)."""

    BASE_URL = "https://open.faceit.com/data/v4"

    def __init__(self, api_key: str | None = None, timeout: float | None = None):
        settings = get_settings()
        self.api_key = api_key if api_key is not None else (get_secret("faceit") or settings.faceit_api_key)
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
    Supports keyless public lookups (with optional _leetify_key when configured in env/DPAPI vault).
    """

    BASE_URL = "https://api-public.cs-prod.leetify.com"

    def __init__(self, api_key: str | None = None, timeout: float | None = None):
        settings = get_settings()
        self.api_key = api_key if api_key is not None else (get_secret("leetify") or settings.leetify_api_key)
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
                endpoint_category="profile_and_matches",
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
                    wait_s = _retry_delay_seconds(resp, attempt, base=1.2)
                    if wait_s is None:
                        break
                    await _asyncio.sleep(wait_s)

                assert resp is not None
                if resp.status_code == 404:
                    return ProviderResult(
                        provider="leetify",
                        status="NOT_LINKED",
                        endpoint_category="profile_and_matches",
                        player_identity=steam_id64,
                        summary="No public Leetify profile found for this SteamID64.",
                    )
                if resp.status_code == 429:
                    return ProviderResult(
                        provider="leetify",
                        status="RATE_LIMITED",
                        endpoint_category="profile_and_matches",
                        player_identity=steam_id64,
                        failure_reason="HTTP 429 rate limited by Leetify API",
                        retry_eligible=True,
                        summary="Leetify public API rate limit reached (HTTP 429).",
                    )
                if resp.status_code != 200:
                    return ProviderResult(
                        provider="leetify",
                        status="UNAVAILABLE",
                        endpoint_category="profile_and_matches",
                        player_identity=steam_id64,
                        failure_reason=f"HTTP {resp.status_code} from Leetify profile endpoint",
                        retry_eligible=True,
                        summary=f"Leetify API unavailable (HTTP {resp.status_code}).",
                    )
                payload = resp.json()
                privacy = payload.get("privacy_mode")
                if privacy == "private":
                    return ProviderResult(
                        provider="leetify",
                        status="PRIVATE",
                        endpoint_category="profile_and_matches",
                        player_identity=steam_id64,
                        failure_reason="Player profile is private on Leetify",
                        summary="Leetify profile is set to private.",
                        data={"leetify_id": payload.get("id")},
                    )

                matches_raw: list[dict] = []
                matches_status = "SKIPPED"
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
                        wait_m = _retry_delay_seconds(mresp, attempt, base=1.0)
                        if wait_m is None:
                            break
                        await _asyncio.sleep(wait_m)
                    if mresp is not None and mresp.status_code == 200 and isinstance(mresp.json(), list):
                        matches_raw = mresp.json()
                        matches_status = "OK"
                    elif mresp is not None and mresp.status_code == 429:
                        matches_status = "RATE_LIMITED"
                    elif mresp is not None:
                        matches_status = "UNAVAILABLE"

            ranks = payload.get("ranks") or {}
            rating = payload.get("rating") or {}
            stats = payload.get("stats") or {}

            leetify_val = _safe_float(ranks.get("leetify")) if isinstance(ranks, dict) else None
            premier = _safe_int(ranks.get("premier")) if isinstance(ranks, dict) else None
            faceit_elo = _safe_int(ranks.get("faceit_elo")) if isinstance(ranks, dict) else None
            faceit_lvl = _safe_int(ranks.get("faceit")) if isinstance(ranks, dict) else None

            aim_rating = _clamp_range(round(_safe_float(rating.get("aim")), 2), 0.0, 100.0) if _safe_float(rating.get("aim")) is not None else None
            utility_rating = _clamp_range(round(_safe_float(rating.get("utility")), 2), 0.0, 100.0) if _safe_float(rating.get("utility")) is not None else None
            positioning_rating = (
                _clamp_range(round(_safe_float(rating.get("positioning")), 2), 0.0, 100.0)
                if _safe_float(rating.get("positioning")) is not None
                else None
            )

            winrate_raw = _safe_float(payload.get("winrate"))
            win_pct = round(winrate_raw * 100.0, 1) if (winrate_raw is not None and 0.0 <= winrate_raw <= 1.0) else winrate_raw
            win_pct = _clamp_range(win_pct, 0.0, 100.0) if win_pct is not None else None

            # Opening duel avg across CT & T
            ct_open = _pct_100(_safe_float(stats.get("ct_opening_duel_success_percentage")))
            t_open = _pct_100(_safe_float(stats.get("t_opening_duel_success_percentage")))
            open_vals = [v for v in (ct_open, t_open) if v is not None]
            opening_pct = round(sum(open_vals) / len(open_vals), 1) if open_vals else None

            clutch_raw = _safe_float(rating.get("clutch"))
            clutch_pct = round(clutch_raw * 100.0, 1) if (clutch_raw is not None and 0.0 <= clutch_raw <= 1.0) else clutch_raw
            clutch_pct = _clamp_range(clutch_pct, 0.0, 100.0) if clutch_pct is not None else None

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

                rt_raw = _safe_float(me.get("reaction_time"))
                rt_ms = round(rt_raw * 1000.0, 1) if (rt_raw is not None and rt_raw < 10.0) else rt_raw
                trade_opps = _safe_int(me.get("trade_kill_opportunities")) or 0
                trade_pct = _pct_100(_safe_float(me.get("trade_kills_success_percentage"))) if trade_opps > 0 else None
                td_opps = _safe_int(me.get("traded_death_opportunities")) or 0
                td_pct = _pct_100(_safe_float(me.get("traded_deaths_success_percentage"))) if td_opps > 0 else None

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
                        "preaim": _safe_float(me.get("preaim")),
                        "reaction_time_ms": rt_ms,
                        "spotted_accuracy": _pct_100(_safe_float(me.get("accuracy_enemy_spotted"))),
                        "spray_accuracy": _pct_100(_safe_float(me.get("spray_accuracy"))),
                        "consistency_score": _pct_100(_safe_float(me.get("counter_strafing_shots_good_ratio"))),
                        "trade_pct": trade_pct,
                        "traded_deaths_pct": td_pct,
                        "enemies_flashed": _safe_float(me.get("flashbang_hit_foe")) or 0.0,
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
                preaims = [x["preaim"] for x in subset if x["preaim"] is not None]
                rts = [x["reaction_time_ms"] for x in subset if x["reaction_time_ms"] is not None]
                spots = [x["spotted_accuracy"] for x in subset if x["spotted_accuracy"] is not None]
                sprays = [x["spray_accuracy"] for x in subset if x["spray_accuracy"] is not None]
                cons = [x["consistency_score"] for x in subset if x["consistency_score"] is not None]
                trades = [x["trade_pct"] for x in subset if x["trade_pct"] is not None]
                tds = [x["traded_deaths_pct"] for x in subset if x["traded_deaths_pct"] is not None]
                total_rounds = sum(x["rounds"] for x in subset)
                total_flashes = sum(x["flash_assist"] for x in subset)
                total_enemies_flashed = sum(x["enemies_flashed"] for x in subset)
                total_multis = sum(x["multi2k"] + x["multi3k"] + x["multi4k"] + x["multi5k"] for x in subset)
                return {
                    "matches_played": n,
                    "win_rate": round((wins / n) * 100.0, 1),
                    "kd_ratio": round(sum(kds) / len(kds), 2) if kds else None,
                    "adr": round(sum(adrs) / len(adrs), 1) if adrs else None,
                    "hs_pct": round(sum(hss) / len(hss), 1) if hss else None,
                    "utility_damage_per_round": round(sum(hes) / len(hes), 1) if hes else None,
                    "flash_assists_per_round": round(total_flashes / total_rounds, 3) if total_rounds > 0 else None,
                    "enemies_flashed_per_round": round(total_enemies_flashed / total_rounds, 3) if total_rounds > 0 else None,
                    "multi_kill_rate": round(total_multis / n, 2),
                    "preaim": round(sum(preaims) / len(preaims), 2) if preaims else None,
                    "reaction_time_ms": round(sum(rts) / len(rts), 1) if rts else None,
                    "spotted_accuracy": round(sum(spots) / len(spots), 1) if spots else None,
                    "spray_accuracy": round(sum(sprays) / len(sprays), 1) if sprays else None,
                    "consistency_score": round(sum(cons) / len(cons), 1) if cons else None,
                    "trade_kills_per_match": round(sum(trades) / len(trades), 1) if trades else None,
                    "traded_deaths_pct": round(sum(tds) / len(tds), 1) if tds else None,
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
                "kd_ratio": _clamp_range(recent30.get("kd_ratio"), 0.0, 10.0),
                "adr": _clamp_range(recent30.get("adr"), 0.0, 300.0),
                "hs_pct": _clamp_range(recent30.get("hs_pct") or _pct_100(_safe_float(stats.get("accuracy_head"))), 0.0, 100.0),
                "opening_duel_pct": opening_pct,
                "trade_kills_per_match": _pct_100(_safe_float(stats.get("trade_kills_success_percentage"))),
                "traded_deaths_pct": _pct_100(_safe_float(stats.get("traded_deaths_success_percentage"))),
                "utility_damage_per_round": _clamp_range(_safe_float(stats.get("he_foes_damage_avg")), 0.0, 150.0),
                "flash_assists_per_round": _clamp_range(recent30.get("flash_assists_per_round"), 0.0, 10.0),
                "enemies_flashed_per_round": _clamp_range(recent30.get("enemies_flashed_per_round"), 0.0, 20.0),
                "clutch_win_pct": clutch_pct,
                "consistency_score": _pct_100(_safe_float(stats.get("counter_strafing_good_shots_ratio"))),
                "aim_rating": aim_rating,
                "utility_rating": utility_rating,
                "positioning_rating": positioning_rating,
                "preaim": _clamp_range(_safe_float(stats.get("preaim")), 0.0, 180.0),
                "reaction_time_ms": _clamp_range(_safe_float(stats.get("reaction_time_ms")), 50.0, 2500.0),
                "spotted_accuracy": _pct_100(_safe_float(stats.get("accuracy_enemy_spotted"))),
                "spray_accuracy": _pct_100(_safe_float(stats.get("spray_accuracy"))),
            }

            res_status = "PARTIAL" if matches_status in ("RATE_LIMITED", "UNAVAILABLE") else "OK"
            summary_note = f" (recent matches: {matches_status})" if res_status == "PARTIAL" else ""
            return ProviderResult(
                provider="leetify",
                status=res_status,
                endpoint_category="profile_and_matches",
                player_identity=steam_id64,
                failure_reason=f"Recent matches endpoint: {matches_status}" if res_status == "PARTIAL" else None,
                retry_eligible=(res_status == "PARTIAL"),
                summary=f"Leetify synced ({payload.get('total_matches') or 0} matches; Premier {premier or 'N/A'}){summary_note}.",
                data={
                    "leetify_id": payload.get("id"),
                    "persona_name": payload.get("name"),
                    "leetify_rating": leetify_val,
                    "premier_rating": premier,
                    "faceit_elo": faceit_elo,
                    "faceit_level": faceit_lvl,
                    "aim_rating": aim_rating,
                    "utility_rating": utility_rating,
                    "positioning_rating": positioning_rating,
                    "bans": payload.get("bans") or [],
                    "recent_form": recent_form,
                    "map_deltas": map_deltas,
                    "combat_stats_lifetime": lifetime_stats,
                    "combat_stats_recent10": recent10,
                    "recent_matches": parsed_matches[:15],
                    "matches_status": matches_status,
                    "profile_url": f"https://leetify.com/app/profile/{steam_id64}",
                },
            )
        except Exception:
            return ProviderResult(
                provider="leetify",
                status="UNAVAILABLE",
                summary="Leetify request timed out or failed.",
            )
