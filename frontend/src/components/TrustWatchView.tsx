import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  ExternalLink,
  Eye,
  RefreshCw,
  Shield,
  ShieldAlert,
  XCircle,
} from 'lucide-react';
import { api, ApiError } from '../api';
import type { Player, TrustOverview } from '../types';

interface Props {
  players: Player[];
  onOpenProfile: (playerId: string) => void;
  onError: (msg: string) => void;
}

export const TrustWatchView: React.FC<Props> = ({ players, onOpenProfile, onError }) => {
  const [overview, setOverview] = useState<TrustOverview | null>(null);
  const [selectedPlayerId, setSelectedPlayerId] = useState('');
  const [watchReason, setWatchReason] = useState('');
  const [watchSource, setWatchSource] = useState('');
  const [checkTargetId, setCheckTargetId] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      setOverview(await api.trustOverview());
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Failed to load Trust & Account Watch.');
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleRunCheck = async () => {
    const pid = checkTargetId || players.find((p) => p.steam_id64)?.id;
    if (!pid) return;
    setBusy(true);
    try {
      await api.runTrustCheck(pid);
      await load();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Trust check failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleAddWatch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPlayerId || !watchReason.trim()) return;
    setBusy(true);
    try {
      const updated = await api.addWatchlist(selectedPlayerId, watchReason.trim(), watchSource.trim());
      setOverview(updated);
      setWatchReason('');
      setWatchSource('');
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Could not add watchlist entry.');
    } finally {
      setBusy(false);
    }
  };

  const handleReview = async (entryId: string, status: 'REVIEWED' | 'DISMISSED') => {
    setBusy(true);
    try {
      const updated = await api.reviewWatchlist(entryId, status);
      setOverview(updated);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Review update failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleRefreshWatched = async () => {
    setBusy(true);
    try {
      const res = await api.refreshWatched();
      setOverview(res.overview);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Watched refresh failed.');
    } finally {
      setBusy(false);
    }
  };

  const steamPlayers = players.filter((p) => Boolean(p.steam_id64));

  return (
    <div className="stack">
      <div className="card">
        <div className="card-header">
          <div>
            <h2>Trust & Account Watch</h2>
            <p className="muted small" style={{ margin: '0.2rem 0 0' }}>
              Separates Official Enforcement, Third-Party Reputation (CSWatch), Community Reports, and Human Review.
              No ban record does not prove clean; a Steam game-ban count alone is not proof of CS2 cheating.
            </p>
          </div>
          <div className="row">
            <select
              className="select"
              style={{ width: '200px' }}
              value={checkTargetId}
              onChange={(e) => setCheckTargetId(e.target.value)}
            >
              <option value="">Select SteamID player...</option>
              {steamPlayers.map((p) => (
                <option key={p.id} value={p.id}>{p.display_name}</option>
              ))}
            </select>
            <button
              className="btn btn-primary btn-sm"
              disabled={busy || steamPlayers.length === 0}
              onClick={handleRunCheck}
            >
              <Shield size={14} /> Run Trust Check
            </button>
            <button className="btn btn-sm" disabled={busy} onClick={handleRefreshWatched}>
              <RefreshCw size={14} /> Refresh Watched
            </button>
          </div>
        </div>
      </div>

      <div className="grid-2">
        {/* Private Watchlist */}
        <div className="card">
          <h3 style={{ marginBottom: '0.65rem' }}>
            <Eye size={16} style={{ verticalAlign: 'text-bottom', marginRight: '0.35rem' }} />
            Private Community Watchlist ({overview?.watchlist.length || 0})
          </h3>
          <form onSubmit={handleAddWatch} className="stack" style={{ gap: '0.45rem', marginBottom: '0.85rem' }}>
            <div className="row">
              <select
                className="select"
                style={{ flex: 1 }}
                value={selectedPlayerId}
                onChange={(e) => setSelectedPlayerId(e.target.value)}
              >
                <option value="">Select player to watch...</option>
                {players.map((p) => (
                  <option key={p.id} value={p.id}>{p.display_name}</option>
                ))}
              </select>
            </div>
            <input
              className="input"
              placeholder="Reason or observation (private to community moderators)..."
              value={watchReason}
              onChange={(e) => setWatchReason(e.target.value)}
            />
            <div className="row">
              <input
                className="input mono"
                style={{ flex: 1 }}
                placeholder="Optional evidence / match URL"
                value={watchSource}
                onChange={(e) => setWatchSource(e.target.value)}
              />
              <button
                type="submit"
                className="btn btn-sm btn-primary"
                disabled={busy || !selectedPlayerId || !watchReason.trim()}
              >
                Add Entry
              </button>
            </div>
          </form>

          {!overview || overview.watchlist.length === 0 ? (
            <p className="muted small" style={{ margin: 0 }}>
              No active watchlist entries. Add a concern above to track and review privately.
            </p>
          ) : (
            <div className="stack" style={{ gap: '0.45rem' }}>
              {overview.watchlist.map((w) => (
                <div key={w.id} className="player-row" style={{ alignItems: 'flex-start' }}>
                  <div style={{ minWidth: 0 }}>
                    <div className="row" style={{ gap: '0.35rem' }}>
                      <strong
                        style={{ cursor: w.community_player_id ? 'pointer' : 'default' }}
                        onClick={() => w.community_player_id && onOpenProfile(w.community_player_id)}
                      >
                        {w.display_name}
                      </strong>
                      <span
                        className={`badge ${
                          w.status === 'DISMISSED'
                            ? 'badge-ok'
                            : w.status === 'REVIEWED'
                              ? 'badge-a'
                              : 'badge-warn'
                        }`}
                      >
                        {w.status}
                      </span>
                    </div>
                    <div className="small muted" style={{ marginTop: '0.2rem' }}>{w.reason}</div>
                    {w.source_url && (
                      <a className="small" href={w.source_url} target="_blank" rel="noreferrer">
                        Evidence Link <ExternalLink size={11} />
                      </a>
                    )}
                  </div>
                  {w.status === 'WATCHING' && (
                    <div className="row" style={{ gap: '0.25rem' }}>
                      <button
                        className="btn btn-xs"
                        onClick={() => handleReview(w.id, 'REVIEWED')}
                        title="Mark reviewed"
                      >
                        <CheckCircle2 size={12} /> Reviewed
                      </button>
                      <button
                        className="btn btn-xs btn-ok"
                        onClick={() => handleReview(w.id, 'DISMISSED')}
                        title="Dismiss concern"
                      >
                        <XCircle size={12} /> Dismiss
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Separated Evidence Feed + Activity Feed */}
        <div className="stack">
          <div className="card">
            <h3 style={{ marginBottom: '0.65rem' }}>
              <ShieldAlert size={16} style={{ verticalAlign: 'text-bottom', marginRight: '0.35rem' }} />
              Separated Evidence Signals ({overview?.signals.length || 0})
            </h3>
            {!overview || overview.signals.length === 0 ? (
              <p className="muted small" style={{ margin: 0 }}>
                No trust signals recorded yet. Select a SteamID64 player above and click Run Trust Check.
              </p>
            ) : (
              <div className="stack" style={{ gap: '0.45rem', maxHeight: '360px', overflowY: 'auto' }}>
                {overview.signals.map((s) => (
                  <div key={s.id} className="player-row" style={{ alignItems: 'flex-start' }}>
                    <div style={{ minWidth: 0 }}>
                      <div className="row" style={{ gap: '0.35rem' }}>
                        <strong className="small">{s.display_name}</strong>
                        <span className="badge">{s.category}</span>
                        <span className="badge">{s.provider}</span>
                        <span
                          className={`badge ${
                            s.status === 'OK' || s.status === 'DISMISSED'
                              ? 'badge-ok'
                              : s.status === 'FLAGGED'
                                ? 'badge-danger'
                                : 'badge-warn'
                          }`}
                        >
                          {s.status}
                        </span>
                      </div>
                      <div className="small" style={{ marginTop: '0.2rem' }}>{s.summary}</div>
                      {s.limitations && (
                        <div className="small muted" style={{ marginTop: '0.15rem' }}>
                          <AlertTriangle size={11} style={{ verticalAlign: 'text-bottom', marginRight: '0.2rem' }} />
                          {s.limitations}
                        </div>
                      )}
                    </div>
                    {s.source_url && (
                      <a className="btn btn-xs" href={s.source_url} target="_blank" rel="noreferrer">
                        Source
                      </a>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <h4 style={{ marginBottom: '0.55rem' }}>
              <Bell size={15} style={{ verticalAlign: 'text-bottom', marginRight: '0.35rem' }} />
              Community Activity Feed
            </h4>
            {!overview || overview.activity.length === 0 ? (
              <p className="muted small" style={{ margin: 0 }}>No recent community activity events.</p>
            ) : (
              <div className="stack" style={{ gap: '0.35rem', maxHeight: '220px', overflowY: 'auto' }}>
                {overview.activity.map((a) => (
                  <div key={a.id} className="player-row" style={{ padding: '0.4rem 0.6rem' }}>
                    <div>
                      <strong className="small">{a.title}</strong>
                      <div className="small muted">{a.detail}</div>
                    </div>
                    <span className="small muted">{new Date(a.created_at).toLocaleTimeString()}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
