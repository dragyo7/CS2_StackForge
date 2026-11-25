from __future__ import annotations

import asyncio
import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.migrations import run_migrations
from app.optimizer.normalizer import normalize_leetify
from app.providers.base import ProviderResult
from app.services import identity_resolver, import_service, player_service, trust_service


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


def test_spreadsheet_csv_and_xlsx_import_with_safe_reimport(db_and_client):
    _SessionLocal, client = db_and_client

    csv_content = (
        "Name,Url,IGN\n"
        "Rahul Pathak,https://csstats.gg/player/76561199004135497,Dark Stone\n"
        "Pallab Biswas,https://csstats.gg/player/76561199103949034,Gamershell\n"
        "Duplicate Row,https://csstats.gg/player/76561199004135497,Dark Stone Dup\n"
        "No Link Friend,,ManualGuy\n"
    ).encode("utf-8")

    prev = client.post(
        "/api/imports/file/preview",
        files={"file": ("cs2.csv", csv_content, "text/csv")},
    )
    assert prev.status_code == 200
    pdata = prev.json()
    assert pdata["counts"]["NEW"] == 2
    assert pdata["counts"]["DUPLICATE_IN_SHEET"] == 1
    assert pdata["counts"]["UNRESOLVED"] == 1

    comm = client.post(
        "/api/imports/file/commit",
        files={"file": ("cs2.csv", csv_content, "text/csv")},
    )
    assert comm.status_code == 200
    cdata = comm.json()
    assert cdata["summary"]["created"] == 2
    assert cdata["summary"]["duplicates"] == 1
    assert cdata["summary"]["unresolved"] == 1

    # Edit Dark Stone manually -> re-import without overwrite_manual preserves manual rating/name!
    players = client.get("/api/players").json()
    dark = next(p for p in players if p["steam_id64"] == "76561199004135497")
    assert any(e["provider"] == "csstats" for e in dark["external_identities"])
    client.patch(f"/api/players/{dark['id']}", json={"display_name": "DarkStone_Custom", "manual_rating": 81})

    reimp = client.post(
        "/api/imports/file/commit",
        files={"file": ("cs2.csv", csv_content, "text/csv")},
        data={"overwrite_manual": "false"},
    )
    assert reimp.status_code == 200
    assert reimp.json()["summary"]["created"] == 0
    assert reimp.json()["summary"]["matched"] == 2

    after_players = client.get("/api/players").json()
    assert len(after_players) == 2
    dark_after = next(p for p in after_players if p["steam_id64"] == "76561199004135497")
    assert dark_after["display_name"] == "DarkStone_Custom"
    assert dark_after["manual_rating"] == 81.0

    # XLSX upload test
    wb = Workbook()
    ws = wb.active
    ws.append(["Name", "Url", "IGN"])
    ws.append(["Arnav Motghare", "https://csstats.gg/player/76561199163085297", "A4NAV"])
    buf = io.BytesIO()
    wb.save(buf)
    xlsx_res = client.post(
        "/api/imports/file/commit",
        files={"file": ("sheet.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert xlsx_res.status_code == 200
    assert xlsx_res.json()["summary"]["created"] == 1


def test_universal_identity_resolver_and_no_false_merges(db_and_client):
    SessionLocal, client = db_and_client
    p = client.post(
        "/api/players",
        json={"display_name": "Drago7", "steam_id64": "76561199567884246", "manual_rating": 65},
    ).json()

    # CSStats URL resolves directly to canonical SteamID64 and matches existing player
    with SessionLocal() as db:
        comm = player_service.get_or_create_default_community(db)

        class _Noop:
            async def resolve_vanity_url(self, _v): return None, "NOT_CONFIGURED"
            async def fetch_by_steam_id64(self, _s, include_matches=False): return ProviderResult("leetify", "NOT_FOUND", "None")
            async def fetch_by_nickname(self, _n): return ProviderResult("faceit", "NOT_CONFIGURED", "None")
            async def fetch_player(self, _s): return ProviderResult("cswatch", "NOT_FOUND", "None")

        res = asyncio.run(
            identity_resolver.resolve_identifier(
                db,
                comm.id,
                "https://csstats.gg/player/76561199567884246",
                steam_provider=_Noop(),
                leetify_provider=_Noop(),
                faceit_provider=_Noop(),
                cswatch_provider=_Noop(),
            )
        )
        assert res["confidence_state"] == "VERIFIED"
        assert res["resolved_steam_id64"] == "76561199567884246"
        assert res["matched_existing"][0]["community_player_id"] == p["id"]

        # Nickname match returns CANDIDATE only (never auto-merged!)
        cand = asyncio.run(
            identity_resolver.resolve_identifier(
                db, comm.id, "Drago7", discover_providers=False,
                steam_provider=_Noop(), leetify_provider=_Noop(), faceit_provider=_Noop(), cswatch_provider=_Noop()
            )
        )
        assert cand["confidence_state"] == "CANDIDATE"
        assert cand["matched_existing"][0]["confidence_state"] == "CANDIDATE"


def test_trust_watchtower_separated_signals_and_review(db_and_client):
    SessionLocal, client = db_and_client
    p = client.post(
        "/api/players",
        json={"display_name": "WatchedPlayer", "steam_id64": "76561199004135497", "manual_rating": 60},
    ).json()

    with SessionLocal() as db:
        comm = player_service.get_or_create_default_community(db)

        class _MockSteam:
            async def fetch_bans(self, sids):
                return {
                    sid: ProviderResult(
                        provider="steam_bans",
                        status="OK",
                        summary="No Steam VAC/game ban record found by Steam API at check time.",
                        data={"vac_banned": False, "number_of_game_bans": 0},
                    )
                    for sid in sids
                }

        class _MockCSWatch:
            async def fetch_player(self, sid):
                return ProviderResult(
                    provider="cswatch",
                    status="OK",
                    summary="CSWatch reputation 96/100 (risk: low).",
                    data={"reputation_score": 96, "risk_level": "low", "profile_url": f"https://cswatch.gg/player/{sid}"},
                )

        signals = asyncio.run(
            trust_service.run_trust_check_for_player(
                db, comm.id, p["id"], steam_provider=_MockSteam(), cswatch_provider=_MockCSWatch()
            )
        )
        assert len(signals) == 2
        assert {s["category"] for s in signals} == {"OFFICIAL_ENFORCEMENT", "THIRD_PARTY_REPUTATION"}

    wl = client.post(
        "/api/trust/watchlist",
        json={"community_player_id": p["id"], "reason": "Check recent demo timing"},
    )
    assert wl.status_code == 200
    entry_id = wl.json()["watchlist"][0]["id"]

    rev = client.patch(
        f"/api/trust/watchlist/{entry_id}",
        json={"status": "DISMISSED", "review_note": "Confirmed clean angle hold via teammate callout"},
    )
    assert rev.status_code == 200
    assert rev.json()["watchlist"][0]["status"] == "DISMISSED"
    assert any(s["category"] == "HUMAN_REVIEW" for s in rev.json()["signals"])


def test_auth_signup_login_me_logout_and_leetify_scale(db_and_client):
    _SessionLocal, client = db_and_client

    # Verify both Leetify v3 percentage-point (+2.84) and decimal (+0.04) normalize consistently
    assert 55.0 <= normalize_leetify(2.84) <= 68.0
    assert abs(normalize_leetify(2.84) - normalize_leetify(0.0284)) < 0.01

    su = client.post(
        "/api/auth/signup",
        json={"email": "host@stackforge.gg", "username": "HostAbhi", "password": "StrongPassword123"},
    )
    assert su.status_code == 200
    token = su.json()["token"]

    me_ok = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_ok.status_code == 200
    assert me_ok.json()["authenticated"] is True
    assert me_ok.json()["user"]["username"] == "HostAbhi"

    bad_login = client.post(
        "/api/auth/login",
        json={"email": "host@stackforge.gg", "password": "WrongPassword"},
    )
    assert bad_login.status_code == 401

    lo = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert lo.status_code == 200
    me_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_after.json()["authenticated"] is False
