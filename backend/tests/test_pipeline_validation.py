from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app, health
from app.migrations import run_migrations
from app.models import MatchRoom, Player, ProviderSnapshot, TeamGeneration
from app.optimizer.engine import optimize_teams
from app.optimizer.normalizer import PlayerInput, normalize_player
from app.providers.external import LeetifyProvider
from app.services import player_service, scheduler, secrets_service


@pytest.fixture()
def pipeline_client(tmp_path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    run_migrations(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with SessionLocal() as db:
        player_service.get_or_create_default_community(db)

    secrets_service.set_vault_path_for_tests(tmp_path / "test_vault.dpapi.json")

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield SessionLocal, client
    secrets_service.set_vault_path_for_tests(None)
    app.dependency_overrides.clear()


# SANITIZED_LIVE_FIXTURE: based on observed Leetify Public v3 profile & match schema for a verified player
SANITIZED_LEETIFY_PROFILE = {
    "id": "00000000-0000-4000-8000-000000000001",
    "steam64_id": "76561199059518829",
    "name": "ZeniKoP_Fixture",
    "privacy_mode": "public",
    "total_matches": 1852,
    "winrate": 0.536,
    "ranks": {
        "premier": 19513,
        "leetify": 2.66,
        "faceit_elo": 1026,
        "faceit": 4,
    },
    "rating": {
        "aim": 69.85,
        "utility": 51.92,
        "positioning": 63.68,
        "clutch": 0.114,
    },
    "stats": {
        "preaim": 11.4,
        "reaction_time_ms": 541.3,
        "accuracy_enemy_spotted": 38.65,
        "accuracy_head": 46.9,
        "spray_accuracy": 41.57,
        "ct_opening_duel_success_percentage": 49.0,
        "t_opening_duel_success_percentage": 48.0,
        "trade_kills_success_percentage": 0.4996,
        "traded_deaths_success_percentage": 0.4963,
        "he_foes_damage_avg": 6.14,
        "counter_strafing_good_shots_ratio": 0.728,
    },
}

SANITIZED_LEETIFY_MATCHES = [
    {
        "id": f"match-fixture-{i}",
        "map_name": "de_mirage" if i % 2 == 0 else "de_inferno",
        "data_source": "matchmaking",
        "rounds_count": 22,
        "rounds_won": 13 if i < 6 else 8,
        "rounds_lost": 9 if i < 6 else 13,
        "finished_at": f"2026-11-{20 - i:02d}T18:00:00Z",
        "stats": [
            {
                "steam64_id": "76561199059518829",
                "total_kills": 20,
                "total_hs_kills": 10,
                "rounds_count": 22,
                "rounds_won": 13 if i < 6 else 8,
                "rounds_lost": 9 if i < 6 else 13,
                "leetify_rating": 0.025,
                "kd_ratio": 1.15,
                "dpr": 82.4,
                "preaim": 10.7,
                "reaction_time": 0.505,  # seconds -> converted to 505.0 ms
                "accuracy_enemy_spotted": 0.385,
                "spray_accuracy": 0.43,
                "counter_strafing_shots_good_ratio": 0.67,
                "trade_kill_opportunities": 5,
                "trade_kills_success_percentage": 0.54,
                "traded_death_opportunities": 4,
                "traded_deaths_success_percentage": 0.53,
                "flashbang_hit_foe": 7.0,
                "flash_assist": 0.25,
                "he_foes_damage_avg": 6.0,
                "multi2k": 1,
                "multi3k": 0,
                "multi4k": 0,
                "multi5k": 0,
            }
        ],
    }
    for i in range(10)
]


@pytest.mark.anyio
async def test_sanitized_leetify_fixture_lineage_validation_and_bounds():
    """Phase 3A & 3B: Verifies exact field parsing, unit conversion (s -> ms, fraction -> %), and positioning/traded deaths lineage."""
    prov = LeetifyProvider()

    def _fake_get(url: str, **kwargs):
        req = httpx.Request("GET", url)
        if url.endswith("/v3/profile"):
            return httpx.Response(200, request=req, json=SANITIZED_LEETIFY_PROFILE)
        if url.endswith("/v3/profile/matches"):
            return httpx.Response(200, request=req, json=SANITIZED_LEETIFY_MATCHES)
        return httpx.Response(404, request=req)

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=_fake_get)):
        res = await prov.fetch_by_steam_id64("76561199059518829", include_matches=True)

    assert res.status == "OK"
    assert res.endpoint_category == "profile_and_matches"
    assert res.data["premier_rating"] == 19513
    assert res.data["positioning_rating"] == pytest.approx(63.68, abs=0.01)

    r10 = res.data["combat_stats_recent10"]
    lt = res.data["combat_stats_lifetime"]
    assert r10["reaction_time_ms"] == pytest.approx(505.0, abs=0.2)
    assert r10["traded_deaths_pct"] == pytest.approx(53.0, abs=0.1)
    assert lt["traded_deaths_pct"] == pytest.approx(49.63, abs=0.05)
    assert lt["trade_kills_per_match"] == pytest.approx(49.96, abs=0.05)
    assert lt["consistency_score"] == pytest.approx(72.8, abs=0.1)

    # Corrupt/outlier mock boundary check: out-of-range percentages must normalize to None cleanly
    corrupt_profile = json.loads(json.dumps(SANITIZED_LEETIFY_PROFILE))
    corrupt_profile["winrate"] = 999.0
    corrupt_profile["rating"]["positioning"] = -15.0
    corrupt_profile["stats"]["reaction_time_ms"] = "bad_value"
    corrupt_profile["stats"]["traded_deaths_success_percentage"] = 142.0

    def _corrupt_get(url: str, **kwargs):
        req = httpx.Request("GET", url)
        if url.endswith("/v3/profile"):
            return httpx.Response(200, request=req, json=corrupt_profile)
        return httpx.Response(200, request=req, json=[])

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=_corrupt_get)):
        res_bad = await prov.fetch_by_steam_id64("76561199059518829", include_matches=True)

    assert res_bad.data["positioning_rating"] is None
    assert res_bad.data["combat_stats_lifetime"]["win_rate"] is None
    assert res_bad.data["combat_stats_lifetime"]["reaction_time_ms"] is None
    assert res_bad.data["combat_stats_lifetime"]["traded_deaths_pct"] is None


def test_positioning_and_traded_deaths_lineage_end_to_end(pipeline_client):
    SessionLocal, client = pipeline_client
    with SessionLocal() as db:
        comm = player_service.get_or_create_default_community(db)
        p = player_service.create_player(
            db,
            comm.id,
            player_service.PlayerCreate(
                display_name="LineagePlayer",
                steam_id64="76561199059518829",
                premier_rating=15000,
                leetify_rating=2.0,
            ),
        )
        cp_id = p.id

    with SessionLocal() as db:
        from app.models import CommunityPlayer, PlayerStatSnapshot

        cp = db.scalar(select(CommunityPlayer).where(CommunityPlayer.id == cp_id))
        cp.aim_rating = 72.0
        cp.utility_rating = 60.0
        cp.positioning_rating = 78.0
        same_ts = datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc)
        # Same timestamp for both scopes must still preserve proper scope selection
        db.add(
            PlayerStatSnapshot(
                player_id=cp.player_id,
                provider="leetify",
                scope="lifetime",
                sample_size=200,
                matches_played=200,
                adr=84.0,
                kd_ratio=1.18,
                positioning_rating=78.0,
                traded_deaths_pct=62.0,
                captured_at=same_ts,
            )
        )
        db.add(
            PlayerStatSnapshot(
                player_id=cp.player_id,
                provider="leetify",
                scope="recent",
                sample_size=10,
                matches_played=10,
                adr=91.5,
                kd_ratio=1.31,
                reaction_time_ms=495.0,
                traded_deaths_pct=66.0,
                captured_at=same_ts,
            )
        )
        db.commit()

    reg = client.get("/api/metrics/registry")
    assert reg.status_code == 200
    reg_names = {m["canonical_name"]: m for m in reg.json()["metrics"]}
    assert reg_names["positioning_rating"]["used_in_matchmaking"] is True
    assert reg_names["traded_deaths_pct"]["used_in_matchmaking"] is True
    assert "UNAVAILABLE" in reg_names["kast"]["provider_field_map"]["leetify"]

    prof = client.get(f"/api/players/{cp_id}/profile").json()
    assert prof["player"]["positioning_rating"] == pytest.approx(78.0)
    assert prof["stat_snapshots"][0]["scope"] == "recent"
    assert prof["stat_snapshots"][0]["adr"] == pytest.approx(91.5)
    assert prof["stat_snapshots"][1]["scope"] == "lifetime"
    assert prof["stat_snapshots"][1]["traded_deaths_pct"] == pytest.approx(62.0)

    # Normalizer verifies positioning_score uses positioning_rating + traded_deaths_pct
    with SessionLocal() as db:
        from app.models import CommunityPlayer

        cp = db.scalar(select(CommunityPlayer).where(CommunityPlayer.id == cp_id))
        pin, _ = player_service.build_player_input(db, cp)
    norm = normalize_player(pin)
    assert norm.positioning_score is not None
    assert norm.positioning_score > 70.0


def test_matchmaking_ten_scenarios_across_126_partitions():
    """Phase 3C: Evaluates stackforge_126_v2 across all 10 required CS2 scenario archetypes."""
    def _mk(i: int, **kw) -> PlayerInput:
        defaults = dict(
            community_player_id=f"p{i}",
            display_name=f"P{i}",
            steam_id64=f"765611980000000{i:02d}",
            identity_status="STEAM_RESOLVED",
            premier_rating=14000,
            leetify_rating=1.0,
            aim_rating=62.0,
            utility_rating=55.0,
            positioning_rating=58.0,
            adr=80.0,
            kd_ratio=1.1,
            hs_pct=45.0,
            opening_duel_pct=48.0,
            trade_kills_per_match=48.0,
            traded_deaths_pct=50.0,
            utility_damage_per_round=14.0,
            flash_assists_per_round=0.015,
            enemies_flashed_per_round=0.25,
            clutch_win_pct=16.0,
            consistency_score=70.0,
            stats_sample_size=25,
        )
        defaults.update(kw)
        return PlayerInput(**defaults)

    # 1. Ten fully rated players with spread skills -> close strength diff
    s1 = [_mk(i, premier_rating=8000 + i * 1600, leetify_rating=-2.0 + i * 0.6, aim_rating=45 + i * 4.5, utility_rating=40 + (9 - i) * 3.5, positioning_rating=48 + i * 2.5) for i in range(10)]
    r1 = optimize_teams(s1, seed=10)
    assert r1.total_partitions_evaluated == 126
    assert r1.recommended.strength_diff <= 2.5

    # 2. Missing metrics -> unrated players split evenly (1 A, 1 B)
    s2 = [_mk(i, premier_rating=12000) for i in range(8)] + [
        _mk(8, premier_rating=None, leetify_rating=None, faceit_elo=None, aim_rating=None, utility_rating=None, positioning_rating=None, adr=None, kd_ratio=None, stats_sample_size=0),
        _mk(9, premier_rating=None, leetify_rating=None, faceit_elo=None, aim_rating=None, utility_rating=None, positioning_rating=None, adr=None, kd_ratio=None, stats_sample_size=0),
    ]
    r2 = optimize_teams(s2, seed=11)
    assert r2.recommended.objective_components["unknown_count_gap"] == 0.0
    assert len(r2.explanation["insufficient_data_players"]) == 2

    # 3. Different rating scales (Premier vs FACEIT vs Leetify) calibrated comparably
    p_prem = normalize_player(_mk(1, premier_rating=20000, faceit_elo=None, leetify_rating=None))
    p_fac = normalize_player(_mk(2, premier_rating=None, faceit_elo=1850, leetify_rating=None))
    assert abs((p_prem.normalized_strength or 0) - (p_fac.normalized_strength or 0)) < 6.0

    # 4. Identical ratings -> deterministic reproducible split & near-zero diff
    s4 = [_mk(i) for i in range(10)]
    r4a = optimize_teams(s4, seed=42)
    r4b = optimize_teams(s4, seed=42)
    assert r4a.recommended.partition_key == r4b.recommended.partition_key
    assert r4a.recommended.strength_diff == 0.0

    # 5. Stale snapshots -> confidence lowered honestly & surfaced in explanation
    s5 = [_mk(i, stats_stale=(i < 4)) for i in range(10)]
    r5 = optimize_teams(s5, seed=12)
    assert r5.explanation["stale_count"] == 4
    assert r5.normalized_players["p0"].confidence < r5.normalized_players["p9"].confidence

    # 6. Exceptionally strong carry player: mathematically pairs superstar with the 4 weakest teammates and explains trade-off
    s6 = [_mk(0, premier_rating=31000, faceit_elo=2850, leetify_rating=8.5, aim_rating=92.0)] + [_mk(i, premier_rating=9500 + i * 400, leetify_rating=0.0) for i in range(1, 10)]
    r6 = optimize_teams(s6, seed=13)
    assert set(r6.recommended.team_a_ids) == {"p0", "p1", "p2", "p3", "p4"}
    assert all(alt.strength_diff >= r6.recommended.strength_diff for alt in r6.alternatives)
    assert any("top-end carry" in t for t in r6.explanation["trade_offs"])

    # 7 & 8. High aim / weak utility vs strong utility / weaker aim
    s7 = [
        _mk(i, premier_rating=15000, aim_rating=86.0 if i < 5 else 46.0, utility_rating=32.0 if i < 5 else 84.0)
        for i in range(10)
    ]
    r7 = optimize_teams(s7, seed=14)
    assert r7.recommended.objective_components["aim_gap"] <= 8.0
    assert r7.recommended.objective_components["utility_gap"] <= 8.0

    # 9 & 10. Small recent sample vs large lifetime sample confidence differentiation
    small_p = normalize_player(_mk(1, stats_sample_size=2, recent_form=0.9))
    large_p = normalize_player(_mk(2, stats_sample_size=80, recent_form=0.9))
    assert small_p.confidence < large_p.confidence
    assert abs(small_p.recent_form_normalized) < abs(large_p.recent_form_normalized)


def test_credential_vault_match_result_ops_and_scheduler(pipeline_client):
    SessionLocal, client = pipeline_client

    # 1. Credential vault (DPAPI server-side only, never exposes secret in GET responses)
    bad = client.put("/api/settings/credentials/steam", json={"api_key": "short", "validate_live": False})
    assert bad.status_code == 422

    saved = client.put("/api/settings/credentials/steam", json={"api_key": "STEAM_TEST_KEY_12345678", "validate_live": False})
    assert saved.status_code == 200
    cred = saved.json()["credential"]
    assert cred["configured"] is True
    assert cred["masked_hint"] == "****5678"
    assert "STEAM_TEST_KEY_12345678" not in json.dumps(saved.json())

    listed = client.get("/api/settings/credentials")
    assert listed.status_code == 200
    assert "STEAM_TEST_KEY_12345678" not in listed.text
    assert secrets_service.get_secret("steam") == "STEAM_TEST_KEY_12345678"

    deleted = client.delete("/api/settings/credentials/steam")
    assert deleted.status_code == 200
    assert deleted.json()["credential"]["configured"] is False

    # 2. Create 10 players + Match Room -> Generate -> Finalize -> Played -> Result Recorded -> Standings
    pids = []
    for i in range(10):
        resp = client.post(
            "/api/players",
            json={
                "display_name": f"StackP{i}",
                "steam_id64": f"765611980000100{i:02d}",
                "premier_rating": 11000 + i * 800,
                "leetify_rating": -1.5 + i * 0.4,
            },
        )
        assert resp.status_code == 201
        pids.append(resp.json()["id"])

    room = client.post("/api/rooms", json={"title": "Post-Match Validation 5v5"}).json()
    client.put(f"/api/rooms/{room['id']}/roster", json={"community_player_ids": pids})
    gen_room = client.post(f"/api/rooms/{room['id']}/generate", json={"seed": 42}).json()
    gen_id = gen_room["proposals"][0]["id"]
    # Sub-dimension scores persisted cleanly in generation snapshot
    assert "dimension_scores" in gen_room["proposals"][0]["input_snapshot"][0]

    fin_room = client.post(
        f"/api/rooms/{room['id']}/finalize",
        json={"generation_id": gen_id, "finalized_by": "Host"},
    )
    assert fin_room.status_code == 200 and fin_room.json()["status"] == "FINALIZED"

    played = client.post(f"/api/rooms/{room['id']}/played")
    assert played.status_code == 200 and played.json()["status"] == "PLAYED"

    # Mismatched score/winner must return 422 cleanly
    bad_res = client.post(
        f"/api/rooms/{room['id']}/result",
        json={"map_played": "de_mirage", "team_a_score": 13, "team_b_score": 8, "winner_side": "B"},
    )
    assert bad_res.status_code == 422

    ok_res = client.post(
        f"/api/rooms/{room['id']}/result",
        json={"map_played": "de_mirage", "team_a_score": 13, "team_b_score": 9},
    )
    assert ok_res.status_code == 201
    res_body = ok_res.json()
    assert res_body["status"] == "RESULT_RECORDED"
    assert res_body["result"]["winner_side"] == "A"
    assert res_body["result"]["model_version"] == "stackforge_126_v2"

    # Locked room cannot be reopened once post-match result recorded
    reopen_fail = client.post(f"/api/rooms/{room['id']}/reopen")
    assert reopen_fail.status_code == 409

    # Community standings reflect 13-9 result while external premier_rating stayed untouched
    standings = client.get("/api/standings/community").json()
    assert standings["total_matches_recorded"] == 1
    assert len(standings["standings"]) == 10
    p0 = client.get(f"/api/players/{pids[0]}/profile").json()["player"]
    assert p0["premier_rating"] == 11000

    # 3. Operational health overview reports honest states
    ops = client.get("/api/ops/overview").json()
    assert ops["database"]["status"] == "ok"
    assert ops["database"]["match_results_recorded"] == 1
    assert ops["scheduler"]["state"] == "disabled_in_tests"
    assert any(p["provider"] == "faceit" and p["health_state"] == "NOT_CONFIGURED" for p in ops["providers"])

    # 4. Verify health() sees active scheduler state (regression check for old by-value import bug)
    async def _check_scheduler_singleton():
        with patch("app.services.scheduler._scheduler_disabled_reason", return_value=None):
            scheduler.start_background_scheduler()
            first_task = scheduler._scheduler_task
            scheduler.start_background_scheduler()
            assert scheduler._scheduler_task is first_task
            assert health()["scheduler"] == "active"
            await scheduler.stop_background_scheduler()
            assert health()["scheduler"] == "inactive"

    asyncio.run(_check_scheduler_singleton())


@pytest.mark.anyio
async def test_cswatch_preserves_stored_at_stale_convictions_and_unknown():
    """Phase 4 CSWatch hardening: preserves storedAt/stale/convictionCount/isCheater and never fakes OK on missing/stale records."""
    from app.providers.cswatch import CSWatchProvider

    CSWatchProvider._request_timestamps.clear()
    cw = CSWatchProvider(timeout=2.0)

    def _cw_resp(body: dict):
        req = httpx.Request("GET", "https://cswatch.gg/api/public/player/76561198000000001")
        return httpx.Response(200, request=req, json=body)

    with patch(
        "httpx.AsyncClient.get",
        new=AsyncMock(
            return_value=_cw_resp(
                {
                    "steamId": "76561198000000001",
                    "stored": False,
                    "storedAt": None,
                    "stale": False,
                    "reputationScore": None,
                    "riskLevel": "unknown",
                    "isCheater": False,
                    "convictionCount": 0,
                    "bans": {"vac": False, "gameBans": 0},
                }
            )
        ),
    ):
        res_unk = await cw.fetch_player("76561198000000001")
    assert res_unk.status == "UNKNOWN"
    assert res_unk.freshness == "UNKNOWN"
    assert res_unk.data["stored"] is False

    with patch(
        "httpx.AsyncClient.get",
        new=AsyncMock(
            return_value=_cw_resp(
                {
                    "steamId": "76561198000000001",
                    "stored": True,
                    "storedAt": "2026-11-08T03:12:45.000Z",
                    "stale": True,
                    "generatedAt": "2026-11-26T10:00:00.000Z",
                    "reputationScore": 88,
                    "riskLevel": "low",
                    "isCheater": False,
                    "convictionCount": 0,
                    "bans": {"vac": False, "gameBans": 0},
                }
            )
        ),
    ):
        res_stale = await cw.fetch_player("76561198000000001")
    assert res_stale.status == "STALE"
    assert res_stale.freshness == "STALE"
    assert res_stale.data["stored_at"] == "2026-11-08T03:12:45.000Z"
    assert res_stale.data["stale"] is True
    assert res_stale.data["steam_data_freshness"] == "STALE"
    assert res_stale.data["convictions_freshness"] == "CURRENT"
    assert res_stale.data["convictions_current"] is True
    assert res_stale.data["permission_status"] == "CLARIFICATION_REQUIRED"

    with patch(
        "httpx.AsyncClient.get",
        new=AsyncMock(
            return_value=_cw_resp(
                {
                    "steamId": "76561198000000001",
                    "stored": True,
                    "storedAt": "2026-11-08T03:12:45.000Z",
                    "stale": True,
                    "reputationScore": 25,
                    "riskLevel": "medium",
                    "isCheater": True,
                    "convictionCount": 2,
                    "bans": {"vac": False, "gameBans": 0},
                }
            )
        ),
    ):
        res_flag = await cw.fetch_player("76561198000000001")
    assert res_flag.status == "FLAGGED"
    assert res_flag.data["conviction_count"] == 2
    assert res_flag.data["is_cheater"] is True
    assert res_flag.data["steam_data_freshness"] == "STALE"
    assert res_flag.data["convictions_freshness"] == "CURRENT"
