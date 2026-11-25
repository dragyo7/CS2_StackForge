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
from app.models import Player, PlayerMatchRecord, PlayerStatSnapshot
from app.optimizer.engine import optimize_teams
from app.optimizer.normalizer import PlayerInput
from app.providers.base import ProviderResult
from app.providers.steam import SteamProvider
from app.schemas import PlayerCreate
from app.services import identity_resolver, player_service


@pytest.fixture()
def db_and_client():
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


def test_all_duplicate_prevention_cases_and_archive_preserves_global_player(db_and_client):
    SessionLocal, client = db_and_client

    # Register Dark Stone by SteamID64
    p1 = client.post(
        "/api/players",
        json={
            "display_name": "Dark Stone",
            "steam_id64": "76561199004135497",
            "manual_rating": 60,
        },
    ).json()

    # 1. Duplicate raw SteamID64 rejected
    assert (
        client.post(
            "/api/players",
            json={"display_name": "Dup1", "steam_id64": "76561199004135497", "manual_rating": 55},
        ).status_code
        == 409
    )

    # 2. Same profile using different URL formats (steamcommunity /profiles/ & csstats.gg)
    bulk = client.post(
        "/api/players/bulk-import",
        json={
            "text": "\n".join(
                [
                    "https://steamcommunity.com/profiles/76561199004135497",
                    "https://csstats.gg/player/76561199004135497",
                ]
            )
        },
    ).json()
    assert bulk["duplicate_count"] == 2
    assert bulk["created_count"] == 0

    # 3. Vanity URL resolving to same SteamID64 (simulated rahulp2134 -> 76561199004135497) rejected as duplicate
    class _FakeVanitySteam(SteamProvider):
        async def resolve_vanity_url(self, vanity_name: str):
            if vanity_name == "rahulp2134":
                return "76561199004135497", "OK"
            if vanity_name == "solitarysam":
                return "76561198935753726", "OK"
            return None, "NOT_FOUND"

    with SessionLocal() as db:
        comm = player_service.get_or_create_default_community(db)
        with pytest.raises(Exception) as exc:
            asyncio.run(
                player_service.create_player_with_resolution(
                    db,
                    comm.id,
                    PlayerCreate(display_name="RahulVanity", steam_profile_url="https://steamcommunity.com/id/rahulp2134/"),
                    steam_provider=_FakeVanitySteam(),
                )
            )
        assert "409" in str(exc.value) or "Duplicate" in str(exc.value)

        # New distinct vanity solitarysam succeeds
        p_new = asyncio.run(
            player_service.create_player_with_resolution(
                db,
                comm.id,
                PlayerCreate(display_name="Pramod_Dubey", steam_profile_url="https://steamcommunity.com/id/solitarysam/"),
                steam_provider=_FakeVanitySteam(),
            )
        )
        assert p_new.steam_id64 == "76561198935753726"

        # 8. Attempt to link same external csstats identity to a second player -> 409 conflict
        identity_resolver.confirm_identity_link(
            db, comm.id, p1["id"], "csstats", "76561199004135497", "https://csstats.gg/player/76561199004135497"
        )
        with pytest.raises(Exception) as exc2:
            identity_resolver.confirm_identity_link(
                db, comm.id, p_new.id, "csstats", "76561199004135497", "https://csstats.gg/player/76561199004135497"
            )
        assert "409" in str(exc2.value) or "already linked" in str(exc2.value)

        # Record a match history item on Dark Stone, then archive & remove from community -> global Player & match preserved!
        db.add(
            PlayerMatchRecord(
                player_id=p1["player_id"],
                provider="leetify",
                external_match_id="match-preserve-1",
                map_name="de_mirage",
                outcome="win",
            )
        )
        db.commit()

    arch = client.post(f"/api/players/{p1['id']}/archive?archived=true")
    assert arch.status_code == 200
    assert arch.json()["is_archived"] is True
    assert all(p["id"] != p1["id"] for p in client.get("/api/players").json())
    assert any(p["id"] == p1["id"] for p in client.get("/api/players?include_archived=true").json())

    rem = client.delete(f"/api/players/{p1['id']}")
    assert rem.status_code == 204
    with SessionLocal() as db:
        assert db.scalar(select(Player).where(Player.id == p1["player_id"])) is not None
        assert db.scalar(select(PlayerMatchRecord).where(PlayerMatchRecord.external_match_id == "match-preserve-1")) is not None


def test_cs2_native_explanation_handles_real_missing_and_stale_stats():
    # Mix of tracked combat players, identical baseline ratings, stale stats, and missing stats
    players = []
    for i in range(10):
        players.append(
            PlayerInput(
                community_player_id=f"p{i}",
                display_name=f"Player{i}",
                steam_id64=f"765611980000000{i:02d}",
                identity_status="STEAM_RESOLVED",
                manual_rating=60.0,
                adr=84.0 if i < 3 else (64.0 if i < 6 else None),
                kd_ratio=1.22 if i < 3 else (0.92 if i < 6 else None),
                opening_duel_pct=53.0 if i < 3 else (45.0 if i < 6 else None),
                clutch_win_pct=21.0 if i < 3 else (28.0 if i < 6 else None),
                utility_damage_per_round=17.5 if i < 3 else None,
                stats_sample_size=15 if i < 6 else 0,
                stats_stale=(i == 4),
            )
        )

    res = optimize_teams(players, seed=42)
    exp = res.explanation
    assert exp["matchup_label"] in {"Very close matchup", "Competitive matchup", "Some imbalance — consider an alternative"}
    assert len(exp["team_a_notes"]) >= 1
    assert len(exp["team_b_notes"]) >= 1
    assert "uncertainty" in exp["good_match_summary"].lower()
    # Ensure no algorithmic jargon leaks into player-facing notes
    joined = (exp["good_match_summary"] + " " + " ".join(exp["team_a_notes"] + exp["team_b_notes"])).lower()
    assert "objective function" not in joined
    assert "optimizer score" not in joined
    assert "partition score" not in joined
    # Ensure anchor and low player are never identical even when ratings tie
    for contrib in exp["player_contributions"]:
        assert "paired with" in contrib
        left, right = contrib.split("paired with", 1)
        left_name = left.split("anchor:", 1)[1].split("(", 1)[0].strip()
        right_name = right.split("(", 1)[0].strip()
        assert left_name != right_name


def test_recent_lifetime_priority_strength_parity_and_safety_warnings(db_and_client):
    SessionLocal, client = db_and_client
    from app.models import TrustSignal, WatchlistEntry

    p_ids = []
    for i in range(10):
        resp = client.post(
            "/api/players",
            json={
                "display_name": f"Stack{i}",
                "steam_id64": f"765611980000100{i:02d}",
                "manual_rating": 55.0 + i,
            },
        )
        assert resp.status_code == 201
        p_ids.append(resp.json())

    now = datetime.now(timezone.utc)
    # Give Stack0 separate recent and lifetime snapshots with same captured_at AND trust signals
    with SessionLocal() as db:
        comm = player_service.get_or_create_default_community(db)
        pid = p_ids[0]["player_id"]
        db.add(
            PlayerStatSnapshot(
                player_id=pid,
                provider="leetify",
                scope="recent",
                game_mode="Leetify CS2",
                sample_size=10,
                matches_played=10,
                adr=94.0,
                kd_ratio=1.35,
                win_rate=60.0,
                freshness="FRESH",
                captured_at=now,
            )
        )
        db.add(
            PlayerStatSnapshot(
                player_id=pid,
                provider="leetify",
                scope="lifetime",
                game_mode="Leetify CS2",
                sample_size=120,
                matches_played=120,
                adr=72.0,
                kd_ratio=1.05,
                opening_duel_pct=56.0,
                trade_kills_per_match=22.0,
                clutch_win_pct=29.0,
                consistency_score=74.0,
                freshness="FRESH",
                captured_at=now,
            )
        )
        db.add(
            TrustSignal(
                community_id=comm.id,
                player_id=pid,
                category="THIRD_PARTY_REPUTATION",
                provider="cswatch",
                status="FLAGGED",
                summary="CSWatch reputation 35/100 (risk: high)",
                payload_json='{"risk_level":"high","reputation_score":35}',
                observed_at=now,
            )
        )
        db.add(
            WatchlistEntry(
                community_id=comm.id,
                player_id=pid,
                status="WATCHING",
                reason="Test host review flag",
            )
        )
        db.commit()

        cp0 = player_service._get_cp_or_404(db, comm.id, p_ids[0]["id"])
        before_trust_str = player_service.to_player_out(db, cp0)
        eff = player_service.select_effective_player_stats(db, pid)
        assert eff["adr"] == 94.0  # recent preferred over lifetime (72.0)
        assert eff["opening_duel_pct"] == 56.0  # lifetime preferred
        assert eff["trade_kills_per_match"] == 22.0
        assert eff["clutch_win_pct"] == 29.0
        assert eff["consistency_score"] == 74.0
        assert before_trust_str.trust_summary is not None
        assert before_trust_str.trust_summary.cswatch_status == "FLAGGED"
        assert before_trust_str.trust_summary.watchlist_status == "WATCHING"

    room = client.post("/api/rooms", json={"title": "Parity Test Room"}).json()
    client.put(f"/api/rooms/{room['id']}/roster", json={"community_player_ids": [p["id"] for p in p_ids]})
    gen = client.post(f"/api/rooms/{room['id']}/generate", json={"seed": 42}).json()
    prop = gen["proposals"][0]
    snap0 = next(s for s in prop["input_snapshot"] if s["id"] == p_ids[0]["id"])
    reg0 = next(p for p in client.get("/api/players").json() if p["id"] == p_ids[0]["id"])
    # Exact parity between registry strength and optimizer snapshot strength
    assert reg0["normalized_strength"] == snap0["normalized_strength"]
    assert snap0["adr"] == 94.0
    assert snap0["opening_duel_pct"] == 56.0
    assert snap0["trade_kills_per_match"] == 22.0
    assert snap0["consistency_score"] == 74.0
