from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.migrations import run_migrations
from app.models import CommunityPlayer, PlayerStatSnapshot, TrustSignal, WatchlistEntry
from app.optimizer.engine import optimize_teams
from app.optimizer.normalizer import PlayerInput, normalize_player
from app.providers.base import ProviderResult
from app.services import player_service


@pytest.fixture()
def v2_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    run_migrations(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with SessionLocal() as db:
        player_service.get_or_create_default_community(db)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield SessionLocal, client
    app.dependency_overrides.clear()


def test_normalization_missing_dimensions_conflicting_providers_and_no_manual_rating():
    # 1. Missing Aim, Utility, Pre-aim, Premier, FACEIT, Leetify -> INSUFFICIENT_DATA, never manual_rating
    no_ext = normalize_player(
        PlayerInput(
            community_player_id="x0",
            display_name="NoStats",
            steam_id64=None,
            identity_status="MANUAL_ONLY",
            manual_rating=98.0,
        )
    )
    assert no_ext.normalized_strength is None
    assert no_ext.data_status == "INSUFFICIENT_DATA"
    assert no_ext.aim_score is None
    assert no_ext.utility_score is None
    assert no_ext.confidence == 0.0

    # 2. High Premier (18000) vs modest Leetify (-0.02), missing Aim/Utility/Pre-aim -> still works, no crash, manual ignored
    conflicting = normalize_player(
        PlayerInput(
            community_player_id="x1",
            display_name="Mixed",
            steam_id64="76561198000020001",
            identity_status="STEAM_RESOLVED",
            manual_rating=15.0,
            premier_rating=18000,
            leetify_rating=-0.02,
            stats_sample_size=12,
            adr=78.0,
        )
    )
    conflicting_high_manual = normalize_player(
        PlayerInput(
            community_player_id="x1",
            display_name="Mixed",
            steam_id64="76561198000020001",
            identity_status="STEAM_RESOLVED",
            manual_rating=99.0,
            premier_rating=18000,
            leetify_rating=-0.02,
            stats_sample_size=12,
            adr=78.0,
        )
    )
    assert conflicting.normalized_strength == conflicting_high_manual.normalized_strength
    assert conflicting.normalized_strength is not None
    assert conflicting.aim_score is None
    assert conflicting.utility_score is None
    assert "faceit" in conflicting.missing_sources

    # 3. Genuine Aim Rating + Utility Rating + Pre-aim contribute without breaking stale penalty
    fresh = normalize_player(
        PlayerInput(
            community_player_id="x2",
            display_name="Mech",
            steam_id64="76561198000020002",
            identity_status="STEAM_RESOLVED",
            premier_rating=15000,
            leetify_rating=0.04,
            aim_rating=80.0,
            utility_rating=72.0,
            preaim=7.5,
            reaction_time_ms=520.0,
            stats_sample_size=25,
            stats_stale=False,
        )
    )
    stale = normalize_player(
        PlayerInput(
            community_player_id="x2",
            display_name="Mech",
            steam_id64="76561198000020002",
            identity_status="STEAM_RESOLVED",
            premier_rating=15000,
            leetify_rating=0.04,
            aim_rating=80.0,
            utility_rating=72.0,
            preaim=7.5,
            reaction_time_ms=520.0,
            stats_sample_size=25,
            stats_stale=True,
        )
    )
    assert fresh.aim_score is not None and fresh.utility_score is not None
    assert stale.confidence < fresh.confidence


def test_individual_refresh_isolation_single_flight_and_provider_failures(v2_client):
    SessionLocal, client = v2_client
    p1 = client.post("/api/players", json={"display_name": "One", "steam_id64": "76561198000030001"}).json()
    p2 = client.post("/api/players", json={"display_name": "Two", "steam_id64": "76561198000030002"}).json()

    calls_log: list[str] = []

    class _CountingSteam:
        is_configured = True

        async def resolve_vanity_url(self, vanity):
            return None, "NOT_FOUND"

        async def fetch_summaries(self, steam_ids):
            calls_log.extend([f"steam:{s}" for s in steam_ids])
            return {
                sid: ProviderResult(
                    provider="steam_profile",
                    status="OK",
                    summary="Public Steam",
                    data={"persona_name": f"Persona_{sid[-4:]}", "avatar_url": f"https://img/{sid}.png"},
                )
                for sid in steam_ids
            }

        async def fetch_bans(self, steam_ids):
            return {sid: ProviderResult(provider="steam_bans", status="NOT_CONFIGURED", summary="No key") for sid in steam_ids}

    class _RichLeetify:
        api_key = None

        async def fetch_by_steam_id64(self, sid, include_matches=True):
            calls_log.append(f"leetify:{sid}")
            await asyncio.sleep(0.05)  # allow concurrent single-flight overlap check
            return ProviderResult(
                provider="leetify",
                status="OK",
                summary="Leetify synced",
                data={
                    "leetify_id": f"lt-{sid}",
                    "premier_rating": 14500,
                    "leetify_rating": 3.1,
                    "aim_rating": 71.5,
                    "utility_rating": 63.0,
                    "positioning_rating": 58.0,
                    "recent_form": 0.2,
                    "combat_stats_recent10": {
                        "matches_played": 10,
                        "win_rate": 60.0,
                        "kd_ratio": 1.25,
                        "adr": 85.4,
                        "preaim": 8.2,
                        "reaction_time_ms": 540.0,
                    },
                    "combat_stats_lifetime": {
                        "matches_played": 100,
                        "win_rate": 53.0,
                        "opening_duel_pct": 54.5,
                        "trade_kills_per_match": 48.0,
                        "clutch_win_pct": 22.0,
                        "consistency_score": 78.0,
                        "aim_rating": 71.5,
                        "utility_rating": 63.0,
                    },
                    "recent_matches": [],
                },
            )

    class _NoFaceit:
        is_configured = False

        async def fetch_by_steam_id64(self, sid):
            calls_log.append(f"faceit:{sid}")
            return ProviderResult(provider="faceit", status="NOT_CONFIGURED", summary="FACEIT key unset")

    class _PrivateLeetify:
        async def fetch_by_steam_id64(self, sid, include_matches=True):
            calls_log.append(f"leetify_priv:{sid}")
            return ProviderResult(provider="leetify", status="PRIVATE", summary="Private Leetify profile")

    class _RateLimitedLeetify:
        async def fetch_by_steam_id64(self, sid, include_matches=True):
            calls_log.append(f"leetify_429:{sid}")
            return ProviderResult(provider="leetify", status="RATE_LIMITED", summary="HTTP 429")

    with SessionLocal() as db:
        comm = player_service.get_or_create_default_community(db)

        # 1. Duplicate concurrent refresh for p1 triggers single-flight deduplication (1 upstream call)
        async def _concurrent():
            return await asyncio.gather(
                player_service.refresh_player_profile(
                    db, comm.id, p1["id"], force=True, steam_provider=_CountingSteam(), leetify_provider=_RichLeetify(), faceit_provider=_NoFaceit()
                ),
                player_service.refresh_player_profile(
                    db, comm.id, p1["id"], force=True, steam_provider=_CountingSteam(), leetify_provider=_RichLeetify(), faceit_provider=_NoFaceit()
                ),
            )

        res_a, res_b = asyncio.run(_concurrent())
        assert calls_log.count(f"leetify:{p1['steam_id64']}") == 1
        assert res_a.status in ("SUCCESS", "PARTIAL")
        assert res_a.profile.player.premier_rating == 14500
        assert res_a.profile.player.aim_rating == 71.5
        assert res_a.profile.player.utility_rating == 63.0
        assert any(pr.provider == "faceit" and pr.status == "NOT_CONFIGURED" for pr in res_a.provider_results)
        # Ensure p2 was NOT touched at all!
        assert all(p2["steam_id64"] not in c for c in calls_log)

        # 2. Refresh p2 as PRIVATE -> p1's values remain untouched
        res_p2 = asyncio.run(
            player_service.refresh_player_profile(
                db, comm.id, p2["id"], force=True, steam_provider=_CountingSteam(), leetify_provider=_PrivateLeetify(), faceit_provider=_NoFaceit()
            )
        )
        assert any(pr.provider == "leetify" and pr.status == "PRIVATE" for pr in res_p2.provider_results)
        p1_check = player_service.get_player_profile(db, comm.id, p1["id"])
        assert p1_check.player.premier_rating == 14500
        assert p1_check.player.aim_rating == 71.5

        # 3. Rate-limited (429) on p1 preserves all previously fetched ratings and stats!
        res_429 = asyncio.run(
            player_service.refresh_player_profile(
                db, comm.id, p1["id"], force=True, steam_provider=_CountingSteam(), leetify_provider=_RateLimitedLeetify(), faceit_provider=_NoFaceit()
            )
        )
        assert res_429.status == "PARTIAL"
        assert any(pr.provider == "leetify" and pr.status == "RATE_LIMITED" for pr in res_429.provider_results)
        assert res_429.profile.player.premier_rating == 14500
        assert res_429.profile.player.aim_rating == 71.5
        assert len(res_429.profile.stat_snapshots) >= 2


def test_rankings_ordering_and_team_generation_ignores_manual_ratings(v2_client):
    SessionLocal, client = v2_client
    created = []
    # Mix of Premiers + 2 unrated players with wildly misleading legacy manual_ratings
    specs = [
        ("HighPrem", "76561198000040001", 22000, None, 10.0),
        ("MidPrem", "76561198000040002", 14000, 1.2, 15.0),
        ("LowPrem", "76561198000040003", 5000, -3.0, 95.0),
        ("NoDataA", None, None, None, 99.0),
        ("NoDataB", None, None, None, 1.0),
        ("R6", "76561198000040006", 12000, 0.5, 50.0),
        ("R7", "76561198000040007", 11000, 0.0, 50.0),
        ("R8", "76561198000040008", 16000, 2.0, 50.0),
        ("R9", "76561198000040009", 9000, -1.2, 50.0),
        ("R10", "76561198000040010", 13000, 0.8, 50.0),
    ]
    for name, sid, prem, lt, manual in specs:
        res = client.post(
            "/api/players",
            json={
                "display_name": name,
                "steam_id64": sid,
                "premier_rating": prem,
                "leetify_rating": lt,
                "manual_rating": manual,
            },
        )
        assert res.status_code == 201
        created.append(res.json())

    ranked = client.get("/api/players/rankings").json()
    assert ranked[0]["display_name"] == "HighPrem"
    # NoDataA & NoDataB have insufficient external data -> must be unranked at the bottom despite manual=99
    assert ranked[-2]["normalized_strength"] is None
    assert ranked[-1]["normalized_strength"] is None
    assert {ranked[-2]["display_name"], ranked[-1]["display_name"]} == {"NoDataA", "NoDataB"}

    # Generate teams -> unrated players split evenly (1 on A, 1 on B) & changing manual_rating changes nothing
    room = client.post("/api/rooms", json={"title": "V2 Match"}).json()
    client.put(f"/api/rooms/{room['id']}/roster", json={"community_player_ids": [p["id"] for p in created]})
    gen = client.post(f"/api/rooms/{room['id']}/generate", json={"seed": 42}).json()
    prop = gen["proposals"][0]
    unrated_ids = {p["id"] for p in created if p["display_name"].startswith("NoData")}
    assert len(set(prop["team_a_ids"]) & unrated_ids) == 1
    assert len(set(prop["team_b_ids"]) & unrated_ids) == 1
    assert "NoDataA" in prop["explanation"]["insufficient_data_players"]


def test_leetify_429_backoff_retry_after_and_scheduler_dedup(monkeypatch):
    import httpx
    from app.providers.external import LeetifyProvider

    attempts = {"profile": 0}
    sleeps: list[float] = []

    async def _fake_sleep(secs: float):
        sleeps.append(secs)

    import asyncio as _asyncio
    monkeypatch.setattr(_asyncio, "sleep", _fake_sleep)

    def _handler(request: httpx.Request) -> httpx.Response:
        if "/v3/profile/matches" in str(request.url):
            return httpx.Response(200, json=[])
        attempts["profile"] += 1
        if attempts["profile"] < 3:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(
            200,
            json={
                "id": "lt-retry",
                "name": "RetryOK",
                "total_matches": 50,
                "winrate": 0.54,
                "ranks": {"premier": 16200, "leetify": 2.4},
                "rating": {"aim": 68.5, "utility": 59.0, "positioning": 52.0, "clutch": 0.2},
                "stats": {"preaim": 9.1, "reaction_time_ms": 545.0, "accuracy_head": 18.0},
            },
        )

    orig_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: orig_async_client(transport=httpx.MockTransport(_handler), **kwargs),
    )

    provider = LeetifyProvider(api_key=None, timeout=2.0)
    res = asyncio.run(provider.fetch_by_steam_id64("76561198000050001"))
    assert attempts["profile"] == 3
    assert len(sleeps) >= 2
    assert res.status == "OK"
    assert res.data["premier_rating"] == 16200
    assert res.data["aim_rating"] == 68.5
    assert res.data["utility_rating"] == 59.0

