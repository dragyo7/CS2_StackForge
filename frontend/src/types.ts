export type RoleType = 'Entry' | 'Rifler' | 'AWPer' | 'Support' | 'Lurker' | 'IGL';

export const ROLES: RoleType[] = ['Entry', 'Rifler', 'AWPer', 'Support', 'Lurker', 'IGL'];

export type HumourIntensity = 'MILD' | 'SPICY' | 'SAVAGE';

export interface ProviderStatus {
  provider: string;
  status: string;
  summary: string;
  fetched_at: string | null;
}

export interface ExternalIdentity {
  id: string;
  provider: string;
  external_id: string;
  profile_url: string | null;
  verification_state: string;
  confidence: number;
}

export interface MatchRecord {
  id: string;
  provider: string;
  external_match_id: string;
  map_name: string | null;
  game_mode: string | null;
  outcome: string | null;
  score_text: string | null;
  kd_ratio: number | null;
  adr: number | null;
  hs_pct: number | null;
  leetify_rating: number | null;
  source_url: string | null;
  played_at: string;
}

export interface AuthState {
  authenticated: boolean;
  mode: string;
  user: {
    id: string;
    email: string;
    username: string;
    role: string;
    linked_steam_id64: string | null;
  } | null;
}

export interface ResolveIdentityResponse {
  raw_input: string;
  identifier_type: string;
  confidence_state: 'VERIFIED' | 'CANDIDATE' | 'UNRESOLVED';
  resolved_steam_id64: string | null;
  message: string;
  matched_existing: {
    community_player_id: string;
    display_name: string;
    steam_id64: string | null;
    match_reason: string;
    confidence_state: string;
  }[];
  provider_discoveries: {
    provider: string;
    status: string;
    summary: string;
    external_id: string | null;
    profile_url: string | null;
    persona_name?: string | null;
    avatar_url?: string | null;
    premier_rating?: number | null;
    leetify_rating?: number | null;
    faceit_elo?: number | null;
    reputation_score?: number | null;
    risk_level?: string | null;
  }[];
}

export interface SpreadsheetPreview {
  headers: string[];
  mapping: Record<string, string | null>;
  content_hash: string;
  total_rows: number;
  counts: Record<string, number>;
  source_url?: string;
  rows: {
    row_number: number;
    raw: Record<string, string>;
    normalized: {
      display_name: string;
      real_name: string;
      steam_id64: string | null;
      source_provider: string | null;
      source_url: string | null;
      manual_rating: number;
      primary_role: string | null;
      notes: string | null;
    };
    status: string;
    message: string;
    matched_community_player_id: string | null;
    matched_display_name: string | null;
  }[];
}

export interface ImportHistoryItem {
  id: string;
  source_type: string;
  source_label: string;
  source_url: string | null;
  content_hash: string;
  summary: Record<string, number>;
  sync_status: string;
  last_attempted_sync_at: string;
  last_successful_sync_at: string | null;
}

export interface TrustOverview {
  watchlist: {
    id: string;
    player_id: string;
    community_player_id: string | null;
    display_name: string;
    steam_id64: string | null;
    status: string;
    reason: string;
    source_url: string | null;
    review_note: string | null;
    reviewed_by: string | null;
    created_at: string;
    updated_at: string;
  }[];
  signals: {
    id: string;
    player_id: string;
    community_player_id: string | null;
    display_name: string;
    category: string;
    provider: string;
    status: string;
    summary: string;
    limitations: string | null;
    source_url: string | null;
    observed_at: string;
  }[];
  activity: {
    id: string;
    event_type: string;
    player_id: string | null;
    title: string;
    detail: string;
    created_at: string;
  }[];
}

export interface AliasItem {
  id: string;
  alias_name: string;
  previous_name: string | null;
  source: string;
  observed_at: string;
}

export interface StatSnapshot {
  id: string;
  provider: string;
  scope: string;
  game_mode: string;
  season: string | null;
  sample_size: number | null;
  raw_rating_label: string | null;
  raw_rating_value: number | null;
  matches_played: number | null;
  win_rate: number | null;
  kd_ratio: number | null;
  adr: number | null;
  kast: number | null;
  hs_pct: number | null;
  opening_duel_pct: number | null;
  trade_kills_per_match: number | null;
  utility_damage_per_round: number | null;
  flash_assists_per_round: number | null;
  clutch_win_pct: number | null;
  multi_kill_rate: number | null;
  consistency_score: number | null;
  aim_rating?: number | null;
  utility_rating?: number | null;
  positioning_rating?: number | null;
  preaim?: number | null;
  reaction_time_ms?: number | null;
  spotted_accuracy?: number | null;
  spray_accuracy?: number | null;
  enemies_flashed_per_round?: number | null;
  traded_deaths_pct?: number | null;
  freshness: string;
  is_sample_demo: boolean;
  captured_at: string;
}

export interface PlayerCardBadge {
  key: string;
  label: string;
  evidence: string;
  hidden: boolean;
}

export interface TrustSummary {
  cswatch_status: string | null;
  cswatch_risk_level: string | null;
  cswatch_reputation_score: number | null;
  cswatch_summary: string | null;
  watchlist_status: string | null;
  watchlist_reason: string | null;
}

export interface PlayerCard {
  rules_version: string;
  humour_enabled: boolean;
  humour_intensity: HumourIntensity;
  primary_title: string;
  tagline: string;
  evidence_summary: string;
  badges: PlayerCardBadge[];
  eligible_count: number;
  discord_card_text: string;
}

export interface Player {
  id: string;
  player_id: string;
  community_id: string;
  display_name: string;
  steam_id64: string | null;
  steam_profile_url: string | null;
  vanity_name: string | null;
  steam_persona_name: string | null;
  avatar_url: string | null;
  identity_status: string;
  last_successful_refresh_at: string | null;
  last_refresh_attempt_at: string | null;
  refresh_status: string;
  refresh_error: string | null;
  profile_visibility: string;
  stats_visibility: string;
  manual_rating?: number | null;
  premier_rating: number | null;
  premier_source: string | null;
  premier_season: string | null;
  faceit_elo: number | null;
  faceit_level?: number | null;
  leetify_rating: number | null;
  aim_rating?: number | null;
  utility_rating?: number | null;
  positioning_rating?: number | null;
  recent_form: number | null;
  primary_role: RoleType | null;
  secondary_role: RoleType | null;
  notes: string | null;
  is_seeded: boolean;
  is_archived?: boolean;
  stats_stale?: boolean;
  data_status?: string;
  normalized_strength: number | null;
  confidence: number;
  strength_band: string;
  missing_sources: string[];
  provider_statuses: ProviderStatus[];
  aliases: AliasItem[];
  external_identities: ExternalIdentity[];
  latest_stats: StatSnapshot | null;
  trust_summary?: TrustSummary | null;
  card: PlayerCard | null;
  created_at: string;
  updated_at: string;
}

export interface ProviderRefreshResult {
  provider: string;
  status: string;
  summary: string;
  cache_hit: boolean;
  fetched_at: string | null;
}

export interface PlayerProfile {
  player: Player;
  stat_snapshots: StatSnapshot[];
  aliases: AliasItem[];
  external_identities: ExternalIdentity[];
  match_records: MatchRecord[];
  provider_statuses: ProviderStatus[];
  card: PlayerCard;
}

export interface RefreshProfileResponse {
  profile: PlayerProfile;
  status?: string;
  cache_hit: boolean;
  alias_changed: boolean;
  message: string;
  provider_results?: ProviderRefreshResult[];
}

export interface PlayerCompare {
  player_a: PlayerProfile;
  player_b: PlayerProfile;
}

export interface BulkImportEntry {
  line: string;
  status: 'CREATED_STEAM' | 'CREATED_MANUAL' | 'DUPLICATE' | 'UNRESOLVED' | 'INVALID';
  message: string;
  player: Player | null;
}

export interface BulkImportResponse {
  created_count: number;
  duplicate_count: number;
  unresolved_count: number;
  invalid_count: number;
  entries: BulkImportEntry[];
}

export interface RoomPlayer {
  slot_order: number;
  locked_team: 'A' | 'B' | null;
  player: Player;
}

export interface PairConstraint {
  id: string;
  constraint_type: 'TOGETHER' | 'OPPONENT';
  player_a_id: string;
  player_b_id: string;
}

export interface FeedbackItem {
  id: string;
  generation_id: string;
  community_player_id: string | null;
  target_player_id: string | null;
  feedback_type: 'OBJECTION' | 'SWAP_REQUEST' | 'REMAKE_REQUEST';
  reason: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  host_note: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface ProposalAlternative {
  partition_key: string;
  team_a_ids: string[];
  team_b_ids: string[];
  team_a_strength: number;
  team_b_strength: number;
  strength_diff: number;
  objective_score: number;
  role_summary: {
    team_a: Record<string, number>;
    team_b: Record<string, number>;
  };
}

export interface ProposalSnapshotPlayer {
  id: string;
  display_name: string;
  steam_id64: string | null;
  identity_status: string;
  manual_rating?: number | null;
  premier_rating: number | null;
  faceit_elo: number | null;
  leetify_rating: number | null;
  primary_role: RoleType | null;
  normalized_strength: number | null;
  strength_band: string;
  confidence: number;
  sources_used: string[];
  missing_sources: string[];
  locked_team: 'A' | 'B' | null;
}

export interface Proposal {
  id: string;
  room_id: string;
  proposal_number: number;
  parent_generation_id: string | null;
  action_type: 'INITIAL' | 'REGENERATE' | 'SWAP' | 'RESTORE' | 'ALTERNATIVE';
  algorithm_version: string;
  normalizer_version: string;
  map_pool_version: string;
  seed: number;
  partition_key: string;
  team_a_ids: string[];
  team_b_ids: string[];
  team_a_strength: number;
  team_b_strength: number;
  strength_diff: number;
  objective_score: number;
  objective_components: Record<string, number>;
  explanation: {
    balance_indicator: string;
    matchup_label?: string;
    summary: string;
    good_match_summary?: string;
    team_a_notes?: string[];
    team_b_notes?: string[];
    share_summary?: string;
    avg_confidence: number;
    data_coverage_pct?: number;
    confidence_label: string;
    manual_only_count: number;
    manual_only_players: string[];
    stale_count?: number;
    unverified_identity_players: string[];
    role_notes: string[];
    player_contributions?: string[];
    recent_form_summary?: string;
    trade_offs?: string[];
    alternative_comparisons?: {
      partition_key: string;
      strength_diff: number;
      strength_diff_delta: number;
      moved_players: string;
      trade_off: string;
    }[];
    constraints_honored: string[];
    alternatives_found: number;
    map_policy_note: string;
  };
  alternatives: ProposalAlternative[];
  input_snapshot: ProposalSnapshotPlayer[];
  constraints_snapshot: {
    locked_a: string[];
    locked_b: string[];
    together_pairs: string[][];
    opponent_pairs: string[][];
  };
  feedback: FeedbackItem[];
  created_at: string;
}

export interface FinalizedLineup {
  id: string;
  room_id: string;
  generation_id: string;
  proposal_number: number;
  share_slug: string;
  team_a: ProposalSnapshotPlayer[];
  team_b: ProposalSnapshotPlayer[];
  team_a_strength: number;
  team_b_strength: number;
  strength_diff: number;
  discord_text: string;
  finalized_by: string;
  finalized_at: string;
}

export interface MatchRoom {
  id: string;
  community_id: string;
  title: string;
  status: string;
  version: number;
  share_slug: string;
  finalized_proposal_id: string | null;
  selected_count: number;
  roster: RoomPlayer[];
  constraints: PairConstraint[];
  proposals: Proposal[];
  finalized_lineup: FinalizedLineup | null;
  created_at: string;
  updated_at: string;
}

export interface SwapPreview {
  before_team_a_strength: number;
  before_team_b_strength: number;
  before_strength_diff: number;
  before_objective: number;
  after_team_a_strength: number;
  after_team_b_strength: number;
  after_strength_diff: number;
  after_objective: number;
  strength_diff_delta: number;
  objective_delta: number;
  after_team_a_ids: string[];
  after_team_b_ids: string[];
}

export interface HealthResponse {
  status: string;
  providers: {
    steam: string;
    faceit: string;
    leetify: string;
    cswatch?: string;
  };
  map_policy: string;
}
