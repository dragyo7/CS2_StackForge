export type RoleType = 'Entry' | 'Rifler' | 'AWPer' | 'Support' | 'Lurker' | 'IGL';

export const ROLES: RoleType[] = ['Entry', 'Rifler', 'AWPer', 'Support', 'Lurker', 'IGL'];

export type HumourIntensity = 'MILD' | 'SPICY' | 'SAVAGE';

export interface ProviderStatus {
  provider: string;
  status: string;
  summary: string;
  fetched_at: string | null;
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
  manual_rating: number;
  premier_rating: number | null;
  premier_source: string | null;
  premier_season: string | null;
  faceit_elo: number | null;
  leetify_rating: number | null;
  recent_form: number | null;
  primary_role: RoleType | null;
  secondary_role: RoleType | null;
  notes: string | null;
  is_seeded: boolean;
  normalized_strength: number;
  confidence: number;
  strength_band: string;
  missing_sources: string[];
  provider_statuses: ProviderStatus[];
  aliases: AliasItem[];
  latest_stats: StatSnapshot | null;
  card: PlayerCard | null;
  created_at: string;
  updated_at: string;
}

export interface PlayerProfile {
  player: Player;
  stat_snapshots: StatSnapshot[];
  aliases: AliasItem[];
  provider_statuses: ProviderStatus[];
  card: PlayerCard;
}

export interface RefreshProfileResponse {
  profile: PlayerProfile;
  cache_hit: boolean;
  alias_changed: boolean;
  message: string;
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
  manual_rating: number;
  premier_rating: number | null;
  faceit_elo: number | null;
  leetify_rating: number | null;
  primary_role: RoleType | null;
  normalized_strength: number;
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
    summary: string;
    avg_confidence: number;
    confidence_label: string;
    manual_only_count: number;
    manual_only_players: string[];
    unverified_identity_players: string[];
    role_notes: string[];
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
  };
  map_policy: string;
}
