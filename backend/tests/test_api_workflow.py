from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services.player_service import get_or_create_default_community


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as db:
        get_or_create_default_community(db)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_player_registry_and_bulk_import(client: TestClient):
    # Create player with SteamID64
    r = client.post(
        "/api/players",
        json={
            "display_name": "Alpha",
            "steam_id64": "76561198000000001",
            "manual_rating": 72,
            "primary_role": "IGL",
        },
    )
    assert r.status_code == 201
    p1 = r.json()
    assert p1["steam_id64"] == "76561198000000001"

    # Duplicate SteamID64 blocked
    dup = client.post(
        "/api/players",
        json={
            "display_name": "AlphaDup",
            "steam_id64": "76561198000000001",
            "manual_rating": 70,
        },
    )
    assert dup.status_code == 409

    # Bulk import: 1 duplicate SteamID, 1 new profile URL, 1 vanity unresolved (no API key), 1 manual name, 1 bad URL
    bulk = client.post(
        "/api/players/bulk-import",
        json={
            "text": "\n".join(
                [
                    "76561198000000001",
                    "https://steamcommunity.com/profiles/76561198000000002",
                    "https://steamcommunity.com/id/somevanity",
                    "Bravo | 68 | Entry",
                    "https://example.com/notsteam",
                ]
            )
        },
    )
    assert bulk.status_code == 200
    bdata = bulk.json()
    assert bdata["duplicate_count"] == 1
    assert bdata["created_count"] == 2
    assert bdata["unresolved_count"] == 1
    assert bdata["invalid_count"] == 1

    # Search, edit, delete
    search = client.get("/api/players?q=Bravo")
    assert search.status_code == 200
    assert len(search.json()) == 1
    bravo_id = search.json()[0]["id"]

    upd = client.patch(f"/api/players/{bravo_id}", json={"manual_rating": 74})
    assert upd.status_code == 200
    assert upd.json()["manual_rating"] == 74.0

    rem = client.delete(f"/api/players/{bravo_id}")
    assert rem.status_code == 204


def test_full_match_room_workflow_end_to_end(client: TestClient):
    seeded = client.post("/api/players/seed-demo")
    assert seeded.status_code == 200
    players = seeded.json()
    assert len(players) == 10
    player_ids = [p["id"] for p in players]

    # Create room
    room_resp = client.post("/api/rooms", json={"title": "Friday Night 10-Man"})
    assert room_resp.status_code == 201
    room_id = room_resp.json()["id"]

    # Reject generation with < 10 players
    client.put(f"/api/rooms/{room_id}/roster", json={"community_player_ids": player_ids[:9]})
    bad_gen = client.post(f"/api/rooms/{room_id}/generate", json={"seed": 42})
    assert bad_gen.status_code == 422

    # Reject > 10 players or duplicates
    extra = client.post("/api/players", json={"display_name": "Sub11", "manual_rating": 60}).json()
    assert client.put(f"/api/rooms/{room_id}/roster", json={"community_player_ids": player_ids + [extra["id"]]}).status_code == 422
    assert client.put(f"/api/rooms/{room_id}/roster", json={"community_player_ids": player_ids[:9] + [player_ids[0]]}).status_code == 422

    # Set 10 unique players
    ready = client.put(f"/api/rooms/{room_id}/roster", json={"community_player_ids": player_ids})
    assert ready.status_code == 200
    assert ready.json()["selected_count"] == 10
    assert ready.json()["status"] == "READY_TO_GENERATE"

    # Non-blocking preflight even without API keys
    pf = client.post(f"/api/rooms/{room_id}/preflight")
    assert pf.status_code == 200

    # Generate initial proposal
    gen1 = client.post(f"/api/rooms/{room_id}/generate", json={"seed": 42})
    assert gen1.status_code == 200
    p1 = gen1.json()["proposals"][0]
    assert p1["proposal_number"] == 1
    assert len(p1["team_a_ids"]) == 5
    assert len(p1["team_b_ids"]) == 5

    # Submit objection and approve
    fb_resp = client.post(
        f"/api/rooms/{room_id}/proposals/{p1['id']}/feedback",
        json={
            "community_player_id": p1["team_a_ids"][0],
            "target_player_id": p1["team_b_ids"][0],
            "feedback_type": "SWAP_REQUEST",
            "reason": "Swap top fraggers",
        },
    )
    assert fb_resp.status_code == 200
    fb_id = fb_resp.json()["proposals"][0]["feedback"][0]["id"]
    res_fb = client.post(
        f"/api/rooms/{room_id}/feedback/{fb_id}/resolve",
        json={"status": "APPROVED", "host_note": "Testing swap"},
    )
    assert res_fb.status_code == 200
    assert res_fb.json()["proposals"][0]["feedback"][0]["status"] == "APPROVED"

    # Swap preview + commit creates Proposal #2 while preserving #1
    pa, pb = p1["team_a_ids"][0], p1["team_b_ids"][0]
    prev = client.post(
        f"/api/rooms/{room_id}/swap-preview",
        json={"generation_id": p1["id"], "player_a_id": pa, "player_b_id": pb},
    )
    assert prev.status_code == 200
    assert "after_strength_diff" in prev.json()

    swapped = client.post(
        f"/api/rooms/{room_id}/swap",
        json={"generation_id": p1["id"], "player_a_id": pa, "player_b_id": pb, "reason": "Requested swap"},
    )
    assert swapped.status_code == 200
    assert len(swapped.json()["proposals"]) == 2
    assert swapped.json()["proposals"][0]["action_type"] == "SWAP"

    # Lock a player to Team A and regenerate -> Proposal #3 differs from #1 and #2 and honors lock
    locked_id = player_ids[0]
    client.put(f"/api/rooms/{room_id}/players/{locked_id}/lock", json={"locked_team": "A"})
    regen = client.post(f"/api/rooms/{room_id}/regenerate", json={"seed": 42})
    assert regen.status_code == 200
    p3 = regen.json()["proposals"][0]
    assert p3["proposal_number"] == 3
    assert locked_id in p3["team_a_ids"]
    assert p3["partition_key"] not in {p1["partition_key"], swapped.json()["proposals"][0]["partition_key"]}

    # Restore Proposal #1 -> Proposal #4
    restored = client.post(f"/api/rooms/{room_id}/proposals/{p1['id']}/restore")
    assert restored.status_code == 200
    p4 = restored.json()["proposals"][0]
    assert p4["proposal_number"] == 4
    assert p4["action_type"] == "RESTORE"
    assert p4["partition_key"] == p1["partition_key"]

    # Finalize Proposal #4
    fin = client.post(
        f"/api/rooms/{room_id}/finalize",
        json={"generation_id": p4["id"], "finalized_by": "Host"},
    )
    assert fin.status_code == 200
    fdata = fin.json()
    assert fdata["status"] == "FINALIZED"
    assert fdata["finalized_lineup"]["proposal_number"] == 4
    assert "TEAM A" in fdata["finalized_lineup"]["discord_text"]
    assert "TEAM B" in fdata["finalized_lineup"]["discord_text"]

    # Shared lineup slug works
    slug = fdata["finalized_lineup"]["share_slug"]
    shared = client.get(f"/api/lineups/{slug}")
    assert shared.status_code == 200
    assert shared.json()["lineup"]["proposal_number"] == 4
