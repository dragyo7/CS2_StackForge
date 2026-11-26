import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowLeftRight,
  Check,
  CheckCircle2,
  Copy,
  History,
  Lock,
  MessageSquareWarning,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Share2,
  ShieldCheck,
  Sparkles,
  Unlock,
  UserMinus,
  UserPlus,
  XCircle,
} from 'lucide-react';
import { api, ApiError } from '../api';
import type {
  MatchRoom,
  Player,
  Proposal,
  ProposalSnapshotPlayer,
  RoleType,
  SwapPreview,
} from '../types';
import { ROLES } from '../types';
import { PlayerAvatar } from './PlayerAvatar';

interface Props {
  room: MatchRoom;
  players: Player[];
  onRoomUpdated: (room: MatchRoom) => void;
  onRefreshPlayers: () => Promise<void>;
  onError: (msg: string) => void;
  onOpenShareSlug: (slug: string) => void;
  onOpenProfile?: (playerId: string) => void;
}

export const MatchRoomView: React.FC<Props> = ({
  room,
  players,
  onRoomUpdated,
  onRefreshPlayers,
  onError,
  onOpenShareSlug,
  onOpenProfile,
}) => {
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState('');
  const [seed, setSeed] = useState('42');
  const [exhaustedMsg, setExhaustedMsg] = useState<string | null>(null);

  // Inline quick-add player inside match room without losing selection
  const [showQuickAdd, setShowQuickAdd] = useState(false);
  const [quickName, setQuickName] = useState('');
  const [quickSteam, setQuickSteam] = useState('');
  const [quickRole, setQuickRole] = useState<RoleType | ''>('');
  const [pickerSort, setPickerSort] = useState<'strength' | 'premier' | 'leetify' | 'name'>('strength');
  const [playerRefreshBanner, setPlayerRefreshBanner] = useState<string | null>(null);
  const [refreshingPlayerId, setRefreshingPlayerId] = useState<string | null>(null);

  // Replace player state
  const [replacingId, setReplacingId] = useState<string | null>(null);

  // Pair constraints
  const [pairType, setPairType] = useState<'TOGETHER' | 'OPPONENT'>('TOGETHER');
  const [pairA, setPairA] = useState('');
  const [pairB, setPairB] = useState('');

  // Swap state
  const [swapPickA, setSwapPickA] = useState<string | null>(null);
  const [swapPickB, setSwapPickB] = useState<string | null>(null);
  const [swapPreview, setSwapPreview] = useState<SwapPreview | null>(null);
  const [swapReason, setSwapReason] = useState('');

  // Feedback / objection form
  const [fbPlayerId, setFbPlayerId] = useState('');
  const [fbTargetId, setFbTargetId] = useState('');
  const [fbType, setFbType] = useState<'OBJECTION' | 'SWAP_REQUEST' | 'REMAKE_REQUEST'>('SWAP_REQUEST');
  const [fbReason, setFbReason] = useState('');

  // Copy states
  const [copiedDiscord, setCopiedDiscord] = useState(false);
  const [copiedShare, setCopiedShare] = useState(false);
  const [preflightResults, setPreflightResults] = useState<Player[] | null>(null);
  const [quickError, setQuickError] = useState<string | null>(null);
  const [showDetailedStats, setShowDetailedStats] = useState(false);

  const activeProposal: Proposal | null = room.proposals[0] || null;
  const isFinalized = room.status === 'FINALIZED';

  useEffect(() => {
    setSwapPickA(null);
    setSwapPickB(null);
    setSwapPreview(null);
    setExhaustedMsg(null);
  }, [room.id, activeProposal?.id]);

  useEffect(() => {
    if (!activeProposal || !swapPickA || !swapPickB) {
      setSwapPreview(null);
      return;
    }
    let cancelled = false;
    api
      .previewSwap(room.id, activeProposal.id, swapPickA, swapPickB)
      .then((res) => {
        if (!cancelled) setSwapPreview(res);
      })
      .catch((err) => {
        if (!cancelled) {
          setSwapPreview(null);
          onError(err instanceof ApiError ? err.message : 'Swap preview failed.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [room.id, activeProposal?.id, swapPickA, swapPickB]);

  const selectedIds = room.roster.map((r) => r.player.id);
  const selectedSet = new Set(selectedIds);
  const playerMap = new Map<string, Player>(players.map((p) => [p.id, p]));
  for (const r of room.roster) {
    playerMap.set(r.player.id, r.player);
  }

  const handleTogglePlayer = async (playerId: string) => {
    if (isFinalized) {
      onError('Room is finalized. Reopen the room to modify the roster.');
      return;
    }
    const exists = selectedSet.has(playerId);
    if (!exists && selectedIds.length >= 10) {
      onError('Roster already has 10 players. Remove or replace a player first.');
      return;
    }
    const nextIds = exists
      ? selectedIds.filter((id) => id !== playerId)
      : [...selectedIds, playerId];

    setBusy(true);
    try {
      const updated = await api.setRoster(room.id, nextIds);
      onRoomUpdated(updated);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Failed to update roster.');
    } finally {
      setBusy(false);
    }
  };

  const handleQuickAddPlayer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickName.trim()) return;
    setBusy(true);
    setQuickError(null);
    try {
      const trimmedSteam = quickSteam.trim();
      const isRawId = /^7656119\d{10}$/.test(trimmedSteam);
      const isUrl =
        trimmedSteam.includes('steamcommunity.com') ||
        trimmedSteam.includes('csstats.gg') ||
        trimmedSteam.includes('leetify.com') ||
        trimmedSteam.includes('cswatch.gg');
      const created = await api.createPlayer({
        display_name: quickName.trim(),
        steam_id64: isRawId ? trimmedSteam : null,
        steam_profile_url: isUrl ? trimmedSteam : null,
        primary_role: quickRole || null,
      });
      await onRefreshPlayers();
      if (selectedIds.length < 10 && !isFinalized) {
        const updated = await api.setRoster(room.id, [...selectedIds, created.id]);
        onRoomUpdated(updated);
      }
      setQuickName('');
      setQuickSteam('');
      setQuickRole('');
      setShowQuickAdd(false);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to add player.';
      setQuickError(msg);
      onError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleReplace = async (newPlayerId: string) => {
    if (!replacingId) return;
    setBusy(true);
    try {
      const updated = await api.replaceRoomPlayer(room.id, replacingId, newPlayerId);
      onRoomUpdated(updated);
      setReplacingId(null);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Failed to replace player.');
    } finally {
      setBusy(false);
    }
  };

  const handleQuickSelectTen = async () => {
    if (isFinalized) return;
    setBusy(true);
    try {
      let pool = players;
      if (pool.length < 10) {
        await api.seedDemoPlayers();
        await onRefreshPlayers();
        pool = await api.listPlayers();
      }
      const needed = [...selectedIds];
      for (const p of pool) {
        if (needed.length >= 10) break;
        if (!needed.includes(p.id)) needed.push(p.id);
      }
      const updated = await api.setRoster(room.id, needed.slice(0, 10));
      onRoomUpdated(updated);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Failed to auto-fill 10 players.');
    } finally {
      setBusy(false);
    }
  };

  const handleLock = async (playerId: string, lock: 'A' | 'B' | null) => {
    if (isFinalized) return;
    setBusy(true);
    try {
      const updated = await api.lockPlayer(room.id, playerId, lock);
      onRoomUpdated(updated);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Failed to update lock.');
    } finally {
      setBusy(false);
    }
  };

  const handleAddConstraint = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pairA || !pairB) return;
    setBusy(true);
    try {
      const updated = await api.addConstraint(room.id, pairType, pairA, pairB);
      onRoomUpdated(updated);
      setPairA('');
      setPairB('');
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Failed to add constraint.');
    } finally {
      setBusy(false);
    }
  };

  const handleRemoveConstraint = async (constraintId: string) => {
    setBusy(true);
    try {
      const updated = await api.removeConstraint(room.id, constraintId);
      onRoomUpdated(updated);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Failed to remove constraint.');
    } finally {
      setBusy(false);
    }
  };

  const handleRefreshSinglePlayer = async (playerId: string) => {
    setBusy(true);
    setRefreshingPlayerId(playerId);
    setPlayerRefreshBanner(null);
    try {
      const res = await api.refreshPlayerProfile(playerId, true);
      await onRefreshPlayers();
      const refreshedRoom = await api.getRoom(room.id);
      onRoomUpdated(refreshedRoom);
      const summary =
        res.provider_results && res.provider_results.length > 0
          ? res.provider_results.map((pr) => `${pr.provider}:${pr.status}`).join(' • ')
          : res.message;
      setPlayerRefreshBanner(`${res.profile.player.display_name} [${res.status || 'DONE'}]: ${summary}`);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Individual refresh failed.');
    } finally {
      setRefreshingPlayerId(null);
      setBusy(false);
    }
  };

  const handlePreflight = async () => {
    setBusy(true);
    try {
      const results = await api.runRoomPreflight(room.id);
      await onRefreshPlayers();
      const refreshed = await api.getRoom(room.id);
      onRoomUpdated(refreshed);
      setPreflightResults(results);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Refresh check error.');
    } finally {
      setBusy(false);
    }
  };

  const getPlayerSafetyWarnings = (p: Player) => {
    const warnings: Array<{ key: string; label: string; title: string; badgeClass: string }> = [];
    const ts = p.trust_summary;
    const risk = (ts?.cswatch_risk_level || '').toLowerCase();
    if (ts?.cswatch_status === 'FLAGGED' || risk === 'high' || risk === 'critical') {
      warnings.push({
        key: 'cswatch',
        label: `CSWatch ${ts?.cswatch_risk_level || 'Flagged'}`,
        title: `${ts?.cswatch_summary || 'CSWatch flagged signal.'} Informational only — never a cheat verdict and never alters skill rating.`,
        badgeClass: 'badge-danger',
      });
    } else if (risk === 'medium' || (ts?.cswatch_reputation_score != null && ts.cswatch_reputation_score < 60)) {
      warnings.push({
        key: 'cswatch',
        label: `CSWatch Rep ${ts?.cswatch_reputation_score ?? '?'}`,
        title: `${ts?.cswatch_summary || 'CSWatch caution.'} Informational only — never alters skill rating.`,
        badgeClass: 'badge-warn',
      });
    }
    if (ts?.watchlist_status === 'WATCHING') {
      warnings.push({
        key: 'watchlist',
        label: 'Watchlist',
        title: `${ts.watchlist_reason || 'On community watchlist.'} Informational only — never alters skill rating.`,
        badgeClass: 'badge-warn',
      });
    }
    if (!p.steam_id64 || p.identity_status !== 'STEAM_RESOLVED') {
      warnings.push({
        key: 'identity',
        label: 'Unverified ID',
        title: p.steam_id64 ? `Identity status: ${p.identity_status}` : 'Manual-only player without verified SteamID64.',
        badgeClass: 'badge-warn',
      });
    }
    if (p.stats_stale) {
      warnings.push({
        key: 'stale',
        label: 'Stale Stats',
        title: 'Latest combat statistics are older cached data (>= 14 days or marked STALE).',
        badgeClass: 'badge-warn',
      });
    }
    const unavailableProvs = (p.provider_statuses || []).filter(
      (s) =>
        s.provider !== 'faceit' &&
        s.provider !== 'steam_bans' &&
        (s.status === 'UNAVAILABLE' || s.status === 'RATE_LIMITED' || s.status === 'PRIVATE'),
    );
    if (p.steam_id64 && (unavailableProvs.length > 0 || (p.refresh_status !== 'OK' && p.refresh_status !== 'NEVER_REFRESHED'))) {
      const labelText =
        unavailableProvs.length > 0
          ? `${unavailableProvs[0].provider}: ${unavailableProvs[0].status.replace('_', ' ')}`
          : `Provider ${p.refresh_status}`;
      warnings.push({
        key: 'provider_unavail',
        label: labelText,
        title: unavailableProvs.map((u) => `${u.provider}: ${u.summary}`).join(' | ') || p.refresh_error || 'Provider data unavailable; using cached data.',
        badgeClass: 'badge-warn',
      });
    }
    return warnings;
  };

  const handleGenerate = async (isRegen: boolean, forceCycle = false) => {
    setBusy(true);
    setExhaustedMsg(null);
    try {
      const numericSeed = Number(seed) || 42;
      const updated = isRegen
        ? await api.regenerateTeams(room.id, numericSeed, forceCycle)
        : await api.generateTeams(room.id, numericSeed);
      onRoomUpdated(updated);
    } catch (err) {
      if (err instanceof ApiError && err.code === 'ALL_SPLITS_EXHAUSTED') {
        setExhaustedMsg(err.message);
      } else if (err instanceof ApiError && err.reasons?.length) {
        onError(`${err.message} (${err.reasons.join(' ')})`);
      } else {
        onError(err instanceof ApiError ? err.message : 'Team generation failed.');
      }
    } finally {
      setBusy(false);
    }
  };

  const handleCommitSwap = async () => {
    if (!activeProposal || !swapPickA || !swapPickB) return;
    setBusy(true);
    try {
      const updated = await api.commitSwap(
        room.id,
        activeProposal.id,
        swapPickA,
        swapPickB,
        swapReason.trim() || undefined,
      );
      onRoomUpdated(updated);
      setSwapPickA(null);
      setSwapPickB(null);
      setSwapReason('');
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Swap failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleAdoptAlternative = async (partitionKey: string) => {
    if (!activeProposal) return;
    setBusy(true);
    try {
      const updated = await api.adoptAlternative(room.id, activeProposal.id, partitionKey);
      onRoomUpdated(updated);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Could not adopt alternative.');
    } finally {
      setBusy(false);
    }
  };

  const handleRestore = async (proposalId: string) => {
    setBusy(true);
    try {
      const updated = await api.restoreProposal(room.id, proposalId);
      onRoomUpdated(updated);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Could not restore proposal.');
    } finally {
      setBusy(false);
    }
  };

  const handleAddFeedback = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProposal || !fbReason.trim()) return;
    setBusy(true);
    try {
      const updated = await api.addFeedback(room.id, activeProposal.id, {
        community_player_id: fbPlayerId || null,
        target_player_id: fbTargetId || null,
        feedback_type: fbType,
        reason: fbReason.trim(),
      });
      onRoomUpdated(updated);
      setFbReason('');
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Could not submit feedback.');
    } finally {
      setBusy(false);
    }
  };

  const handleResolveFeedback = async (fbId: string, status: 'APPROVED' | 'REJECTED') => {
    setBusy(true);
    try {
      const updated = await api.resolveFeedback(room.id, fbId, status);
      onRoomUpdated(updated);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Could not resolve objection.');
    } finally {
      setBusy(false);
    }
  };

  const handleFinalize = async () => {
    if (!activeProposal) return;
    setBusy(true);
    try {
      const updated = await api.finalizeRoom(room.id, activeProposal.id, 'Host');
      onRoomUpdated(updated);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Finalization failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleReopen = async () => {
    setBusy(true);
    try {
      const updated = await api.reopenRoom(room.id);
      onRoomUpdated(updated);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Could not reopen room.');
    } finally {
      setBusy(false);
    }
  };

  const copyDiscord = async () => {
    if (!room.finalized_lineup) return;
    await navigator.clipboard.writeText(room.finalized_lineup.discord_text);
    setCopiedDiscord(true);
    setTimeout(() => setCopiedDiscord(false), 1800);
  };

  const copyShareUrl = async () => {
    if (!room.finalized_lineup) return;
    const url = `${window.location.origin}/?share=${room.finalized_lineup.share_slug}`;
    await navigator.clipboard.writeText(url);
    setCopiedShare(true);
    setTimeout(() => setCopiedShare(false), 1800);
  };

  const availableToPick = players
    .filter((p) => {
      const q = search.trim().toLowerCase();
      if (!q) return true;
      const aliasHit = p.aliases.some(
        (a) =>
          a.alias_name.toLowerCase().includes(q) ||
          (a.previous_name && a.previous_name.toLowerCase().includes(q)),
      );
      return (
        p.display_name.toLowerCase().includes(q) ||
        (p.steam_id64 && p.steam_id64.includes(q)) ||
        (p.steam_persona_name && p.steam_persona_name.toLowerCase().includes(q)) ||
        (p.vanity_name && p.vanity_name.toLowerCase().includes(q)) ||
        (p.primary_role && p.primary_role.toLowerCase().includes(q)) ||
        aliasHit
      );
    })
    .slice()
    .sort((a, b) => {
      if (pickerSort === 'name') return a.display_name.localeCompare(b.display_name);
      if (pickerSort === 'premier') return (b.premier_rating ?? -1) - (a.premier_rating ?? -1);
      if (pickerSort === 'leetify') return (b.leetify_rating ?? -999) - (a.leetify_rating ?? -999);
      const sa = a.normalized_strength ?? -1;
      const sb = b.normalized_strength ?? -1;
      if (sb !== sa) return sb - sa;
      return b.confidence - a.confidence || a.display_name.localeCompare(b.display_name);
    });

  const handleResetSelection = async () => {
    if (isFinalized || selectedIds.length === 0) return;
    setBusy(true);
    try {
      const updated = await api.setRoster(room.id, []);
      onRoomUpdated(updated);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Failed to clear selection.');
    } finally {
      setBusy(false);
    }
  };

  const lockMap = new Map(room.roster.map((r) => [r.player.id, r.locked_team]));
  const snapshotMap = new Map<string, ProposalSnapshotPlayer>(
    (activeProposal?.input_snapshot || []).map((p) => [p.id, p]),
  );

  const renderTeamCard = (teamLabel: 'A' | 'B', ids: string[], avgStrength: number) => (
    <div className={`team-panel ${teamLabel === 'A' ? 'team-a' : 'team-b'}`}>
      <div className="card-header" style={{ marginBottom: '0.6rem' }}>
        <h3 style={{ color: teamLabel === 'A' ? 'var(--team-a)' : 'var(--team-b)' }}>
          TEAM {teamLabel}
        </h3>
        <span className={`badge ${teamLabel === 'A' ? 'badge-a' : 'badge-b'} mono`}>
          Avg {avgStrength.toFixed(1)}
        </span>
      </div>
      {ids.map((pid) => {
        const snap = snapshotMap.get(pid);
        const live = playerMap.get(pid);
        const name = snap?.display_name || live?.display_name || pid;
        const role = snap?.primary_role || live?.primary_role;
        const strength = snap ? snap.normalized_strength : live?.normalized_strength;
        const band = snap?.strength_band || live?.strength_band || 'Insufficient Data';
        const conf = snap?.confidence ?? live?.confidence ?? 0;
        const isInsufficient = strength == null || band === 'Insufficient Data';
        const currentLock = lockMap.get(pid) || null;
        const isPicked = (teamLabel === 'A' && swapPickA === pid) || (teamLabel === 'B' && swapPickB === pid);

        return (
          <div key={pid} className={`team-player-card ${isPicked ? 'swap-picked' : ''}`}>
            <div className="row" style={{ gap: '0.5rem', minWidth: 0 }}>
              <PlayerAvatar name={name} avatarUrl={live?.avatar_url} role={role} size={30} />
              <div style={{ minWidth: 0 }}>
                <div className="row" style={{ gap: '0.35rem' }}>
                  <strong
                    style={{ cursor: onOpenProfile ? 'pointer' : 'default' }}
                    onClick={() => onOpenProfile?.(pid)}
                  >
                    {name}
                  </strong>
                  {role && <span className="badge">{role}</span>}
                  {currentLock && (
                    <span className={`badge ${currentLock === 'A' ? 'badge-a' : 'badge-b'}`}>
                      <Lock size={10} /> {currentLock}
                    </span>
                  )}
                </div>
                <div className="small muted" style={{ marginTop: '0.15rem' }}>
                  <span className="mono">{strength != null ? strength.toFixed(1) : 'Unavailable'}</span> ({band}) • Conf {Math.round(conf * 100)}%
                  {isInsufficient ? ' • Low/No External Stats' : ''}
                </div>
              </div>
            </div>

            {!isFinalized && (
              <div className="row" style={{ gap: '0.25rem' }}>
                <button
                  className={`btn btn-xs ${isPicked ? 'btn-primary' : ''}`}
                  title={`Select from Team ${teamLabel} to swap`}
                  onClick={() => {
                    if (teamLabel === 'A') setSwapPickA(swapPickA === pid ? null : pid);
                    else setSwapPickB(swapPickB === pid ? null : pid);
                  }}
                >
                  <ArrowLeftRight size={12} /> {isPicked ? 'Picked' : 'Swap'}
                </button>
                <button
                  className={`btn btn-xs ${currentLock === teamLabel ? 'btn-primary' : ''}`}
                  title={currentLock === teamLabel ? 'Unlock player' : `Lock to Team ${teamLabel}`}
                  onClick={() => handleLock(pid, currentLock === teamLabel ? null : teamLabel)}
                >
                  {currentLock === teamLabel ? <Lock size={12} /> : <Unlock size={12} />}
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="room-layout">
      {/* LEFT COLUMN: 10-PLAYER ROSTER & CONSTRAINTS */}
      <div className="stack">
        <div className="card">
          <div className="card-header">
            <div>
              <h3 style={{ fontSize: '1.05rem' }}>{room.title}</h3>
              <span className="small muted">Room #{room.version} • Status: {room.status}</span>
            </div>
            <span className={`badge mono ${room.selected_count === 10 ? 'badge-ok' : 'badge-warn'}`}>
              {room.selected_count}/10 Players
            </span>
          </div>

          <div className="row" style={{ marginBottom: '0.75rem' }}>
            <span className="badge">Maps: Random</span>
            {room.selected_count < 10 && !isFinalized && (
              <button className="btn btn-xs" onClick={handleQuickSelectTen} disabled={busy}>
                <Sparkles size={12} /> {players.length < 10 ? 'Load Demo 10 & Fill' : 'Fill to 10'}
              </button>
            )}
            {room.selected_count > 0 && !isFinalized && (
              <button className="btn btn-xs" onClick={handleResetSelection} disabled={busy}>
                Reset Selection
              </button>
            )}
            <button
              className="btn btn-xs"
              onClick={handlePreflight}
              disabled={busy || room.selected_count === 0}
              title="Refresh Steam/Leetify/CSWatch status (non-blocking)"
            >
              Refresh Status
            </button>
          </div>

          {preflightResults && (
            <div className="card" style={{ background: 'var(--bg-canvas)', marginBottom: '0.75rem', padding: '0.6rem 0.75rem' }}>
              <div className="row" style={{ justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                <strong className="small">Pre-Match Refresh Report ({preflightResults.length} players)</strong>
                <button className="btn btn-xs" onClick={() => setPreflightResults(null)}>
                  Dismiss
                </button>
              </div>
              <div className="stack" style={{ gap: '0.25rem', maxHeight: '165px', overflowY: 'auto' }}>
                {preflightResults.map((pr) => {
                  const byProv = new Map(pr.provider_statuses.map((s) => [s.provider, s.status]));
                  const stStatus = byProv.get('steam_profile') || pr.refresh_status;
                  const ltStatus = byProv.get('leetify') || (pr.steam_id64 ? 'NOT_CHECKED' : 'NOT_LINKED');
                  const cwStatus = byProv.get('cswatch') || (pr.steam_id64 ? 'NOT_CHECKED' : 'NOT_LINKED');
                  return (
                    <div key={pr.id} className="row" style={{ justifyContent: 'space-between', gap: '0.35rem', fontSize: '0.75rem' }}>
                      <span style={{ fontWeight: 600 }}>{pr.display_name}</span>
                      <div className="row" style={{ gap: '0.25rem' }}>
                        <span className={`badge ${stStatus === 'OK' ? 'badge-ok' : 'badge-warn'}`}>Steam:{stStatus}</span>
                        <span className={`badge ${ltStatus === 'OK' ? 'badge-ok' : ltStatus === 'NOT_LINKED' ? '' : 'badge-warn'}`}>Leetify:{ltStatus}</span>
                        <span className={`badge ${cwStatus === 'OK' ? 'badge-ok' : cwStatus === 'FLAGGED' ? 'badge-danger' : 'badge-warn'}`}>CSWatch:{cwStatus}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="small muted" style={{ marginTop: '0.35rem' }}>
                Cached/previously stored data is preserved when providers are rate-limited, private, or unconfigured.
              </div>
            </div>
          )}

          {/* Selected 10 slots */}
          <div className="stack" style={{ gap: '0.4rem' }}>
            {room.roster.length === 0 ? (
              <div className="muted small" style={{ padding: '0.5rem 0' }}>
                Select 10 unique players below to unlock team generation.
              </div>
            ) : (
              room.roster.map((entry) => {
                const p = entry.player;
                const safetyWarnings = getPlayerSafetyWarnings(p);
                return (
                  <div key={p.id} className="player-row selected" style={{ padding: '0.45rem 0.6rem' }}>
                    <div style={{ minWidth: 0 }}>
                      <div className="row" style={{ gap: '0.35rem' }}>
                        <span className="mono small muted">{entry.slot_order}.</span>
                        <strong style={{ fontSize: '0.86rem' }}>{p.display_name}</strong>
                        {p.primary_role && <span className="badge">{p.primary_role}</span>}
                      </div>
                      <div className="small muted mono">
                        {p.normalized_strength != null ? `Str ${p.normalized_strength.toFixed(1)}` : 'Insufficient Data'} •{' '}
                        {p.steam_id64 ? 'SteamID' : 'Unlinked'}
                      </div>
                      {safetyWarnings.length > 0 && (
                        <div className="row" style={{ gap: '0.25rem', marginTop: '0.22rem', flexWrap: 'wrap' }}>
                          {safetyWarnings.map((w) => (
                            <span
                              key={w.key}
                              className={`badge ${w.badgeClass}`}
                              style={{ fontSize: '0.67rem', padding: '0.1rem 0.35rem' }}
                              title={w.title}
                            >
                              {w.label}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    {!isFinalized && (
                      <div className="row" style={{ gap: '0.25rem' }}>
                        <button
                          className="btn btn-xs"
                          onClick={() => handleRefreshSinglePlayer(p.id)}
                          disabled={busy || (!p.steam_id64 && !p.vanity_name)}
                          title="Refresh only this player"
                        >
                          <RefreshCw size={11} />
                        </button>
                        <button
                          className={`btn btn-xs ${entry.locked_team === 'A' ? 'btn-primary' : ''}`}
                          onClick={() => handleLock(p.id, entry.locked_team === 'A' ? null : 'A')}
                          title="Lock to Team A"
                        >
                          A
                        </button>
                        <button
                          className={`btn btn-xs ${entry.locked_team === 'B' ? 'btn-primary' : ''}`}
                          onClick={() => handleLock(p.id, entry.locked_team === 'B' ? null : 'B')}
                          title="Lock to Team B"
                        >
                          B
                        </button>
                        <button
                          className="btn btn-xs"
                          onClick={() => setReplacingId(replacingId === p.id ? null : p.id)}
                          title="Replace player"
                        >
                          Sub
                        </button>
                        <button
                          className="btn btn-xs btn-danger"
                          onClick={() => handleTogglePlayer(p.id)}
                          title="Remove from room"
                        >
                          <UserMinus size={12} />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {replacingId && (
            <div className="alert alert-warn" style={{ marginTop: '0.6rem', flexDirection: 'column' }}>
              <div className="small">
                Replacing <strong>{playerMap.get(replacingId)?.display_name}</strong> — click any unselected player below to swap in.
              </div>
              <button className="btn btn-xs" onClick={() => setReplacingId(null)}>
                Cancel Replace
              </button>
            </div>
          )}

          <div className="divider" />

          {/* Quick-Add Player inside room */}
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <strong className="small">Select Saved Players ({players.length})</strong>
            <button className="btn btn-xs" onClick={() => setShowQuickAdd(!showQuickAdd)}>
              <Plus size={12} /> {showQuickAdd ? 'Hide New' : 'New Player'}
            </button>
          </div>

          {showQuickAdd && (
            <form
              onSubmit={handleQuickAddPlayer}
              className="card"
              style={{ background: 'var(--bg-canvas)', padding: '0.65rem', marginBottom: '0.65rem' }}
            >
              <div className="stack" style={{ gap: '0.45rem' }}>
                {quickError && (
                  <div className="alert alert-danger" style={{ padding: '0.45rem 0.6rem' }}>
                    <span className="small">{quickError}</span>
                  </div>
                )}
                <input
                  className="input"
                  required
                  placeholder="Display name *"
                  value={quickName}
                  onChange={(e) => setQuickName(e.target.value)}
                />
                <input
                  className="input mono"
                  placeholder="SteamID64, /id/vanity, /profiles/, or CSStats URL"
                  value={quickSteam}
                  onChange={(e) => setQuickSteam(e.target.value)}
                />
                <div className="row">
                  <select
                    className="select"
                    style={{ flex: 1 }}
                    value={quickRole}
                    onChange={(e) => setQuickRole(e.target.value as RoleType | '')}
                  >
                    <option value="">Role (opt)</option>
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                </div>
                <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
                  Save & Add to Room
                </button>
              </div>
            </form>
          )}

          {playerRefreshBanner && (
            <div className="alert alert-ok" style={{ marginBottom: '0.5rem', padding: '0.45rem 0.6rem' }}>
              <span className="small">{playerRefreshBanner}</span>
              <button className="btn btn-xs" onClick={() => setPlayerRefreshBanner(null)}>
                OK
              </button>
            </div>
          )}

          <div className="row" style={{ gap: '0.4rem', marginBottom: '0.5rem' }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <Search
                size={14}
                style={{ position: 'absolute', left: '0.65rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
              />
              <input
                className="input"
                style={{ paddingLeft: '2rem', fontSize: '0.82rem' }}
                placeholder="Filter saved players..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <select
              className="select"
              style={{ width: 'auto', fontSize: '0.78rem', padding: '0.35rem 0.5rem' }}
              value={pickerSort}
              onChange={(e) => setPickerSort(e.target.value as 'strength' | 'premier' | 'leetify' | 'name')}
              title="Sort player picker"
            >
              <option value="strength">Rank: Competitive</option>
              <option value="premier">Rank: Premier CSR</option>
              <option value="leetify">Rank: Leetify</option>
              <option value="name">Sort: Name</option>
            </select>
          </div>

          <div className="stack" style={{ gap: '0.35rem', maxHeight: '260px', overflowY: 'auto' }}>
            {availableToPick.map((p) => {
              const inRoom = selectedSet.has(p.id);
              return (
                <div key={p.id} className="player-row" style={{ padding: '0.4rem 0.6rem' }}>
                  <div className="row" style={{ gap: '0.5rem', minWidth: 0 }}>
                    <PlayerAvatar name={p.display_name} avatarUrl={p.avatar_url} role={p.primary_role} size={28} />
                    <div style={{ minWidth: 0 }}>
                      <div className="row" style={{ gap: '0.35rem' }}>
                        <span style={{ fontSize: '0.84rem', fontWeight: 600 }}>{p.display_name}</span>
                        {p.primary_role && <span className="badge">{p.primary_role}</span>}
                      </div>
                      <div className="small muted mono">
                        {p.normalized_strength != null ? `Rating ${p.normalized_strength.toFixed(1)}` : 'Insufficient Data'}
                        {p.premier_rating != null ? ` • Prem ${p.premier_rating.toLocaleString()}` : ''}
                      </div>
                    </div>
                  </div>
                  <div className="row" style={{ gap: '0.25rem' }}>
                    <button
                      className="btn btn-xs"
                      onClick={() => handleRefreshSinglePlayer(p.id)}
                      disabled={busy || (!p.steam_id64 && !p.vanity_name)}
                      title="Refresh this player only"
                    >
                      <RefreshCw size={11} />
                      {refreshingPlayerId === p.id ? '...' : ''}
                    </button>
                    {replacingId && !inRoom ? (
                      <button className="btn btn-xs btn-primary" onClick={() => handleReplace(p.id)} disabled={busy}>
                        Swap In
                      </button>
                    ) : (
                      <button
                        className={`btn btn-xs ${inRoom ? 'btn-danger' : 'btn-primary'}`}
                        disabled={busy || isFinalized || (!inRoom && selectedIds.length >= 10)}
                        onClick={() => handleTogglePlayer(p.id)}
                      >
                        {inRoom ? <UserMinus size={12} /> : <UserPlus size={12} />}
                        {inRoom ? 'Remove' : 'Add'}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Pair Constraints */}
        {room.selected_count >= 2 && !isFinalized && (
          <div className="card">
            <h4 style={{ marginBottom: '0.55rem' }}>Pair Constraints (Optional)</h4>
            <form onSubmit={handleAddConstraint} className="stack" style={{ gap: '0.45rem' }}>
              <div className="row">
                <select
                  className="select"
                  value={pairType}
                  onChange={(e) => setPairType(e.target.value as 'TOGETHER' | 'OPPONENT')}
                >
                  <option value="TOGETHER">Keep Together</option>
                  <option value="OPPONENT">Force Opponents</option>
                </select>
              </div>
              <div className="row">
                <select className="select" style={{ flex: 1 }} value={pairA} onChange={(e) => setPairA(e.target.value)}>
                  <option value="">Player 1...</option>
                  {room.roster.map((r) => (
                    <option key={r.player.id} value={r.player.id}>
                      {r.player.display_name}
                    </option>
                  ))}
                </select>
                <select className="select" style={{ flex: 1 }} value={pairB} onChange={(e) => setPairB(e.target.value)}>
                  <option value="">Player 2...</option>
                  {room.roster.map((r) => (
                    <option key={r.player.id} value={r.player.id}>
                      {r.player.display_name}
                    </option>
                  ))}
                </select>
              </div>
              <button type="submit" className="btn btn-sm" disabled={busy || !pairA || !pairB || pairA === pairB}>
                Add Constraint
              </button>
            </form>

            {room.constraints.length > 0 && (
              <div className="stack" style={{ marginTop: '0.6rem', gap: '0.35rem' }}>
                {room.constraints.map((c) => (
                  <div key={c.id} className="player-row" style={{ padding: '0.35rem 0.55rem' }}>
                    <span className="small">
                      <strong>{c.constraint_type}</strong>: {playerMap.get(c.player_a_id)?.display_name} &{' '}
                      {playerMap.get(c.player_b_id)?.display_name}
                    </span>
                    <button className="btn btn-xs btn-danger" onClick={() => handleRemoveConstraint(c.id)}>
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* RIGHT COLUMN: TEAM GENERATION, REVIEW, OBJECTIONS, HISTORY & FINALIZE */}
      <div className="stack">
        {/* Top Action Bar */}
        <div className="card">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div className="row">
              <button
                className="btn btn-primary"
                disabled={busy || room.selected_count !== 10 || isFinalized}
                onClick={() => handleGenerate(false)}
              >
                <Sparkles size={15} />
                {activeProposal ? 'Create Fresh Teams' : 'Create Teams'}
              </button>

              {activeProposal && !isFinalized && (
                <button className="btn" disabled={busy} onClick={() => handleGenerate(true)}>
                  <RefreshCw size={15} /> Regenerate
                </button>
              )}

              {activeProposal?.parent_generation_id && !isFinalized && (
                <button
                  className="btn"
                  disabled={busy}
                  onClick={() => handleRestore(activeProposal.parent_generation_id!)}
                  title="Undo back to the previous team split"
                >
                  <RotateCcw size={15} /> Undo
                </button>
              )}
            </div>

            {activeProposal && !isFinalized && (
              <button className="btn btn-ok" disabled={busy} onClick={handleFinalize}>
                <ShieldCheck size={15} /> Finalize Teams (#{activeProposal.proposal_number})
              </button>
            )}
            {isFinalized && (
              <button className="btn" disabled={busy} onClick={handleReopen}>
                <RotateCcw size={15} /> Reopen Room
              </button>
            )}
          </div>

          {room.selected_count !== 10 && (
            <p className="muted small" style={{ margin: '0.55rem 0 0' }}>
              Select 10 unique players ({room.selected_count}/10 selected) to build two balanced 5v5 teams.
            </p>
          )}
        </div>

        {exhaustedMsg && (
          <div className="alert alert-warn">
            <div>
              <strong>All valid splits already shown:</strong> {exhaustedMsg}
            </div>
            <button className="btn btn-xs" onClick={() => handleGenerate(true, true)}>
              Cycle Again
            </button>
          </div>
        )}

        {/* FINALIZED LINEUP PANEL */}
        {room.finalized_lineup && isFinalized && (
          <div className="card" style={{ borderColor: 'rgba(16, 185, 129, 0.45)' }}>
            <div className="card-header">
              <div>
                <div className="row">
                  <span className="badge badge-ok">
                    <ShieldCheck size={13} /> FINALIZED
                  </span>
                  <h3>Proposal #{room.finalized_lineup.proposal_number} Locked In</h3>
                </div>
                <p className="muted small" style={{ margin: '0.25rem 0 0' }}>
                  Maps are random (active pool). Copy the Discord-ready format or share the read-only link.
                </p>
              </div>
              <div className="row">
                <button className="btn btn-primary" onClick={copyDiscord}>
                  {copiedDiscord ? <Check size={15} /> : <Copy size={15} />}
                  {copiedDiscord ? 'Copied!' : 'Copy Discord Lineup'}
                </button>
                <button className="btn" onClick={copyShareUrl}>
                  {copiedShare ? <Check size={15} /> : <Share2 size={15} />}
                  {copiedShare ? 'Link Copied!' : 'Copy Share Link'}
                </button>
                <button className="btn" onClick={() => onOpenShareSlug(room.finalized_lineup!.share_slug)}>
                  Open Share View
                </button>
              </div>
            </div>
            <pre
              className="mono small"
              style={{
                background: 'var(--bg-canvas)',
                padding: '0.75rem',
                borderRadius: '8px',
                border: '1px solid var(--border)',
                margin: 0,
                whiteSpace: 'pre-wrap',
              }}
            >
              {room.finalized_lineup.discord_text}
            </pre>
          </div>
        )}

        {/* ACTIVE PROPOSAL COMPARISON */}
        {activeProposal ? (
          <>
            <div className="card">
              <div className="card-header">
                <div className="row">
                  <h3>Matchup #{activeProposal.proposal_number}</h3>
                  <span className="badge">{activeProposal.action_type}</span>
                  <span
                    className={`badge ${
                      activeProposal.strength_diff <= 1.5
                        ? 'badge-ok'
                        : activeProposal.strength_diff <= 3.8
                          ? 'badge-a'
                          : 'badge-warn'
                    }`}
                  >
                    {activeProposal.explanation.matchup_label || activeProposal.explanation.balance_indicator}
                  </span>
                </div>
                <span className="small muted">{activeProposal.explanation.map_policy_note}</span>
              </div>

              {/* Swap Preview Bar */}
              {(swapPickA || swapPickB) && !isFinalized && (
                <div className="alert alert-warn" style={{ marginBottom: '0.85rem', flexDirection: 'column', gap: '0.5rem' }}>
                  <div className="row" style={{ width: '100%', justifyContent: 'space-between' }}>
                    <div className="small">
                      <strong>Swap Selection:</strong>{' '}
                      Team A: <strong>{swapPickA ? playerMap.get(swapPickA)?.display_name : 'pick a player'}</strong> ↔{' '}
                      Team B: <strong>{swapPickB ? playerMap.get(swapPickB)?.display_name : 'pick a player'}</strong>
                    </div>
                    <button
                      className="btn btn-xs"
                      onClick={() => {
                        setSwapPickA(null);
                        setSwapPickB(null);
                      }}
                    >
                      Clear
                    </button>
                  </div>
                  {swapPreview && (
                    <div className="row" style={{ width: '100%', justifyContent: 'space-between' }}>
                      <div className="small mono">
                        Diff: {swapPreview.before_strength_diff.toFixed(2)} →{' '}
                        <strong>{swapPreview.after_strength_diff.toFixed(2)}</strong> (
                        {swapPreview.strength_diff_delta >= 0 ? '+' : ''}
                        {swapPreview.strength_diff_delta.toFixed(2)}) | Team A{' '}
                        {swapPreview.after_team_a_strength.toFixed(1)} vs Team B{' '}
                        {swapPreview.after_team_b_strength.toFixed(1)}
                      </div>
                      <div className="row">
                        <input
                          className="input"
                          style={{ width: '180px', padding: '0.3rem 0.5rem', fontSize: '0.8rem' }}
                          placeholder="Reason (optional)"
                          value={swapReason}
                          onChange={(e) => setSwapReason(e.target.value)}
                        />
                        <button className="btn btn-primary btn-sm" onClick={handleCommitSwap} disabled={busy}>
                          Confirm Swap
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="grid-2">
                {renderTeamCard('A', activeProposal.team_a_ids, activeProposal.team_a_strength)}
                {renderTeamCard('B', activeProposal.team_b_ids, activeProposal.team_b_strength)}
              </div>

              {/* CS2-Native Matchup Breakdown */}
              <div
                className="card"
                style={{ background: 'var(--bg-canvas)', marginTop: '0.85rem', padding: '0.9rem' }}
              >
                <div className="row" style={{ justifyContent: 'space-between', marginBottom: '0.55rem' }}>
                  <strong>Why this should be a good match</strong>
                  <button
                    type="button"
                    className="btn btn-xs"
                    onClick={() => setShowDetailedStats(!showDetailedStats)}
                  >
                    {showDetailedStats ? 'Hide Detailed Stats Breakdown' : 'Show Detailed Stats Breakdown'}
                  </button>
                </div>

                <p style={{ margin: '0 0 0.75rem', fontSize: '0.88rem', color: 'var(--text-primary)' }}>
                  {activeProposal.explanation.good_match_summary || activeProposal.explanation.summary}
                </p>

                {(activeProposal.explanation.team_a_notes || activeProposal.explanation.team_b_notes) && (
                  <div className="grid-2" style={{ gap: '0.75rem', marginBottom: '0.65rem' }}>
                    <div className="card" style={{ background: 'var(--bg-surface)', padding: '0.7rem' }}>
                      <strong className="small" style={{ color: 'var(--team-a)' }}>Team A Profile</strong>
                      <div className="stack" style={{ gap: '0.25rem', marginTop: '0.35rem' }}>
                        {(activeProposal.explanation.team_a_notes || []).map((note, idx) => (
                          <div key={idx} className="small muted">• {note}</div>
                        ))}
                      </div>
                    </div>
                    <div className="card" style={{ background: 'var(--bg-surface)', padding: '0.7rem' }}>
                      <strong className="small" style={{ color: 'var(--team-b)' }}>Team B Profile</strong>
                      <div className="stack" style={{ gap: '0.25rem', marginTop: '0.35rem' }}>
                        {(activeProposal.explanation.team_b_notes || []).map((note, idx) => (
                          <div key={idx} className="small muted">• {note}</div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                <div className="row" style={{ gap: '0.4rem' }}>
                  {activeProposal.explanation.constraints_honored?.map((c, idx) => (
                    <span key={idx} className="badge badge-ok">
                      {c}
                    </span>
                  ))}
                  {activeProposal.explanation.manual_only_count > 0 && (
                    <span className="badge badge-warn">
                      <AlertTriangle size={11} /> {activeProposal.explanation.manual_only_count}/10 lack external stats
                    </span>
                  )}
                </div>

                {showDetailedStats && (
                  <div className="card" style={{ background: 'var(--bg-elevated)', marginTop: '0.7rem', padding: '0.7rem' }}>
                    <div className="row" style={{ justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                      <strong className="small">Detailed Stats Breakdown</strong>
                      <div className="row" style={{ gap: '0.35rem' }}>
                        <span className="small muted">Rating Gap: <strong className="mono">{activeProposal.strength_diff.toFixed(2)}</strong></span>
                        <span className="small muted">Confidence: <strong className="mono">{Math.round((activeProposal.explanation.avg_confidence || 0.55) * 100)}%</strong></span>
                        {activeProposal.explanation.data_coverage_pct != null && (
                          <span className="small muted">Coverage: <strong className="mono">{activeProposal.explanation.data_coverage_pct}%</strong></span>
                        )}
                      </div>
                    </div>
                    {activeProposal.explanation.player_contributions?.map((c, idx) => (
                      <div key={idx} className="small muted">• {c}</div>
                    ))}
                    {activeProposal.explanation.recent_form_summary && (
                      <div className="small muted">• {activeProposal.explanation.recent_form_summary}</div>
                    )}
                    <div className="row" style={{ marginTop: '0.45rem', gap: '0.35rem' }}>
                      <span className="small muted">Seed</span>
                      <input
                        className="input mono"
                        style={{ width: '74px', padding: '0.2rem 0.4rem', fontSize: '0.78rem' }}
                        type="number"
                        value={seed}
                        onChange={(e) => setSeed(e.target.value)}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* ALTERNATIVES + OBJECTIONS + HISTORY */}
            <div className="grid-2">
              {/* Alternatives */}
              <div className="card">
                <h4 style={{ marginBottom: '0.6rem' }}>
                  Distinct Alternatives ({activeProposal.alternatives.length})
                </h4>
                {activeProposal.alternatives.length === 0 ? (
                  <p className="muted small">No additional distinct splits under current locks.</p>
                ) : (
                  <div className="stack" style={{ gap: '0.5rem' }}>
                    {activeProposal.alternatives.map((alt, idx) => {
                      const cmp = activeProposal.explanation.alternative_comparisons?.find(
                        (c) => c.partition_key === alt.partition_key,
                      );
                      return (
                        <div key={alt.partition_key} className="player-row" style={{ alignItems: 'flex-start' }}>
                          <div style={{ minWidth: 0 }}>
                            <div className="row" style={{ gap: '0.4rem' }}>
                              <strong className="small">Option #{idx + 1}</strong>
                              <span className="badge mono">Diff {alt.strength_diff.toFixed(2)}</span>
                              <span className="small muted mono">
                                {alt.team_a_strength.toFixed(1)} vs {alt.team_b_strength.toFixed(1)}
                              </span>
                            </div>
                            <div className="small muted" style={{ marginTop: '0.25rem' }}>
                              A: {alt.team_a_ids.map((id) => playerMap.get(id)?.display_name || id).join(', ')}
                            </div>
                            {cmp && (
                              <div className="small muted" style={{ marginTop: '0.2rem' }}>
                                {cmp.moved_players} • {cmp.trade_off}
                              </div>
                            )}
                          </div>
                          {!isFinalized && (
                            <button
                              className="btn btn-xs"
                              disabled={busy}
                              onClick={() => handleAdoptAlternative(alt.partition_key)}
                            >
                              Use Split
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Objections & Requests */}
              <div className="card">
                <h4 style={{ marginBottom: '0.6rem' }}>
                  <MessageSquareWarning size={15} style={{ verticalAlign: 'text-bottom', marginRight: '0.35rem' }} />
                  Objections & Swap Requests
                </h4>
                {!isFinalized && (
                  <form onSubmit={handleAddFeedback} className="stack" style={{ gap: '0.4rem', marginBottom: '0.7rem' }}>
                    <div className="row">
                      <select
                        className="select"
                        style={{ flex: 1 }}
                        value={fbType}
                        onChange={(e) => setFbType(e.target.value as any)}
                      >
                        <option value="SWAP_REQUEST">Swap Request</option>
                        <option value="OBJECTION">Objection</option>
                        <option value="REMAKE_REQUEST">Remake Request</option>
                      </select>
                      <select
                        className="select"
                        style={{ flex: 1 }}
                        value={fbPlayerId}
                        onChange={(e) => setFbPlayerId(e.target.value)}
                      >
                        <option value="">Player (optional)...</option>
                        {room.roster.map((r) => (
                          <option key={r.player.id} value={r.player.id}>
                            {r.player.display_name}
                          </option>
                        ))}
                      </select>
                    </div>
                    {fbType === 'SWAP_REQUEST' && (
                      <select
                        className="select"
                        value={fbTargetId}
                        onChange={(e) => setFbTargetId(e.target.value)}
                      >
                        <option value="">Suggested counterpart (optional)...</option>
                        {room.roster.map((r) => (
                          <option key={r.player.id} value={r.player.id}>
                            {r.player.display_name}
                          </option>
                        ))}
                      </select>
                    )}
                    <div className="row">
                      <input
                        className="input"
                        style={{ flex: 1 }}
                        placeholder="Reason (e.g. two main AWPers on Team A)..."
                        value={fbReason}
                        onChange={(e) => setFbReason(e.target.value)}
                      />
                      <button type="submit" className="btn btn-sm" disabled={busy || !fbReason.trim()}>
                        Log
                      </button>
                    </div>
                  </form>
                )}

                {activeProposal.feedback.length === 0 ? (
                  <p className="muted small" style={{ margin: 0 }}>
                    No objections recorded on Proposal #{activeProposal.proposal_number}.
                  </p>
                ) : (
                  <div className="stack" style={{ gap: '0.4rem' }}>
                    {activeProposal.feedback.map((fb) => (
                      <div key={fb.id} className="player-row" style={{ alignItems: 'flex-start' }}>
                        <div style={{ minWidth: 0 }}>
                          <div className="row" style={{ gap: '0.35rem' }}>
                            <span className="badge">{fb.feedback_type}</span>
                            <span
                              className={`badge ${
                                fb.status === 'APPROVED'
                                  ? 'badge-ok'
                                  : fb.status === 'REJECTED'
                                    ? 'badge-danger'
                                    : 'badge-warn'
                              }`}
                            >
                              {fb.status}
                            </span>
                            {fb.community_player_id && (
                              <strong className="small">
                                {playerMap.get(fb.community_player_id)?.display_name}
                              </strong>
                            )}
                          </div>
                          <div className="small" style={{ marginTop: '0.2rem' }}>{fb.reason}</div>
                        </div>
                        {fb.status === 'PENDING' && !isFinalized && (
                          <div className="row" style={{ gap: '0.25rem' }}>
                            <button
                              className="btn btn-xs btn-ok"
                              onClick={() => handleResolveFeedback(fb.id, 'APPROVED')}
                              title="Approve objection"
                            >
                              <CheckCircle2 size={12} />
                            </button>
                            <button
                              className="btn btn-xs btn-danger"
                              onClick={() => handleResolveFeedback(fb.id, 'REJECTED')}
                              title="Reject objection"
                            >
                              <XCircle size={12} />
                            </button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Proposal History */}
            <div className="card">
              <h4 style={{ marginBottom: '0.6rem' }}>
                <History size={15} style={{ verticalAlign: 'text-bottom', marginRight: '0.35rem' }} />
                Proposal History ({room.proposals.length})
              </h4>
              <div className="stack" style={{ gap: '0.4rem' }}>
                {room.proposals.map((prop) => {
                  const isCurrent = prop.id === activeProposal.id;
                  const isFinProp = prop.id === room.finalized_proposal_id;
                  return (
                    <div key={prop.id} className={`player-row ${isCurrent ? 'selected' : ''}`}>
                      <div className="row" style={{ gap: '0.45rem' }}>
                        <strong className="mono small">#{prop.proposal_number}</strong>
                        <span className="badge">{prop.action_type}</span>
                        {isFinProp && <span className="badge badge-ok">FINALIZED</span>}
                        <span className="small muted mono">
                          {prop.team_a_strength.toFixed(1)} vs {prop.team_b_strength.toFixed(1)} (diff{' '}
                          {prop.strength_diff.toFixed(2)})
                        </span>
                      </div>
                      {!isCurrent && !isFinalized && (
                        <button className="btn btn-xs" disabled={busy} onClick={() => handleRestore(prop.id)}>
                          <RotateCcw size={12} /> Restore
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        ) : (
          <div className="card" style={{ textAlign: 'center', padding: '2.5rem 1.25rem' }}>
            <h3>Ready for 5v5 Team Generation</h3>
            <p className="muted" style={{ maxWidth: '500px', margin: '0.5rem auto 0' }}>
              Select 10 unique players in the roster panel on the left, then click{' '}
              <strong>Create Teams</strong>. Maps remain random — no map picker is used.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
