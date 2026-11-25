import type {
  BulkImportResponse,
  HealthResponse,
  HumourIntensity,
  MatchRoom,
  Player,
  PlayerCompare,
  PlayerProfile,
  RefreshProfileResponse,
  RoleType,
  SwapPreview,
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

export class ApiError extends Error {
  status: number;
  code?: string;
  reasons?: string[];

  constructor(message: string, status: number, code?: string, reasons?: string[]) {
    super(message);
    this.status = status;
    this.code = code;
    this.reasons = reasons;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
    ...init,
  });

  if (resp.status === 204) {
    return undefined as T;
  }

  const text = await resp.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  if (!resp.ok) {
    const detail = data?.detail;
    if (detail && typeof detail === 'object') {
      throw new ApiError(
        detail.message || `Request failed (${resp.status})`,
        resp.status,
        detail.code,
        detail.reasons,
      );
    }
    throw new ApiError(
      typeof detail === 'string' ? detail : `Request failed (${resp.status})`,
      resp.status,
    );
  }

  return data as T;
}

export const api = {
  health: () => request<HealthResponse>('/health'),

  listPlayers: (q?: string) =>
    request<Player[]>(q ? `/players?q=${encodeURIComponent(q)}` : '/players'),

  createPlayer: (payload: {
    display_name: string;
    steam_id64?: string | null;
    steam_profile_url?: string | null;
    manual_rating: number;
    premier_rating?: number | null;
    faceit_elo?: number | null;
    leetify_rating?: number | null;
    recent_form?: number | null;
    primary_role?: RoleType | null;
    notes?: string | null;
  }) => request<Player>('/players', { method: 'POST', body: JSON.stringify(payload) }),

  updatePlayer: (id: string, payload: Record<string, unknown>) =>
    request<Player>(`/players/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  deletePlayer: (id: string) =>
    request<void>(`/players/${id}`, { method: 'DELETE' }),

  bulkImport: (text: string, defaultManualRating = 50, allowManualNames = true) =>
    request<BulkImportResponse>('/players/bulk-import', {
      method: 'POST',
      body: JSON.stringify({
        text,
        default_manual_rating: defaultManualRating,
        allow_manual_names: allowManualNames,
      }),
    }),

  seedDemoPlayers: () =>
    request<Player[]>('/players/seed-demo', { method: 'POST' }),

  preflightPlayer: (playerId: string) =>
    request<Player[]>(`/players/${playerId}/preflight`, { method: 'POST' }),

  getPlayerProfile: (playerId: string) =>
    request<PlayerProfile>(`/players/${playerId}/profile`),

  refreshPlayerProfile: (playerId: string, force = false) =>
    request<RefreshProfileResponse>(`/players/${playerId}/refresh?force=${force}`, {
      method: 'POST',
    }),

  addStatSnapshot: (playerId: string, payload: Record<string, unknown>) =>
    request<PlayerProfile>(`/players/${playerId}/stats`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateCardSettings: (
    playerId: string,
    payload: {
      humour_enabled?: boolean;
      humour_intensity?: HumourIntensity;
      hidden_badges?: string[];
      regenerate_tagline?: boolean;
      stats_visibility?: 'COMMUNITY' | 'HOST_ONLY';
      profile_visibility?: 'COMMUNITY' | 'PUBLIC' | 'PRIVATE';
    },
  ) =>
    request<PlayerProfile>(`/players/${playerId}/card-settings`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  comparePlayers: (playerAId: string, playerBId: string) =>
    request<PlayerCompare>(
      `/players/compare?a=${encodeURIComponent(playerAId)}&b=${encodeURIComponent(playerBId)}`,
    ),

  listRooms: () => request<MatchRoom[]>('/rooms'),

  createRoom: (title: string) =>
    request<MatchRoom>('/rooms', { method: 'POST', body: JSON.stringify({ title }) }),

  getRoom: (roomId: string) => request<MatchRoom>(`/rooms/${roomId}`),

  setRoster: (roomId: string, communityPlayerIds: string[]) =>
    request<MatchRoom>(`/rooms/${roomId}/roster`, {
      method: 'PUT',
      body: JSON.stringify({ community_player_ids: communityPlayerIds }),
    }),

  replaceRoomPlayer: (roomId: string, removePlayerId: string, addPlayerId: string) =>
    request<MatchRoom>(`/rooms/${roomId}/replace-player`, {
      method: 'POST',
      body: JSON.stringify({ remove_player_id: removePlayerId, add_player_id: addPlayerId }),
    }),

  lockPlayer: (roomId: string, playerId: string, lockedTeam: 'A' | 'B' | null) =>
    request<MatchRoom>(`/rooms/${roomId}/players/${playerId}/lock`, {
      method: 'PUT',
      body: JSON.stringify({ locked_team: lockedTeam }),
    }),

  addConstraint: (
    roomId: string,
    constraintType: 'TOGETHER' | 'OPPONENT',
    playerAId: string,
    playerBId: string,
  ) =>
    request<MatchRoom>(`/rooms/${roomId}/constraints`, {
      method: 'POST',
      body: JSON.stringify({
        constraint_type: constraintType,
        player_a_id: playerAId,
        player_b_id: playerBId,
      }),
    }),

  removeConstraint: (roomId: string, constraintId: string) =>
    request<MatchRoom>(`/rooms/${roomId}/constraints/${constraintId}`, { method: 'DELETE' }),

  runRoomPreflight: (roomId: string) =>
    request<Player[]>(`/rooms/${roomId}/preflight`, { method: 'POST' }),

  generateTeams: (roomId: string, seed = 42) =>
    request<MatchRoom>(`/rooms/${roomId}/generate`, {
      method: 'POST',
      body: JSON.stringify({ seed, force_cycle: false }),
    }),

  regenerateTeams: (roomId: string, seed = 42, forceCycle = false) =>
    request<MatchRoom>(`/rooms/${roomId}/regenerate`, {
      method: 'POST',
      body: JSON.stringify({ seed, force_cycle: forceCycle }),
    }),

  previewSwap: (roomId: string, generationId: string, playerAId: string, playerBId: string) =>
    request<SwapPreview>(`/rooms/${roomId}/swap-preview`, {
      method: 'POST',
      body: JSON.stringify({
        generation_id: generationId,
        player_a_id: playerAId,
        player_b_id: playerBId,
      }),
    }),

  commitSwap: (
    roomId: string,
    generationId: string,
    playerAId: string,
    playerBId: string,
    reason?: string,
  ) =>
    request<MatchRoom>(`/rooms/${roomId}/swap`, {
      method: 'POST',
      body: JSON.stringify({
        generation_id: generationId,
        player_a_id: playerAId,
        player_b_id: playerBId,
        reason: reason || null,
      }),
    }),

  adoptAlternative: (roomId: string, generationId: string, partitionKey: string) =>
    request<MatchRoom>(`/rooms/${roomId}/proposals/${generationId}/adopt-alternative`, {
      method: 'POST',
      body: JSON.stringify({ partition_key: partitionKey }),
    }),

  restoreProposal: (roomId: string, generationId: string) =>
    request<MatchRoom>(`/rooms/${roomId}/proposals/${generationId}/restore`, {
      method: 'POST',
    }),

  addFeedback: (
    roomId: string,
    generationId: string,
    payload: {
      community_player_id?: string | null;
      target_player_id?: string | null;
      feedback_type: 'OBJECTION' | 'SWAP_REQUEST' | 'REMAKE_REQUEST';
      reason: string;
    },
  ) =>
    request<MatchRoom>(`/rooms/${roomId}/proposals/${generationId}/feedback`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  resolveFeedback: (
    roomId: string,
    feedbackId: string,
    status: 'APPROVED' | 'REJECTED',
    hostNote?: string,
  ) =>
    request<MatchRoom>(`/rooms/${roomId}/feedback/${feedbackId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ status, host_note: hostNote || null }),
    }),

  finalizeRoom: (roomId: string, generationId: string, finalizedBy = 'Host') =>
    request<MatchRoom>(`/rooms/${roomId}/finalize`, {
      method: 'POST',
      body: JSON.stringify({ generation_id: generationId, finalized_by: finalizedBy }),
    }),

  reopenRoom: (roomId: string) =>
    request<MatchRoom>(`/rooms/${roomId}/reopen`, { method: 'POST' }),

  getSharedLineup: (slug: string) =>
    request<{ room_title: string; room_status: string; lineup: any }>(`/lineups/${slug}`),
};
