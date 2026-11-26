from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class Community(Base):
    __tablename__ = "communities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    members: Mapped[list["CommunityPlayer"]] = relationship(back_populates="community")
    rooms: Mapped[list["MatchRoom"]] = relationship(back_populates="community")


class Player(Base):
    """Global player identity canonically keyed by SteamID64 string when linked."""

    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    steam_id64: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)
    steam_profile_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vanity_name: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    steam_persona_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    identity_status: Mapped[str] = mapped_column(String(32), default="MANUAL_ONLY", nullable=False)

    last_successful_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_refresh_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_status: Mapped[str] = mapped_column(String(32), default="NEVER_REFRESHED", nullable=False)
    refresh_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_visibility: Mapped[str] = mapped_column(String(32), default="COMMUNITY", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    community_profiles: Mapped[list["CommunityPlayer"]] = relationship(back_populates="player")
    provider_snapshots: Mapped[list["ProviderSnapshot"]] = relationship(back_populates="player")
    aliases: Mapped[list["PlayerAlias"]] = relationship(
        back_populates="player", cascade="all, delete-orphan", order_by="PlayerAlias.observed_at.desc()"
    )
    stat_snapshots: Mapped[list["PlayerStatSnapshot"]] = relationship(
        back_populates="player", cascade="all, delete-orphan", order_by="PlayerStatSnapshot.captured_at.desc()"
    )
    external_identities: Mapped[list["PlayerExternalIdentity"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
    match_records: Mapped[list["PlayerMatchRecord"]] = relationship(
        back_populates="player", cascade="all, delete-orphan", order_by="PlayerMatchRecord.played_at.desc()"
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(24), default="HOST", nullable=False)
    linked_steam_id64: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship()


class PlayerExternalIdentity(Base):
    """Canonical mapping between a global Player and external CS2 provider IDs."""

    __tablename__ = "player_external_identities"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_provider_external_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # steam | faceit | leetify | csstats | cswatch
    external_id: Mapped[str] = mapped_column(String(160), nullable=False)
    profile_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verification_state: Mapped[str] = mapped_column(String(24), default="VERIFIED", nullable=False)  # VERIFIED | CANDIDATE | UNRESOLVED
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    player: Mapped["Player"] = relationship(back_populates="external_identities")


class PlayerMatchRecord(Base):
    """Deduplicated external or private 5v5 match history for trend and form tracking."""

    __tablename__ = "player_match_records"
    __table_args__ = (
        UniqueConstraint("player_id", "provider", "external_match_id", name="uq_player_provider_match"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_match_id: Mapped[str] = mapped_column(String(120), nullable=False)
    map_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    game_mode: Mapped[str | None] = mapped_column(String(48), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(24), nullable=True)  # win | loss | tie
    score_text: Mapped[str | None] = mapped_column(String(32), nullable=True)
    kd_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    adr: Mapped[float | None] = mapped_column(Float, nullable=True)
    hs_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    leetify_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    player: Mapped["Player"] = relationship(back_populates="match_records")


class SpreadsheetImport(Base):
    __tablename__ = "spreadsheet_imports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    community_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)  # GOOGLE_SHEET | CSV | XLSX
    source_label: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    mapping_json: Mapped[str] = mapped_column(Text, nullable=False)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False)
    sync_status: Mapped[str] = mapped_column(String(24), default="OK", nullable=False)
    last_attempted_sync_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    rows: Mapped[list["SpreadsheetImportRow"]] = relationship(
        back_populates="import_job", cascade="all, delete-orphan"
    )


class SpreadsheetImportRow(Base):
    __tablename__ = "spreadsheet_import_rows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    import_id: Mapped[str] = mapped_column(ForeignKey("spreadsheet_imports.id", ondelete="CASCADE"), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # CREATED | UPDATED | MATCHED | DUPLICATE | UNRESOLVED | INVALID
    matched_community_player_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    extracted_steam_id64: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str] = mapped_column(String(300), nullable=False)

    import_job: Mapped["SpreadsheetImport"] = relationship(back_populates="rows")


class WatchlistEntry(Base):
    __tablename__ = "watchlist_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    community_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), default="WATCHING", nullable=False)  # WATCHING | REVIEWED | DISMISSED
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    player: Mapped["Player"] = relationship()


class TrustSignal(Base):
    """Separated evidence records: official enforcement, 3rd-party reputation, community report, human review."""

    __tablename__ = "trust_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    community_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)  # OFFICIAL_ENFORCEMENT | THIRD_PARTY_REPUTATION | BEHAVIORAL_ANOMALY | COMMUNITY_REPORT | HUMAN_REVIEW
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # OK | FLAGGED | UNAVAILABLE | PENDING_REVIEW | DISMISSED
    summary: Mapped[str] = mapped_column(String(400), nullable=False)
    limitations: Mapped[str | None] = mapped_column(String(400), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    community_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    player_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    dedup_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class PlayerAlias(Base):
    """Append-only historical display-name / alias observations for a canonical player."""

    __tablename__ = "player_aliases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    alias_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    previous_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="steam_web_api", nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    player: Mapped["Player"] = relationship(back_populates="aliases")


class PlayerStatSnapshot(Base):
    """Source-qualified, timestamped competitive & combat metrics (never zero-filled)."""

    __tablename__ = "player_stat_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # faceit | leetify | community_match | manual
    scope: Mapped[str] = mapped_column(String(24), default="recent", nullable=False)  # recent | lifetime | season
    game_mode: Mapped[str] = mapped_column(String(40), default="CS2 5v5", nullable=False)
    season: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    raw_rating_label: Mapped[str | None] = mapped_column(String(48), nullable=True)
    raw_rating_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    matches_played: Mapped[int | None] = mapped_column(Integer, nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100 %
    kd_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    adr: Mapped[float | None] = mapped_column(Float, nullable=True)
    kast: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100 %
    hs_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100 %
    opening_duel_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100 %
    entry_attempts_per_match: Mapped[float | None] = mapped_column(Float, nullable=True)
    trade_kills_per_match: Mapped[float | None] = mapped_column(Float, nullable=True)
    utility_damage_per_round: Mapped[float | None] = mapped_column(Float, nullable=True)
    flash_assists_per_round: Mapped[float | None] = mapped_column(Float, nullable=True)
    clutch_win_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100 %
    multi_kill_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    aim_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    utility_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    positioning_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    preaim: Mapped[float | None] = mapped_column(Float, nullable=True)
    reaction_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    spotted_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    spray_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    enemies_flashed_per_round: Mapped[float | None] = mapped_column(Float, nullable=True)
    traded_deaths_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    freshness: Mapped[str] = mapped_column(String(24), default="FRESH", nullable=False)
    is_sample_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    player: Mapped["Player"] = relationship(back_populates="stat_snapshots")


class CommunityPlayer(Base):
    """Community-scoped player profile, nickname, roles, ratings, and card preferences."""

    __tablename__ = "community_players"
    __table_args__ = (
        UniqueConstraint("community_id", "player_id", name="uq_community_player"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    community_id: Mapped[str] = mapped_column(ForeignKey("communities.id", ondelete="CASCADE"), nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)

    display_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    manual_rating: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)

    # Source-qualified optional metrics (missing = None, never 0)
    premier_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    premier_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    premier_season: Mapped[str | None] = mapped_column(String(64), nullable=True)
    faceit_elo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    faceit_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leetify_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    aim_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    utility_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    positioning_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    recent_form: Mapped[float | None] = mapped_column(Float, nullable=True)  # -1.0 to +1.0

    primary_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    secondary_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    map_ratings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_seeded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Player Card & Humour Controls
    humour_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    humour_intensity: Mapped[str] = mapped_column(String(16), default="SPICY", nullable=False)
    hidden_badges_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    card_tagline_variant: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stats_visibility: Mapped[str] = mapped_column(String(24), default="COMMUNITY", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    community: Mapped["Community"] = relationship(back_populates="members")
    player: Mapped["Player"] = relationship(back_populates="community_profiles")


class ProviderSnapshot(Base):
    """Append-only provider observations (Steam profile/bans, FACEIT, Leetify, CSWatch)."""

    __tablename__ = "provider_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    endpoint_category: Mapped[str | None] = mapped_column(String(48), nullable=True)
    player_identity: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summary_text: Mapped[str] = mapped_column(String(255), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    retry_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data_freshness: Mapped[str | None] = mapped_column(String(24), nullable=True)
    last_successful_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    player: Mapped["Player"] = relationship(back_populates="provider_snapshots")


class MatchRoom(Base):
    __tablename__ = "match_rooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    community_id: Mapped[str] = mapped_column(ForeignKey("communities.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    finalized_proposal_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    share_slug: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    community: Mapped["Community"] = relationship(back_populates="rooms")
    roster_entries: Mapped[list["MatchRoomPlayer"]] = relationship(
        back_populates="room", cascade="all, delete-orphan", order_by="MatchRoomPlayer.slot_order"
    )
    constraints: Mapped[list["TeamConstraint"]] = relationship(
        back_populates="room", cascade="all, delete-orphan"
    )
    proposals: Mapped[list["TeamGeneration"]] = relationship(
        back_populates="room", cascade="all, delete-orphan", order_by="TeamGeneration.proposal_number"
    )


class MatchRoomPlayer(Base):
    __tablename__ = "match_room_players"
    __table_args__ = (
        UniqueConstraint("room_id", "community_player_id", name="uq_room_community_player"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("match_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    community_player_id: Mapped[str] = mapped_column(
        ForeignKey("community_players.id", ondelete="CASCADE"), nullable=False
    )
    slot_order: Mapped[int] = mapped_column(Integer, nullable=False)
    locked_team: Mapped[str | None] = mapped_column(String(1), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    room: Mapped["MatchRoom"] = relationship(back_populates="roster_entries")
    community_player: Mapped["CommunityPlayer"] = relationship()


class TeamConstraint(Base):
    __tablename__ = "team_constraints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("match_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    constraint_type: Mapped[str] = mapped_column(String(24), nullable=False)
    player_a_id: Mapped[str] = mapped_column(String(36), nullable=False)
    player_b_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    room: Mapped["MatchRoom"] = relationship(back_populates="constraints")


class TeamGeneration(Base):
    __tablename__ = "team_generations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("match_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    proposal_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_generation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action_type: Mapped[str] = mapped_column(String(24), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)
    normalizer_version: Mapped[str] = mapped_column(String(40), nullable=False)
    map_pool_version: Mapped[str] = mapped_column(String(40), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)

    partition_key: Mapped[str] = mapped_column(String(400), nullable=False)
    team_a_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    team_b_ids_json: Mapped[str] = mapped_column(Text, nullable=False)

    team_a_strength: Mapped[float] = mapped_column(Float, nullable=False)
    team_b_strength: Mapped[float] = mapped_column(Float, nullable=False)
    strength_diff: Mapped[float] = mapped_column(Float, nullable=False)
    objective_score: Mapped[float] = mapped_column(Float, nullable=False)

    input_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    constraints_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    objective_components_json: Mapped[str] = mapped_column(Text, nullable=False)
    explanation_json: Mapped[str] = mapped_column(Text, nullable=False)
    alternatives_json: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    room: Mapped["MatchRoom"] = relationship(back_populates="proposals")
    feedback_items: Mapped[list["GenerationFeedback"]] = relationship(
        back_populates="generation", cascade="all, delete-orphan", order_by="GenerationFeedback.created_at"
    )


class GenerationFeedback(Base):
    __tablename__ = "generation_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("match_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    generation_id: Mapped[str] = mapped_column(
        ForeignKey("team_generations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    community_player_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    target_player_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    feedback_type: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False)
    host_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    generation: Mapped["TeamGeneration"] = relationship(back_populates="feedback_items")


class FinalizedLineup(Base):
    __tablename__ = "finalized_lineups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("match_rooms.id", ondelete="CASCADE"), nullable=False, unique=True)
    generation_id: Mapped[str] = mapped_column(ForeignKey("team_generations.id", ondelete="CASCADE"), nullable=False)
    share_slug: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    lineup_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    discord_text: Mapped[str] = mapped_column(Text, nullable=False)
    finalized_by: Mapped[str] = mapped_column(String(120), default="Host", nullable=False)
    finalized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MatchResult(Base):
    """Post-match outcome preserving finalized teams & random map played (separate from Valve/FACEIT ladder ranks)."""

    __tablename__ = "match_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("match_rooms.id", ondelete="CASCADE"), nullable=False, unique=True)
    community_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    generation_id: Mapped[str] = mapped_column(ForeignKey("team_generations.id", ondelete="CASCADE"), nullable=False)
    share_slug: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    map_played: Mapped[str] = mapped_column(String(40), nullable=False)  # random map drawn during match
    team_a_score: Mapped[int] = mapped_column(Integer, nullable=False)
    team_b_score: Mapped[int] = mapped_column(Integer, nullable=False)
    winner_side: Mapped[str] = mapped_column(String(8), nullable=False)  # A | B | TIE
    external_match_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    demo_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result_source: Mapped[str] = mapped_column(String(32), default="manual_host", nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), default="CONFIRMED", nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    normalizer_version: Mapped[str] = mapped_column(String(40), nullable=False)
    lineup_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(120), default="Host", nullable=False)
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    community_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    room_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), default="Host", nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
