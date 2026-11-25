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
  const [quickRating, setQuickRating] = useState('55');
  const [quickRole, setQuickRole] = useState<RoleType | ''>('');

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
  const [preflightNote, setPreflightNote] = useState<string | null>(null);

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
    try {
      const trimmedSteam = quickSteam.trim();
      const isRawId = /^7656119\d{10}$/.test(trimmedSteam);
      const isUrl = trimmedSteam.includes('steamcommunity.com');
      const created = await api.createPlayer({
        display_name: quickName.trim(),
        steam_id64: isRawId ? trimmedSteam : null,
        steam_profile_url: isUrl ? trimmedSteam : null,
        manual_rating: Number(quickRating) || 55,
        primary_role: quickRole || null,
      });
      await onRefreshPlayers();
      if (selectedIds.length < 10 && !isFinalized) {
        const updated = await api.setRoster(room.id, [...selectedIds, created.id]);
        onRoomUpdated(updated);
      }
      setQuickName('');
      setQuickSteam('');
      setQuickRating('55');
      setQuickRole('');
      setShowQuickAdd(false);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Failed to add player.');
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

  const handlePreflight = async () => {
    setBusy(true);
    try {
      await api.runRoomPreflight(room.id);
      await onRefreshPlayers();
      const refreshed = await api.getRoom(room.id);
      onRoomUpdated(refreshed);
      setPreflightNote(
        'Preflight completed (non-blocking). Unconfigured external providers remain Unavailable/Not configured and do not block team generation.',
      );
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Preflight check error.');
    } finally {
      setBusy(false);
    }
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

  const availableToPick = players.filter((p) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (
      p.display_name.toLowerCase().includes(q) ||
      (p.steam_id64 && p.steam_id64.includes(q)) ||
      (p.primary_role && p.primary_role.toLowerCase().includes(q))
    );
  });

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
        const strength = snap?.normalized_strength ?? live?.normalized_strength ?? 50;
        const band = snap?.strength_band || live?.strength_band || 'Solid';
        const conf = snap?.confidence ?? live?.confidence ?? 0.55;
        const isManualOnly = snap
          ? snap.sources_used.length === 1 && snap.sources_used[0] === 'manual'
          : (live?.missing_sources.length ?? 0) >= 3;
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
                  <span className="mono">{strength.toFixed(1)}</span> ({band}) • Conf {Math.round(conf * 100)}%
                  {isManualOnly ? ' • Manual baseline' : ''}
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
            <span className="badge">Maps: Random (Active Pool)</span>
            {room.selected_count < 10 && !isFinalized && (
              <button className="btn btn-xs" onClick={handleQuickSelectTen} disabled={busy}>
                <Sparkles size={12} /> {players.length < 10 ? 'Load Demo 10 & Fill' : 'Auto-Fill to 10'}
              </button>
            )}
            <button
              className="btn btn-xs"
              onClick={handlePreflight}
              disabled={busy || room.selected_count === 0}
              title="Check Steam/FACEIT/Leetify if configured (non-blocking)"
            >
              Run Preflight
            </button>
          </div>

          {preflightNote && (
            <div className="alert alert-warn" style={{ marginBottom: '0.75rem', padding: '0.55rem 0.7rem' }}>
              <span className="small">{preflightNote}</span>
              <button className="btn btn-xs" onClick={() => setPreflightNote(null)}>
                OK
              </button>
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
                return (
                  <div key={p.id} className="player-row selected" style={{ padding: '0.45rem 0.6rem' }}>
                    <div style={{ minWidth: 0 }}>
                      <div className="row" style={{ gap: '0.35rem' }}>
                        <span className="mono small muted">{entry.slot_order}.</span>
                        <strong style={{ fontSize: '0.86rem' }}>{p.display_name}</strong>
                        {p.primary_role && <span className="badge">{p.primary_role}</span>}
                      </div>
                      <div className="small muted mono">
                        Str {p.normalized_strength.toFixed(1)} • {p.steam_id64 ? 'SteamID' : 'Manual'}
                      </div>
                    </div>
                    {!isFinalized && (
                      <div className="row" style={{ gap: '0.25rem' }}>
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
                <input
                  className="input"
                  required
                  placeholder="Display name *"
                  value={quickName}
                  onChange={(e) => setQuickName(e.target.value)}
                />
                <input
                  className="input mono"
                  placeholder="SteamID64 or /profiles/ URL (optional)"
                  value={quickSteam}
                  onChange={(e) => setQuickSteam(e.target.value)}
                />
                <div className="row">
                  <input
                    className="input mono"
                    type="number"
                    min={1}
                    max={100}
                    style={{ flex: 1 }}
                    value={quickRating}
                    onChange={(e) => setQuickRating(e.target.value)}
                    placeholder="Rating 1-100"
                  />
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

          <div style={{ position: 'relative', marginBottom: '0.5rem' }}>
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

          <div className="stack" style={{ gap: '0.35rem', maxHeight: '240px', overflowY: 'auto' }}>
            {availableToPick.map((p) => {
              const inRoom = selectedSet.has(p.id);
              return (
                <div key={p.id} className="player-row" style={{ padding: '0.4rem 0.6rem' }}>
                  <div style={{ minWidth: 0 }}>
                    <div className="row" style={{ gap: '0.35rem' }}>
                      <span style={{ fontSize: '0.84rem', fontWeight: 600 }}>{p.display_name}</span>
                      {p.primary_role && <span className="badge">{p.primary_role}</span>}
                    </div>
                    <div className="small muted mono">Str {p.normalized_strength.toFixed(1)}</div>
                  </div>
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
                      {inRoom ? 'Remove' : 'Select'}
                    </button>
                  )}
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
                {activeProposal ? 'Generate Initial' : 'Generate Teams (126 Splits)'}
              </button>

              {activeProposal && !isFinalized && (
                <button className="btn" disabled={busy} onClick={() => handleGenerate(true)}>
                  <RefreshCw size={15} /> Regenerate (New Split)
                </button>
              )}

              <div className="row" style={{ gap: '0.3rem' }}>
                <span className="small muted">Seed</span>
                <input
                  className="input mono"
                  style={{ width: '68px', padding: '0.35rem 0.45rem' }}
                  type="number"
                  value={seed}
                  onChange={(e) => setSeed(e.target.value)}
                />
              </div>
            </div>

            {activeProposal && !isFinalized && (
              <button className="btn btn-ok" disabled={busy} onClick={handleFinalize}>
                <ShieldCheck size={15} /> Finalize Proposal #{activeProposal.proposal_number}
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
              Select exactly 10 unique players ({room.selected_count}/10 currently selected) to enable the 126-partition optimizer.
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
                  <h3>Proposal #{activeProposal.proposal_number}</h3>
                  <span className="badge">{activeProposal.action_type}</span>
                  <span
                    className={`badge ${
                      activeProposal.strength_diff <= 3.5
                        ? 'badge-ok'
                        : activeProposal.strength_diff <= 6.5
                          ? 'badge-warn'
                          : 'badge-danger'
                    }`}
                  >
                    {activeProposal.explanation.balance_indicator} • Diff{' '}
                    <span className="mono">{activeProposal.strength_diff.toFixed(2)}</span>
                  </span>
                  <span className="badge">
                    Conf {Math.round((activeProposal.explanation.avg_confidence || 0.55) * 100)}%
                  </span>
                </div>
                <span className="small muted mono">
                  {activeProposal.algorithm_version} • seed {activeProposal.seed}
                </span>
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

              {/* Explanation */}
              <div
                className="card"
                style={{ background: 'var(--bg-canvas)', marginTop: '0.85rem', padding: '0.8rem' }}
              >
                <div className="row" style={{ justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                  <strong className="small">Optimizer Explanation</strong>
                  <span className="small muted">{activeProposal.explanation.map_policy_note}</span>
                </div>
                <p className="muted" style={{ margin: '0 0 0.5rem', fontSize: '0.84rem' }}>
                  {activeProposal.explanation.summary}
                </p>
                <div className="row" style={{ gap: '0.4rem' }}>
                  {activeProposal.explanation.role_notes?.map((note, idx) => (
                    <span key={idx} className="badge">
                      {note}
                    </span>
                  ))}
                  {activeProposal.explanation.constraints_honored?.map((c, idx) => (
                    <span key={idx} className="badge badge-ok">
                      {c}
                    </span>
                  ))}
                  {activeProposal.explanation.manual_only_count > 0 && (
                    <span className="badge badge-warn">
                      <AlertTriangle size={11} /> {activeProposal.explanation.manual_only_count}/10 Manual Baseline Only
                    </span>
                  )}
                </div>
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
                    {activeProposal.alternatives.map((alt, idx) => (
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
                    ))}
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
              <strong>Generate Teams (126 Splits)</strong>. Maps remain random — no map picker is used.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
