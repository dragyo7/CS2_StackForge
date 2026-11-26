import React, { useEffect, useState } from 'react';
import {
  Activity,
  CheckCircle2,
  Database,
  KeyRound,
  RefreshCw,
  Server,
  ShieldAlert,
  Trash2,
  Trophy,
} from 'lucide-react';
import { api, ApiError } from '../api';
import type { CommunityStandingsResponse, OpsOverview } from '../types';

interface Props {
  onRefreshPlayers: () => Promise<void>;
  onOpenProfile: (playerId: string) => void;
  onError: (msg: string) => void;
}

const KEY_GUIDES: Record<
  'steam' | 'faceit' | 'leetify',
  { title: string; optionalNote: string; url: string; steps: string }
> = {
  steam: {
    title: 'Steam Web API Key',
    optionalNote:
      'Optional. Without it, StackForge uses public Steam Community XML (?xml=1) for personas, avatars, and vanity URLs; GetPlayerBans stays NOT_CONFIGURED.',
    url: 'https://steamcommunity.com/dev/apikey',
    steps: 'Sign in with Steam -> register localhost/domain name -> copy key. Stored server-side only (Windows DPAPI vault).',
  },
  faceit: {
    title: 'FACEIT Data API v4 Key',
    optionalNote:
      'Optional. Without it, linked FACEIT levels/ELO still arrive when exposed by Leetify, while direct FACEIT CS2 stats remain NOT_CONFIGURED.',
    url: 'https://developers.faceit.com/',
    steps: 'Create a FACEIT Developer App -> generate a Server-side API Key -> paste here. Never stored in frontend bundles or logs.',
  },
  leetify: {
    title: 'Leetify Developer API Key',
    optionalNote:
      'Optional. Public Leetify CS API v3 already works keyless cleanly; adding a key reduces HTTP 429 rate-limit throttling.',
    url: 'https://leetify.com/app/developer',
    steps: 'Open Leetify Developer Portal -> generate API key -> paste here to send via server-side _leetify_key header.',
  },
};

export const OpsAndSettingsView: React.FC<Props> = ({
  onRefreshPlayers,
  onOpenProfile,
  onError,
}) => {
  const [ops, setOps] = useState<OpsOverview | null>(null);
  const [standings, setStandings] = useState<CommunityStandingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({
    steam: '',
    faceit: '',
    leetify: '',
  });
  const [statusBanner, setStatusBanner] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const [o, st] = await Promise.all([api.opsOverview(), api.communityStandings()]);
      setOps(o);
      setStandings(st);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Failed to load operational telemetry.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRefreshOne = async (playerId: string, name: string) => {
    setBusyKey(`refresh:${playerId}`);
    try {
      const res = await api.refreshPlayerProfile(playerId, false);
      setStatusBanner(`${name}: ${res.status} — ${res.message}`);
      await Promise.all([onRefreshPlayers(), loadData()]);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : `Failed to refresh ${name}.`);
    } finally {
      setBusyKey(null);
    }
  };

  const handleRefreshAll = async () => {
    setBusyKey('refresh_all');
    try {
      const res = await api.refreshAllPlayers(false);
      setStatusBanner(`Refresh All finished (${res.total} players processed).`);
      await Promise.all([onRefreshPlayers(), loadData()]);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Refresh All failed.');
    } finally {
      setBusyKey(null);
    }
  };

  const handleSaveKey = async (provider: 'steam' | 'faceit' | 'leetify', validateLive: boolean) => {
    const val = (keyInputs[provider] || '').trim();
    if (!val) {
      onError(`Enter a ${provider.toUpperCase()} API key first.`);
      return;
    }
    setBusyKey(`key:${provider}`);
    try {
      const res = await api.saveCredential(provider, val, validateLive);
      setKeyInputs((prev) => ({ ...prev, [provider]: '' }));
      const valNote = res.validation ? ` Validation: ${res.validation.status} (${res.validation.message})` : '';
      setStatusBanner(`${provider.toUpperCase()} credential saved (${res.credential.masked_hint || 'configured'}).${valNote}`);
      await loadData();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : `Failed to save ${provider} credential.`);
    } finally {
      setBusyKey(null);
    }
  };

  const handleValidateStored = async (provider: 'steam' | 'faceit' | 'leetify') => {
    setBusyKey(`val:${provider}`);
    try {
      const res = await api.validateCredential(provider);
      setStatusBanner(`${provider.toUpperCase()} check: ${res.status} — ${res.message}`);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : `Validation failed for ${provider}.`);
    } finally {
      setBusyKey(null);
    }
  };

  const handleDeleteKey = async (provider: 'steam' | 'faceit' | 'leetify') => {
    setBusyKey(`del:${provider}`);
    try {
      await api.deleteCredential(provider);
      setStatusBanner(`${provider.toUpperCase()} vault key removed.`);
      await loadData();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : `Could not delete ${provider} key.`);
    } finally {
      setBusyKey(null);
    }
  };

  if (loading || !ops) {
    return (
      <div className="card" style={{ padding: '2rem', textAlign: 'center' }}>
        <p className="muted">Loading operational telemetry &amp; community standings...</p>
      </div>
    );
  }

  return (
    <div className="stack">
      {statusBanner && (
        <div className="alert alert-ok" style={{ justifyContent: 'space-between' }}>
          <span className="small">{statusBanner}</span>
          <button className="btn btn-xs" onClick={() => setStatusBanner(null)}>
            Dismiss
          </button>
        </div>
      )}

      {/* System, Scheduler & Database Health */}
      <div className="card">
        <div className="card-header">
          <div>
            <h2>
              <Server size={18} style={{ verticalAlign: 'text-bottom', marginRight: '0.4rem' }} />
              Operational Health &amp; Data Quality
            </h2>
            <p className="muted small" style={{ margin: '0.2rem 0 0' }}>
              Live database, scheduler, and per-provider ingestion health. Providers are never marked green from config alone.
            </p>
          </div>
          <div className="row">
            <button className="btn btn-sm" disabled={busyKey === 'refresh_all'} onClick={handleRefreshAll}>
              <RefreshCw size={14} /> {busyKey === 'refresh_all' ? 'Refreshing...' : 'Refresh All (TTL-Safe)'}
            </button>
            <button className="btn btn-sm" onClick={loadData}>
              Reload Telemetry
            </button>
          </div>
        </div>

        <div className="cs2-kpi-grid">
          <div className="cs2-kpi">
            <span className="small muted">Backend &amp; SQLite</span>
            <strong className="mono" style={{ color: ops.database.status === 'ok' ? 'var(--ok)' : 'var(--danger)' }}>
              {ops.backend_status.toUpperCase()} / {ops.database.status.toUpperCase()}
            </strong>
            <span className="small muted">
              <Database size={11} style={{ verticalAlign: 'text-bottom' }} /> {ops.database.players_active} active ({ops.database.steam_verified} verified)
            </span>
          </div>
          <div className="cs2-kpi">
            <span className="small muted">Refresh Scheduler</span>
            <strong className="mono" style={{ color: ops.scheduler.status === 'active' ? 'var(--ok)' : 'var(--accent-amber)' }}>
              {ops.scheduler.state.toUpperCase()}
            </strong>
            <span className="small muted">
              Cycles: {ops.scheduler.cycles_completed} • Last: {ops.scheduler.last_cycle_at ? new Date(ops.scheduler.last_cycle_at).toLocaleString() : 'Never'}
            </span>
          </div>
          <div className="cs2-kpi">
            <span className="small muted">Data Freshness &amp; Coverage</span>
            <strong className="mono">
              {ops.stale_players_count} stale • {ops.insufficient_data_count} insufficient
            </strong>
            <span className="small muted">
              Last Full Refresh: {ops.scheduler.last_full_refresh_at ? new Date(ops.scheduler.last_full_refresh_at).toLocaleString() : 'None this session'}
            </span>
          </div>
          <div className="cs2-kpi">
            <span className="small muted">Matches &amp; Demo Queue</span>
            <strong className="mono">
              {ops.database.match_results_recorded} / {ops.database.match_rooms_total} results
            </strong>
            <span className="small muted">Demo queue: {ops.demo_queue.pending_jobs} pending ({ops.demo_queue.status})</span>
          </div>
        </div>
      </div>

      {/* Per-Provider Ingestion Table */}
      <div className="card">
        <h3 style={{ marginBottom: '0.65rem' }}>
          <Activity size={16} style={{ verticalAlign: 'text-bottom', marginRight: '0.35rem' }} />
          Provider Ingestion Matrix
        </h3>
        <div style={{ overflowX: 'auto' }}>
          <table className="standings-table">
            <thead>
              <tr>
                <th>Provider</th>
                <th>Mode</th>
                <th>Health</th>
                <th>Active OK</th>
                <th>Rate Limits</th>
                <th>Private / Unlinked</th>
                <th>Last Success</th>
                <th>Last Failure</th>
              </tr>
            </thead>
            <tbody>
              {ops.providers.map((p) => (
                <tr key={p.provider}>
                  <td><strong>{p.label}</strong></td>
                  <td className="mono small">{p.mode}</td>
                  <td>
                    <span
                      className={`badge ${
                        p.health_state === 'HEALTHY'
                          ? 'badge-ok'
                          : p.health_state === 'PARTIAL_COVERAGE'
                            ? 'badge-warn'
                            : p.health_state === 'NOT_CONFIGURED'
                              ? ''
                              : 'badge-danger'
                      }`}
                    >
                      {p.health_state}
                    </span>
                  </td>
                  <td className="mono">
                    {p.active_players_ok}/{ops.database.players_active} ({p.success_rate_pct}%)
                  </td>
                  <td className="mono">{p.rate_limit_events}</td>
                  <td className="mono">{p.private_or_unlinked_players}</td>
                  <td className="small muted">
                    {p.last_successful_at ? new Date(p.last_successful_at).toLocaleString() : 'Never'}
                  </td>
                  <td className="small muted">
                    {p.last_failed_at ? new Date(p.last_failed_at).toLocaleString() : 'None'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Stale & Insufficient Data Action Lists */}
      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <h4>
              <ShieldAlert size={15} style={{ verticalAlign: 'text-bottom', marginRight: '0.35rem' }} />
              Players With Insufficient Data ({ops.insufficient_data_count})
            </h4>
          </div>
          {ops.insufficient_data_players.length === 0 ? (
            <p className="muted small" style={{ margin: 0 }}>All active players have verified skill ratings or combat samples.</p>
          ) : (
            <div className="stack" style={{ gap: '0.35rem', maxHeight: '260px', overflowY: 'auto' }}>
              {ops.insufficient_data_players.map((pl) => (
                <div key={pl.id} className="player-row" style={{ padding: '0.45rem 0.65rem' }}>
                  <div>
                    <strong style={{ cursor: 'pointer' }} onClick={() => onOpenProfile(pl.id)}>
                      {pl.display_name}
                    </strong>
                    <div className="small muted mono">
                      {pl.steam_id64 || 'No SteamID64'} • {pl.refresh_status}
                    </div>
                  </div>
                  <button
                    className="btn btn-xs btn-primary"
                    disabled={busyKey === `refresh:${pl.id}`}
                    onClick={() => handleRefreshOne(pl.id, pl.display_name)}
                  >
                    <RefreshCw size={11} /> Refresh
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <h4>
              <Trophy size={15} style={{ verticalAlign: 'text-bottom', marginRight: '0.35rem' }} />
              Community Private 5v5 Standings ({standings?.total_matches_recorded || 0} recorded)
            </h4>
          </div>
          <p className="small muted" style={{ marginTop: 0 }}>
            {standings?.separation_note}
          </p>
          {!standings || standings.standings.length === 0 ? (
            <p className="muted small" style={{ margin: 0 }}>
              No post-match results recorded yet. Finalize a 5v5 Match Room and save its post-match score to track private standings.
            </p>
          ) : (
            <div style={{ overflowX: 'auto', maxHeight: '240px' }}>
              <table className="standings-table">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>W-L-T</th>
                    <th>Win%</th>
                    <th>RD</th>
                    <th>Comm Elo</th>
                  </tr>
                </thead>
                <tbody>
                  {standings.standings.map((row) => (
                    <tr key={row.community_player_id}>
                      <td>
                        <strong style={{ cursor: 'pointer' }} onClick={() => onOpenProfile(row.community_player_id)}>
                          {row.display_name}
                        </strong>
                      </td>
                      <td className="mono">{row.wins}-{row.losses}-{row.ties}</td>
                      <td className="mono">{row.win_pct.toFixed(0)}%</td>
                      <td className="mono">{row.round_diff >= 0 ? `+${row.round_diff}` : row.round_diff}</td>
                      <td className="mono">{row.community_internal_rating.toFixed(0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Optional Credentials Vault (Server-Side Only / Windows DPAPI) */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3>
              <KeyRound size={16} style={{ verticalAlign: 'text-bottom', marginRight: '0.35rem' }} />
              Integrations &amp; Optional API Credentials
            </h3>
            <p className="muted small" style={{ margin: '0.2rem 0 0' }}>
              StackForge works in Keyless Mode by default. Optional API keys are encrypted server-side using OS DPAPI and are never returned to the browser.
            </p>
          </div>
          <span className="badge">Keyless Mode Supported</span>
        </div>

        <div className="stack" style={{ gap: '0.75rem' }}>
          {ops.credentials.map((cred) => {
            const guide = KEY_GUIDES[cred.provider];
            return (
              <div key={cred.provider} className="card" style={{ background: 'var(--bg-canvas)' }}>
                <div className="row" style={{ justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                  <div className="row">
                    <strong>{guide.title}</strong>
                    <span className={`badge ${cred.configured ? 'badge-ok' : ''}`}>
                      {cred.configured ? `Connected (${cred.masked_hint || cred.source})` : 'Not Configured'}
                    </span>
                  </div>
                  <a className="small" href={guide.url} target="_blank" rel="noreferrer">
                    Official Key Portal ↗
                  </a>
                </div>
                <p className="small muted" style={{ margin: '0 0 0.35rem' }}>
                  {guide.optionalNote}
                </p>
                <p className="small muted" style={{ margin: '0 0 0.55rem' }}>
                  Setup: {guide.steps}
                </p>
                <div className="row" style={{ gap: '0.45rem', flexWrap: 'wrap' }}>
                  <input
                    className="input"
                    type="password"
                    autoComplete="off"
                    style={{ maxWidth: '320px' }}
                    placeholder={`Enter optional ${cred.env_var}...`}
                    value={keyInputs[cred.provider] || ''}
                    onChange={(e) => setKeyInputs((prev) => ({ ...prev, [cred.provider]: e.target.value }))}
                  />
                  <button
                    className="btn btn-sm btn-primary"
                    disabled={busyKey === `key:${cred.provider}`}
                    onClick={() => handleSaveKey(cred.provider, false)}
                  >
                    <CheckCircle2 size={13} /> Save Key
                  </button>
                  <button
                    className="btn btn-sm"
                    disabled={busyKey === `key:${cred.provider}`}
                    onClick={() => handleSaveKey(cred.provider, true)}
                  >
                    Save &amp; Validate
                  </button>
                  {cred.configured && (
                    <>
                      <button
                        className="btn btn-sm"
                        disabled={busyKey === `val:${cred.provider}`}
                        onClick={() => handleValidateStored(cred.provider)}
                      >
                        Validate Stored
                      </button>
                      <button
                        className="btn btn-sm btn-danger"
                        disabled={busyKey === `del:${cred.provider}`}
                        onClick={() => handleDeleteKey(cred.provider)}
                      >
                        <Trash2 size={13} /> Remove
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
