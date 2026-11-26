import type {
  AuthState,
  BulkImportResponse,
  CommunityStandingsResponse,
  CredentialStatus,
  HealthResponse,
  HumourIntensity,
  ImportHistoryItem,
  MatchRoom,
  OpsOverview,
  Player,
  PlayerCompare,
  PlayerProfile,
  RefreshProfileResponse,
  ResolveIdentityResponse,
  RoleType,
  SpreadsheetPreview,
  SwapPreview,
  TrustOverview,
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

const TOKEN_KEY = 'stackforge_session_token';
export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setStoredToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

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
  const token = getStoredToken();
  const isFormData = typeof FormData !== 'undefined' && init?.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((init?.headers as Record<string, string>) || {}),
  };
  const resp = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
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

  listPlayers: (q?: string, includeArchived = false) => {
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (includeArchived) params.set('include_archived', 'true');
    const qs = params.toString();
    return request<Player[]>(qs ? `/players?${qs}` : '/players');
  },

  archivePlayer: (id: string, archived = true) =>
    request<Player>(`/players/${id}/archive?archived=${archived}`, { method: 'POST' }),

  refreshAllPlayers: (force = false) =>
    request<{ total: number; results: any[] }>(`/players/refresh-all?force=${force}`, {
      method: 'POST',
    }),

  createPlayer: (payload: {
    display_name: string;
    steam_id64?: string | null;
    steam_profile_url?: string | null;
    manual_rating?: number | null;
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

  refreshPlayerProfile: (playerId: string, force = false, provider?: string) =>
    request<RefreshProfileResponse>(
      `/players/${playerId}/refresh?force=${force}${provider && provider !== 'all' ? `&provider=${encodeURIComponent(provider)}` : ''}`,
      {
        method: 'POST',
      },
    ),

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

  // Auth
  authMe: () => request<AuthState>('/auth/me'),
  authSignup: (email: string, username: string, password: string) =>
    request<{ token: string; user: AuthState['user'] }>('/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ email, username, password }),
    }),
  authLogin: (email: string, password: string) =>
    request<{ token: string; user: AuthState['user'] }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  authLogout: () => request<{ ok: boolean }>('/auth/logout', { method: 'POST' }),

  // Identity Resolution
  resolveIdentity: (query: string, discoverProviders = true) =>
    request<ResolveIdentityResponse>('/identity/resolve', {
      method: 'POST',
      body: JSON.stringify({ query, discover_providers: discoverProviders }),
    }),
  confirmIdentity: (payload: {
    community_player_id: string;
    provider: string;
    external_id: string;
    profile_url?: string | null;
    steam_id64?: string | null;
  }) =>
    request<any>('/identity/confirm', { method: 'POST', body: JSON.stringify(payload) }),

  // Spreadsheet Import & Sync
  previewGoogleSheet: (
    url: string,
    mappingOverride?: Record<string, string | null> | null,
    defaultRating = 55,
  ) =>
    request<SpreadsheetPreview>('/imports/google-sheet/preview', {
      method: 'POST',
      body: JSON.stringify({
        url,
        mapping_override: mappingOverride || null,
        default_rating: defaultRating,
      }),
    }),
  commitGoogleSheet: (
    url: string,
    mappingOverride?: Record<string, string | null> | null,
    overwriteManual = false,
    defaultRating = 55,
  ) =>
    request<any>('/imports/google-sheet/commit', {
      method: 'POST',
      body: JSON.stringify({
        url,
        mapping_override: mappingOverride || null,
        overwrite_manual: overwriteManual,
        default_rating: defaultRating,
      }),
    }),
  previewFileImport: (file: File, mappingJson?: string | null, defaultRating = 55) => {
    const fd = new FormData();
    fd.append('file', file);
    if (mappingJson) fd.append('mapping_json', mappingJson);
    fd.append('default_rating', String(defaultRating));
    return request<SpreadsheetPreview>('/imports/file/preview', { method: 'POST', body: fd });
  },
  commitFileImport: (
    file: File,
    mappingJson?: string | null,
    overwriteManual = false,
    defaultRating = 55,
  ) => {
    const fd = new FormData();
    fd.append('file', file);
    if (mappingJson) fd.append('mapping_json', mappingJson);
    fd.append('overwrite_manual', String(overwriteManual));
    fd.append('default_rating', String(defaultRating));
    return request<any>('/imports/file/commit', { method: 'POST', body: fd });
  },
  importHistory: () => request<ImportHistoryItem[]>('/imports/history'),
  syncImport: (importId: string, overwriteManual = false) =>
    request<any>(`/imports/${importId}/sync?overwrite_manual=${overwriteManual}`, {
      method: 'POST',
    }),

  // Trust & Account Watch
  trustOverview: () => request<TrustOverview>('/trust/overview'),
  runTrustCheck: (playerId: string) =>
    request<any[]>(`/trust/players/${playerId}/check`, { method: 'POST' }),
  addWatchlist: (communityPlayerId: string, reason: string, sourceUrl?: string) =>
    request<TrustOverview>('/trust/watchlist', {
      method: 'POST',
      body: JSON.stringify({
        community_player_id: communityPlayerId,
        reason,
        source_url: sourceUrl || null,
      }),
    }),
  reviewWatchlist: (
    entryId: string,
    status: 'WATCHING' | 'REVIEWED' | 'DISMISSED',
    reviewNote?: string,
  ) =>
    request<TrustOverview>(`/trust/watchlist/${entryId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status, review_note: reviewNote || null }),
    }),
  addTrustReport: (
    communityPlayerId: string,
    summary: string,
    sourceUrl?: string,
    category = 'COMMUNITY_REPORT',
  ) =>
    request<any>('/trust/reports', {
      method: 'POST',
      body: JSON.stringify({
        community_player_id: communityPlayerId,
        summary,
        source_url: sourceUrl || null,
        category,
      }),
    }),
  refreshWatched: () =>
    request<{ checked: number; overview: TrustOverview }>('/trust/refresh-watched', {
      method: 'POST',
    }),

  // Match Lifecycle & Community Standings
  markRoomPlayed: (roomId: string) =>
    request<MatchRoom>(`/rooms/${roomId}/played`, { method: 'POST' }),
  recordRoomResult: (
    roomId: string,
    payload: {
      map_played: string;
      team_a_score: number;
      team_b_score: number;
      external_match_url?: string | null;
      demo_reference?: string | null;
      notes?: string | null;
    },
  ) =>
    request<MatchRoom>(`/rooms/${roomId}/result`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  communityStandings: () => request<CommunityStandingsResponse>('/standings/community'),

  // Operational Health, Canonical Metrics & Optional Secret Vault
  opsOverview: () => request<OpsOverview>('/ops/overview'),
  metricsRegistry: () => request<{ metrics: any[] }>('/metrics/registry'),
  getCredentials: () =>
    request<{ keyless_mode_supported: boolean; storage_backend: string; credentials: CredentialStatus[] }>(
      '/settings/credentials',
    ),
  saveCredential: (provider: string, apiKey: string, validateLive = false) =>
    request<{ credential: CredentialStatus; validation: any }>(`/settings/credentials/${provider}`, {
      method: 'PUT',
      body: JSON.stringify({ api_key: apiKey, validate_live: validateLive }),
    }),
  validateCredential: (provider: string, apiKey?: string) =>
    request<{ provider: string; valid: boolean; status: string; message: string }>(
      `/settings/credentials/${provider}/validate`,
      {
        method: 'POST',
        body: JSON.stringify({ api_key: apiKey || null }),
      },
    ),
  deleteCredential: (provider: string) =>
    request<{ credential: CredentialStatus }>(`/settings/credentials/${provider}`, {
      method: 'DELETE',
    }),
};
