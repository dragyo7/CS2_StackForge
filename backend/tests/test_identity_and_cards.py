from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.migrations import run_migrations
from app.providers.base import ProviderResult
from app.services import player_service
from app.services.humour_engine import CardMetricContext, generate_player_card
from app.services.player_service import get_or_create_default_community, refresh_player_profile


class _FakeSteamProvider:
    def __init__(self, persona_name: str | None = None, fail: bool = False):
        self.persona_name = persona_name
        self.fail = fail
        self.calls = 0

    @property
    def is_configured(self) -> bool:
        return True

    async def resolve_vanity_url(self, vanity_name: str):
        return None, "NOT_FOUND"

    async def fetch_summaries(self, steam_ids: list[str]):
        self.calls += 1
        if self.fail:
            return {
                sid: ProviderResult(
                    provider="steam_profile",
                    status="UNAVAILABLE",
                    summary="Simulated Steam outage.",
                )
                for sid in steam_ids
            }
        return {
            sid: ProviderResult(
                provider="steam_profile",
                status="OK",
                summary=f"{self.persona_name} (Public profile)",
                data={
                    "persona_name": self.persona_name,
                    "avatar_url": "https://example.com/avatar.png",
                    "profile_url": f"https://steamcommunity.com/profiles/{sid}",
                },
            )
            for sid in steam_ids
        }

    async def fetch_bans(self, steam_ids: list[str]):
        return {
            sid: ProviderResult(
                provider="steam_bans",
                status="OK",
                summary="No Steam VAC/game ban record found by Steam API at check time.",
                data={"number_of_vac_bans": 0, "number_of_game_bans": 0},
            )
            for sid in steam_ids
        }


class _NoopProvider:
    async def fetch_by_steam_id64(self, steam_id64: str | None):
        return ProviderResult(provider="stub", status="NOT_CONFIGURED", summary="Not configured")


def _make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    run_migrations(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return engine, SessionLocal


def test_steam_username_change_tracks_alias_and_searchable():
    _engine, SessionLocal = _make_session()
    with SessionLocal() as db:
        comm = get_or_create_default_community(db)
        created = player_service.create_player(
            db,
            comm.id,
            player_service.PlayerCreate(
                display_name="Abhi",
                steam_id64="76561198012345678",
                manual_rating=70,
            ),
        )

        # First Steam refresh observes "clutch_or_kick"
        s1 = _FakeSteamProvider(persona_name="clutch_or_kick")
        r1 = asyncio.run(
            refresh_player_profile(
                db, comm.id, created.id, force=True, steam_provider=s1, faceit_provider=_NoopProvider(), leetify_provider=_NoopProvider()
            )
        )
        assert r1.profile.player.steam_persona_name == "clutch_or_kick"
        assert len(r1.profile.aliases) == 1

        # Second refresh within TTL returns cached result without calling Steam again
        r_cached = asyncio.run(
            refresh_player_profile(
                db, comm.id, created.id, force=False, steam_provider=s1, faceit_provider=_NoopProvider(), leetify_provider=_NoopProvider()
            )
        )
        assert r_cached.cache_hit is True
        assert s1.calls == 1

        # Player changes Steam username to "eco_round_terrorist" -> forced refresh
        s2 = _FakeSteamProvider(persona_name="eco_round_terrorist")
        r2 = asyncio.run(
            refresh_player_profile(
                db, comm.id, created.id, force=True, steam_provider=s2, faceit_provider=_NoopProvider(), leetify_provider=_NoopProvider()
            )
        )
        assert r2.alias_changed is True
        assert r2.profile.player.id == created.id
        assert r2.profile.player.steam_id64 == "76561198012345678"
        assert r2.profile.player.steam_persona_name == "eco_round_terrorist"
        assert len(r2.profile.aliases) == 2
        assert r2.profile.aliases[0].previous_name == "clutch_or_kick"

        # Searching by previous username locates the SAME player
        found = player_service.list_players(db, comm.id, query="clutch_or_kick")
        assert len(found) == 1
        assert found[0].id == created.id

        # Outage during subsequent refresh retains last valid persona & avatar!
        s_fail = _FakeSteamProvider(fail=True)
        r_fail = asyncio.run(
            refresh_player_profile(
                db, comm.id, created.id, force=True, steam_provider=s_fail, faceit_provider=_NoopProvider(), leetify_provider=_NoopProvider()
            )
        )
        assert r_fail.profile.player.refresh_status == "UNAVAILABLE"
        assert r_fail.profile.player.steam_persona_name == "eco_round_terrorist"
        assert r_fail.profile.player.avatar_url == "https://example.com/avatar.png"


def test_identical_display_names_different_steam_ids_stay_separate():
    _engine, SessionLocal = _make_session()
    with SessionLocal() as db:
        comm = get_or_create_default_community(db)
        p1 = player_service.create_player(
            db,
            comm.id,
            player_service.PlayerCreate(display_name="Sniper", steam_id64="76561198000000101", manual_rating=65),
        )
        p2 = player_service.create_player(
            db,
            comm.id,
            player_service.PlayerCreate(display_name="Sniper", steam_id64="76561198000000102", manual_rating=75),
        )
        assert p1.id != p2.id
        assert p1.player_id != p2.player_id


def test_humour_engine_evidence_and_missing_stats_safety():
    # Missing stats -> never assigns negative title!
    no_stats_ctx = CardMetricContext(
        display_name="NewPlayer",
        primary_role="Rifler",
        normalized_strength=50.0,
        strength_band="Solid",
        sample_size=0,
        provider_label=None,
    )
    card_missing = generate_player_card(no_stats_ctx)
    assert card_missing["primary_title"] == "Uncharted Operative"
    assert "Professional Spectator" not in card_missing["primary_title"]
    assert card_missing["eligible_count"] == 0

    # Utility & Flash evidence across >=5 matches -> deterministic title + tagline variants
    util_ctx = CardMetricContext(
        display_name="NadeKing",
        primary_role="Support",
        normalized_strength=70.0,
        strength_band="High",
        sample_size=12,
        provider_label="leetify",
        utility_damage_per_round=22.4,
        flash_assists_per_round=0.31,
        adr=74.0,
    )
    c_v0 = generate_player_card(util_ctx, humour_intensity="SPICY", variant=0, hidden_badges=["flashbang_dept"])
    c_v1 = generate_player_card(util_ctx, humour_intensity="SPICY", variant=1, hidden_badges=["flashbang_dept"])
    assert c_v0["primary_title"] == "Utility Damage Investor"
    assert c_v0["tagline"] != c_v1["tagline"]
    assert any(b["key"] == "flashbang_dept" and b["hidden"] is True for b in c_v0["badges"])


def test_migrations_backwards_compatible_on_legacy_schema():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE communities (id VARCHAR(36) PRIMARY KEY, name VARCHAR(120), slug VARCHAR(120), created_at DATETIME)"))
        conn.execute(text("CREATE TABLE players (id VARCHAR(36) PRIMARY KEY, steam_id64 VARCHAR(32), steam_profile_url VARCHAR(500), steam_persona_name VARCHAR(120), avatar_url VARCHAR(500), identity_status VARCHAR(32), created_at DATETIME, updated_at DATETIME)"))
        conn.execute(text("CREATE TABLE community_players (id VARCHAR(36) PRIMARY KEY, community_id VARCHAR(36), player_id VARCHAR(36), display_name VARCHAR(120), manual_rating FLOAT, premier_rating INTEGER, premier_source VARCHAR(64), premier_season VARCHAR(64), faceit_elo INTEGER, leetify_rating FLOAT, recent_form FLOAT, primary_role VARCHAR(32), secondary_role VARCHAR(32), map_ratings_json TEXT, notes TEXT, is_seeded BOOLEAN, is_active BOOLEAN, created_at DATETIME, updated_at DATETIME)"))
        conn.execute(text("INSERT INTO players (id, steam_id64, identity_status) VALUES ('legacy-p1', '76561198099999999', 'STEAM_PARSED')"))

    run_migrations(engine)
    with engine.begin() as conn:
        row = conn.execute(text("SELECT id, steam_id64, refresh_status, profile_visibility FROM players WHERE id='legacy-p1'")).fetchone()
        assert row is not None
        assert row[1] == "76561198099999999"
        assert row[2] == "NEVER_REFRESHED"
        assert row[3] == "COMMUNITY"


def test_profile_stats_compare_and_card_endpoints():
    _engine, SessionLocal = _make_session()
    with SessionLocal() as db:
        get_or_create_default_community(db)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        p1 = client.post("/api/players", json={"display_name": "Alpha", "steam_id64": "76561198000000011", "manual_rating": 80, "primary_role": "AWPer"}).json()
        p2 = client.post("/api/players", json={"display_name": "Bravo", "steam_id64": "76561198000000012", "manual_rating": 65, "primary_role": "Support"}).json()

        # Add source-qualified combat stats
        st = client.post(
            f"/api/players/{p1['id']}/stats",
            json={
                "provider": "community_match",
                "scope": "recent",
                "sample_size": 10,
                "matches_played": 10,
                "win_rate": 60.0,
                "kd_ratio": 1.35,
                "adr": 92.0,
                "clutch_win_pct": 33.0,
            },
        )
        assert st.status_code == 201
        prof = st.json()
        assert prof["stat_snapshots"][0]["adr"] == 92.0
        assert prof["card"]["primary_title"] == "The Clutch Department"

        # Update card settings (regenerate tagline + hide badge + change intensity)
        upd = client.patch(
            f"/api/players/{p1['id']}/card-settings",
            json={"humour_intensity": "SAVAGE", "regenerate_tagline": True, "hidden_badges": ["damage_distributor"]},
        )
        assert upd.status_code == 200
        assert upd.json()["card"]["humour_intensity"] == "SAVAGE"

        # Compare endpoint
        cmp_res = client.get(f"/api/players/compare?a={p1['id']}&b={p2['id']}")
        assert cmp_res.status_code == 200
        assert cmp_res.json()["player_a"]["player"]["id"] == p1["id"]
        assert cmp_res.json()["player_b"]["player"]["id"] == p2["id"]
    app.dependency_overrides.clear()
