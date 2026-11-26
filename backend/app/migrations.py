from __future__ import annotations

from sqlalchemy import Engine, text

from app.database import Base


def _existing_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def _add_column_if_missing(conn, table: str, column: str, ddl_type: str) -> None:
    cols = _existing_columns(conn, table)
    if cols and column not in cols:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


def run_migrations(engine: Engine) -> None:
    """
    Idempotent, backwards-compatible SQLite schema migration runner.
    Creates missing tables and safely appends new nullable/defaulted columns
    without dropping or modifying existing player, room, or proposal data.
    """
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        # Player identity & refresh tracking columns
        _add_column_if_missing(conn, "players", "vanity_name", "VARCHAR(120)")
        _add_column_if_missing(conn, "players", "last_successful_refresh_at", "DATETIME")
        _add_column_if_missing(conn, "players", "last_refresh_attempt_at", "DATETIME")
        _add_column_if_missing(conn, "players", "refresh_status", "VARCHAR(32) NOT NULL DEFAULT 'NEVER_REFRESHED'")
        _add_column_if_missing(conn, "players", "refresh_error", "VARCHAR(255)")
        _add_column_if_missing(conn, "players", "profile_visibility", "VARCHAR(32) NOT NULL DEFAULT 'COMMUNITY'")

        # CommunityPlayer humour & privacy settings
        _add_column_if_missing(conn, "community_players", "humour_enabled", "BOOLEAN NOT NULL DEFAULT 1")
        _add_column_if_missing(conn, "community_players", "humour_intensity", "VARCHAR(16) NOT NULL DEFAULT 'SPICY'")
        _add_column_if_missing(conn, "community_players", "hidden_badges_json", "TEXT")
        _add_column_if_missing(conn, "community_players", "card_tagline_variant", "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "community_players", "stats_visibility", "VARCHAR(24) NOT NULL DEFAULT 'COMMUNITY'")
        _add_column_if_missing(conn, "community_players", "is_archived", "BOOLEAN NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "community_players", "faceit_level", "INTEGER")
        _add_column_if_missing(conn, "community_players", "aim_rating", "FLOAT")
        _add_column_if_missing(conn, "community_players", "utility_rating", "FLOAT")
        _add_column_if_missing(conn, "community_players", "positioning_rating", "FLOAT")

        # PlayerStatSnapshot extended CS2 mechanical & utility columns
        for col_name in (
            "aim_rating",
            "utility_rating",
            "positioning_rating",
            "preaim",
            "reaction_time_ms",
            "spotted_accuracy",
            "spray_accuracy",
            "enemies_flashed_per_round",
            "traded_deaths_pct",
        ):
            _add_column_if_missing(conn, "player_stat_snapshots", col_name, "FLOAT")

        # ProviderSnapshot telemetry & lineage columns
        _add_column_if_missing(conn, "provider_snapshots", "endpoint_category", "VARCHAR(48)")
        _add_column_if_missing(conn, "provider_snapshots", "player_identity", "VARCHAR(120)")
        _add_column_if_missing(conn, "provider_snapshots", "normalized_status", "VARCHAR(32)")
        _add_column_if_missing(conn, "provider_snapshots", "failure_reason", "VARCHAR(300)")
        _add_column_if_missing(conn, "provider_snapshots", "retry_eligible", "BOOLEAN NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "provider_snapshots", "data_freshness", "VARCHAR(24)")
        _add_column_if_missing(conn, "provider_snapshots", "last_successful_at", "DATETIME")
