from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RoleType = Literal["Entry", "Rifler", "AWPer", "Support", "Lurker", "IGL"]
TeamSide = Literal["A", "B"]


class ProviderStatusOut(BaseModel):
    provider: str
    status: str
    summary: str
    fetched_at: datetime | None = None


class AliasOut(BaseModel):
    id: str
    alias_name: str
    previous_name: str | None = None
    source: str
    observed_at: datetime


class StatSnapshotCreate(BaseModel):
    provider: Literal["faceit", "leetify", "community_match", "manual"] = "community_match"
    scope: Literal["recent", "lifetime", "season"] = "recent"
    game_mode: str = Field(default="CS2 5v5", max_length=40)
    season: str | None = Field(default=None, max_length=64)
    sample_size: int | None = Field(default=None, ge=1, le=5000)
    matches_played: int | None = Field(default=None, ge=1, le=5000)
    win_rate: float | None = Field(default=None, ge=0.0, le=100.0)
    kd_ratio: float | None = Field(default=None, ge=0.0, le=10.0)
    adr: float | None = Field(default=None, ge=0.0, le=300.0)
    kast: float | None = Field(default=None, ge=0.0, le=100.0)
    hs_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    opening_duel_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    trade_kills_per_match: float | None = Field(default=None, ge=0.0, le=50.0)
    utility_damage_per_round: float | None = Field(default=None, ge=0.0, le=100.0)
    flash_assists_per_round: float | None = Field(default=None, ge=0.0, le=10.0)
    clutch_win_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    multi_kill_rate: float | None = Field(default=None, ge=0.0, le=100.0)
    consistency_score: float | None = Field(default=None, ge=0.0, le=100.0)


class StatSnapshotOut(BaseModel):
    id: str
    provider: str
    scope: str
    game_mode: str
    season: str | None = None
    sample_size: int | None = None
    raw_rating_label: str | None = None
    raw_rating_value: float | None = None
    matches_played: int | None = None
    win_rate: float | None = None
    kd_ratio: float | None = None
    adr: float | None = None
    kast: float | None = None
    hs_pct: float | None = None
    opening_duel_pct: float | None = None
    trade_kills_per_match: float | None = None
    utility_damage_per_round: float | None = None
    flash_assists_per_round: float | None = None
    clutch_win_pct: float | None = None
    multi_kill_rate: float | None = None
    consistency_score: float | None = None
    aim_rating: float | None = None
    utility_rating: float | None = None
    positioning_rating: float | None = None
    preaim: float | None = None
    reaction_time_ms: float | None = None
    spotted_accuracy: float | None = None
    spray_accuracy: float | None = None
    enemies_flashed_per_round: float | None = None
    traded_deaths_pct: float | None = None
    freshness: str
    is_sample_demo: bool
    captured_at: datetime


class PlayerCardBadgeOut(BaseModel):
    key: str
    label: str
    evidence: str
    hidden: bool


class PlayerCardOut(BaseModel):
    rules_version: str
    humour_enabled: bool
    humour_intensity: str
    primary_title: str
    tagline: str
    evidence_summary: str
    badges: list[PlayerCardBadgeOut]
    eligible_count: int
    discord_card_text: str


class PlayerCardSettingsUpdate(BaseModel):
    humour_enabled: bool | None = None
    humour_intensity: Literal["MILD", "SPICY", "SAVAGE"] | None = None
    hidden_badges: list[str] | None = None
    regenerate_tagline: bool = False
    stats_visibility: Literal["COMMUNITY", "HOST_ONLY"] | None = None
    profile_visibility: Literal["COMMUNITY", "PUBLIC", "PRIVATE"] | None = None


class PlayerCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    steam_id64: str | None = Field(default=None, max_length=32)
    steam_profile_url: str | None = Field(default=None, max_length=500)
    avatar_url: str | None = Field(default=None, max_length=500)
    manual_rating: float = Field(default=50.0, ge=1.0, le=100.0)
    premier_rating: int | None = Field(default=None, ge=0, le=45000)
    premier_source: str | None = Field(default=None, max_length=64)
    premier_season: str | None = Field(default=None, max_length=64)
    faceit_elo: int | None = Field(default=None, ge=100, le=5000)
    leetify_rating: float | None = Field(default=None, ge=-25.0, le=25.0)
    recent_form: float | None = Field(default=None, ge=-1.0, le=1.0)
    primary_role: RoleType | None = None
    secondary_role: RoleType | None = None
    notes: str | None = Field(default=None, max_length=500)


class PlayerUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    steam_id64: str | None = Field(default=None, max_length=32)
    steam_profile_url: str | None = Field(default=None, max_length=500)
    avatar_url: str | None = Field(default=None, max_length=500)
    manual_rating: float | None = Field(default=None, ge=1.0, le=100.0)
    premier_rating: int | None = Field(default=None, ge=0, le=45000)
    premier_source: str | None = Field(default=None, max_length=64)
    premier_season: str | None = Field(default=None, max_length=64)
    faceit_elo: int | None = Field(default=None, ge=100, le=5000)
    leetify_rating: float | None = Field(default=None, ge=-25.0, le=25.0)
    recent_form: float | None = Field(default=None, ge=-1.0, le=1.0)
    primary_role: RoleType | None = None
    secondary_role: RoleType | None = None
    notes: str | None = Field(default=None, max_length=500)
    clear_premier: bool = False
    clear_faceit: bool = False
    clear_leetify: bool = False
    clear_primary_role: bool = False


class ExternalIdentityOut(BaseModel):
    id: str
    provider: str
    external_id: str
    profile_url: str | None = None
    verification_state: str
    confidence: float


class MatchRecordOut(BaseModel):
    id: str
    provider: str
    external_match_id: str
    map_name: str | None = None
    game_mode: str | None = None
    outcome: str | None = None
    score_text: str | None = None
    kd_ratio: float | None = None
    adr: float | None = None
    hs_pct: float | None = None
    leetify_rating: float | None = None
    source_url: str | None = None
    played_at: datetime


class TrustSummaryOut(BaseModel):
    cswatch_status: str | None = None
    cswatch_risk_level: str | None = None
    cswatch_reputation_score: float | None = None
    cswatch_summary: str | None = None
    watchlist_status: str | None = None
    watchlist_reason: str | None = None


class PlayerOut(BaseModel):
    id: str
    player_id: str
    community_id: str
    display_name: str
    steam_id64: str | None
    steam_profile_url: str | None
    vanity_name: str | None = None
    steam_persona_name: str | None
    avatar_url: str | None
    identity_status: str
    last_successful_refresh_at: datetime | None = None
    last_refresh_attempt_at: datetime | None = None
    refresh_status: str = "NEVER_REFRESHED"
    refresh_error: str | None = None
    profile_visibility: str = "COMMUNITY"
    stats_visibility: str = "COMMUNITY"
    manual_rating: float
    premier_rating: int | None
    premier_source: str | None
    premier_season: str | None
    faceit_elo: int | None
    faceit_level: int | None = None
    leetify_rating: float | None
    aim_rating: float | None = None
    utility_rating: float | None = None
    positioning_rating: float | None = None
    recent_form: float | None
    primary_role: str | None
    secondary_role: str | None
    notes: str | None
    is_seeded: bool
    is_archived: bool = False
    stats_stale: bool = False
    data_status: str = "INSUFFICIENT_DATA"  # OK | LOW_CONFIDENCE | INSUFFICIENT_DATA
    normalized_strength: float | None = None
    confidence: float
    strength_band: str
    missing_sources: list[str]
    provider_statuses: list[ProviderStatusOut] = []
    aliases: list[AliasOut] = []
    external_identities: list[ExternalIdentityOut] = []
    latest_stats: StatSnapshotOut | None = None
    trust_summary: TrustSummaryOut | None = None
    card: PlayerCardOut | None = None
    created_at: datetime
    updated_at: datetime


class ProviderRefreshResultOut(BaseModel):
    provider: str
    status: str  # SUCCESS | PARTIAL | PRIVATE | NOT_LINKED | NOT_CONFIGURED | RATE_LIMITED | UNAVAILABLE | FAILED
    summary: str
    cache_hit: bool = False
    fetched_at: datetime | None = None


class PlayerProfileOut(BaseModel):
    player: PlayerOut
    stat_snapshots: list[StatSnapshotOut]
    aliases: list[AliasOut]
    external_identities: list[ExternalIdentityOut] = []
    match_records: list[MatchRecordOut] = []
    provider_statuses: list[ProviderStatusOut]
    card: PlayerCardOut


class RefreshProfileResponse(BaseModel):
    profile: PlayerProfileOut
    status: str = "SUCCESS"
    cache_hit: bool
    alias_changed: bool
    message: str
    provider_results: list[ProviderRefreshResultOut] = []


class PlayerCompareOut(BaseModel):
    player_a: PlayerProfileOut
    player_b: PlayerProfileOut


class BulkImportRequest(BaseModel):
    text: str = Field(..., min_length=1)
    default_manual_rating: float = Field(default=50.0, ge=1.0, le=100.0)
    allow_manual_names: bool = True


class BulkImportEntryResult(BaseModel):
    line: str
    status: Literal["CREATED_STEAM", "CREATED_MANUAL", "DUPLICATE", "UNRESOLVED", "INVALID"]
    message: str
    player: PlayerOut | None = None


class BulkImportResponse(BaseModel):
    created_count: int
    duplicate_count: int
    unresolved_count: int
    invalid_count: int
    entries: list[BulkImportEntryResult]


class MatchRoomCreate(BaseModel):
    title: str = Field(default="Evening 5v5 Stack", min_length=1, max_length=160)


class RoomRosterUpdate(BaseModel):
    community_player_ids: list[str]


class RoomSlotReplace(BaseModel):
    remove_player_id: str
    add_player_id: str


class LockPlayerRequest(BaseModel):
    locked_team: TeamSide | None = None


class PairConstraintCreate(BaseModel):
    constraint_type: Literal["TOGETHER", "OPPONENT"]
    player_a_id: str
    player_b_id: str


class PairConstraintOut(BaseModel):
    id: str
    constraint_type: str
    player_a_id: str
    player_b_id: str


class RoomPlayerOut(BaseModel):
    slot_order: int
    locked_team: str | None
    player: PlayerOut


class FeedbackCreate(BaseModel):
    community_player_id: str | None = None
    target_player_id: str | None = None
    feedback_type: Literal["OBJECTION", "SWAP_REQUEST", "REMAKE_REQUEST"]
    reason: str = Field(..., min_length=2, max_length=500)


class FeedbackResolve(BaseModel):
    status: Literal["APPROVED", "REJECTED"]
    host_note: str | None = Field(default=None, max_length=300)


class FeedbackOut(BaseModel):
    id: str
    generation_id: str
    community_player_id: str | None
    target_player_id: str | None
    feedback_type: str
    reason: str
    status: str
    host_note: str | None
    created_at: datetime
    resolved_at: datetime | None


class ProposalAlternativeOut(BaseModel):
    partition_key: str
    team_a_ids: list[str]
    team_b_ids: list[str]
    team_a_strength: float
    team_b_strength: float
    strength_diff: float
    objective_score: float
    role_summary: dict[str, Any]


class ProposalOut(BaseModel):
    id: str
    room_id: str
    proposal_number: int
    parent_generation_id: str | None
    action_type: str
    algorithm_version: str
    normalizer_version: str
    map_pool_version: str
    seed: int
    partition_key: str
    team_a_ids: list[str]
    team_b_ids: list[str]
    team_a_strength: float
    team_b_strength: float
    strength_diff: float
    objective_score: float
    objective_components: dict[str, Any]
    explanation: dict[str, Any]
    alternatives: list[ProposalAlternativeOut]
    input_snapshot: list[dict[str, Any]]
    constraints_snapshot: dict[str, Any]
    feedback: list[FeedbackOut] = []
    created_at: datetime


class AdoptAlternativeRequest(BaseModel):
    partition_key: str


class GenerateRequest(BaseModel):
    seed: int = 42
    force_cycle: bool = False


class SwapPreviewRequest(BaseModel):
    generation_id: str
    player_a_id: str
    player_b_id: str


class SwapPreviewResponse(BaseModel):
    before_team_a_strength: float
    before_team_b_strength: float
    before_strength_diff: float
    before_objective: float
    after_team_a_strength: float
    after_team_b_strength: float
    after_strength_diff: float
    after_objective: float
    strength_diff_delta: float
    objective_delta: float
    after_team_a_ids: list[str]
    after_team_b_ids: list[str]


class SwapCommitRequest(BaseModel):
    generation_id: str
    player_a_id: str
    player_b_id: str
    reason: str | None = None


class FinalizeRequest(BaseModel):
    generation_id: str
    finalized_by: str = Field(default="Host", min_length=1, max_length=100)


class FinalizedLineupOut(BaseModel):
    id: str
    room_id: str
    generation_id: str
    proposal_number: int
    share_slug: str
    team_a: list[dict[str, Any]]
    team_b: list[dict[str, Any]]
    team_a_strength: float
    team_b_strength: float
    strength_diff: float
    discord_text: str
    finalized_by: str
    finalized_at: datetime


class MatchRoomOut(BaseModel):
    id: str
    community_id: str
    title: str
    status: str
    version: int
    share_slug: str
    finalized_proposal_id: str | None
    selected_count: int
    roster: list[RoomPlayerOut]
    constraints: list[PairConstraintOut]
    proposals: list[ProposalOut]
    finalized_lineup: FinalizedLineupOut | None = None
    created_at: datetime
    updated_at: datetime
