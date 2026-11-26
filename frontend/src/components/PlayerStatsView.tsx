import React, { useEffect, useState } from 'react';
import {
  Activity,
  ArrowLeftRight,
  Clock,
  ExternalLink,
  History,
  Lock,
  Plus,
  RefreshCw,
  Search,
  Shield,
} from 'lucide-react';
import { api, ApiError } from '../api';
import type { Player, PlayerCompare, PlayerProfile, StatSnapshot } from '../types';
import { PlayerAvatar } from './PlayerAvatar';
import { PlayerCardTile } from './PlayerCardTile';

interface Props {
  players: Player[];
  selectedPlayerId: string | null;
  onSelectPlayerId: (id: string) => void;
  onRefreshPlayers: () => Promise<void>;
  onError: (msg: string) => void;
}

const METRIC_LABELS: { key: keyof StatSnapshot; label: string; suffix?: string; decimals?: number }[] = [
  { key: 'matches_played', label: 'Matches Played', decimals: 0 },
  { key: 'win_rate', label: 'Win Rate', suffix: '%', decimals: 1 },
  { key: 'kd_ratio', label: 'K/D Ratio', decimals: 2 },
  { key: 'adr', label: 'ADR', decimals: 1 },
  { key: 'aim_rating', label: 'Aim Rating', decimals: 1 },
  { key: 'utility_rating', label: 'Utility Rating', decimals: 1 },
  { key: 'preaim', label: 'Pre-aim (°)', suffix: '°', decimals: 2 },
  { key: 'reaction_time_ms', label: 'Time to Damage', suffix: ' ms', decimals: 0 },
  { key: 'spotted_accuracy', label: 'Spotted Acc', suffix: '%', decimals: 1 },
  { key: 'spray_accuracy', label: 'Spray Acc', suffix: '%', decimals: 1 },
  { key: 'kast', label: 'KAST', suffix: '%', decimals: 1 },
  { key: 'hs_pct', label: 'Headshot %', suffix: '%', decimals: 1 },
  { key: 'opening_duel_pct', label: 'Opening Duel %', suffix: '%', decimals: 1 },
  { key: 'trade_kills_per_match', label: 'Trade Kills %', suffix: '%', decimals: 1 },
  { key: 'utility_damage_per_round', label: 'Utility Dmg / Rd', decimals: 1 },
  { key: 'flash_assists_per_round', label: 'Flash Assists / Rd', decimals: 2 },
  { key: 'enemies_flashed_per_round', label: 'Enemies Flashed / Rd', decimals: 2 },
  { key: 'clutch_win_pct', label: 'Clutch Win %', suffix: '%', decimals: 1 },
  { key: 'consistency_score', label: 'Counter-Strafe %', suffix: '%', decimals: 1 },
];

export const PlayerStatsView: React.FC<Props> = ({
  players,
  selectedPlayerId,
  onSelectPlayerId,
  onRefreshPlayers,
  onError,
}) => {
  const [mode, setMode] = useState<'profile' | 'compare'>('profile');
  const [search, setSearch] = useState('');
  const [providerFilter, setProviderFilter] = useState<string>('all');
  const [scopeFilter, setScopeFilter] = useState<string>('all');
  const [profile, setProfile] = useState<PlayerProfile | null>(null);
  const [refreshProvider, setRefreshProvider] = useState<string>('all');
  const [refreshResult, setRefreshResult] = useState<{ text: string; status: string; providers?: { provider: string; status: string; summary: string; cache_hit?: boolean }[] } | null>(null);
  const [busy, setBusy] = useState(false);

  // Compare state
  const [compareA, setCompareA] = useState<string>(selectedPlayerId || '');
  const [compareB, setCompareB] = useState<string>('');
  const [compareData, setCompareData] = useState<PlayerCompare | null>(null);

  // Log community match stats modal/panel
  const [showAddStat, setShowAddStat] = useState(false);
  const [statMatches, setStatMatches] = useState('10');
  const [statWinRate, setStatWinRate] = useState('');
  const [statKd, setStatKd] = useState('');
  const [statAdr, setStatAdr] = useState('');
  const [statKast, setStatKast] = useState('');
  const [statHs, setStatHs] = useState('');
  const [statOpen, setStatOpen] = useState('');
  const [statUtil, setStatUtil] = useState('');
  const [statFlash, setStatFlash] = useState('');
  const [statClutch, setStatClutch] = useState('');

  const activeId = selectedPlayerId || players[0]?.id || null;

  useEffect(() => {
    if (!activeId) {
      setProfile(null);
      return;
    }
    let cancelled = false;
    setRefreshResult(null);
    api
      .getPlayerProfile(activeId)
      .then((res) => {
        if (!cancelled) setProfile(res);
      })
      .catch((err) => {
        if (!cancelled) onError(err instanceof ApiError ? err.message : 'Failed to load profile.');
      });
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  useEffect(() => {
    if (!compareA && players[0]) setCompareA(players[0].id);
    if (!compareB && players[1]) setCompareB(players[1].id);
  }, [players]);

  useEffect(() => {
    if (mode !== 'compare' || !compareA || !compareB) return;
    let cancelled = false;
    api
      .comparePlayers(compareA, compareB)
      .then((res) => {
        if (!cancelled) setCompareData(res);
      })
      .catch((err) => {
        if (!cancelled) onError(err instanceof ApiError ? err.message : 'Comparison failed.');
      });
    return () => {
      cancelled = true;
    };
  }, [mode, compareA, compareB]);

  const handleRefreshProfile = async (force: boolean) => {
    if (!activeId) return;
    setBusy(true);
    try {
      const res = await api.refreshPlayerProfile(activeId, force, refreshProvider);
      setProfile(res.profile);
      setRefreshResult({
        text: res.message,
        status: res.status || res.profile.player.refresh_status,
        providers: res.provider_results,
      });
      await onRefreshPlayers();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Profile refresh failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleAddStat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeId) return;
    setBusy(true);
    try {
      const updated = await api.addStatSnapshot(activeId, {
        provider: 'community_match',
        scope: 'recent',
        sample_size: statMatches ? Number(statMatches) : null,
        matches_played: statMatches ? Number(statMatches) : null,
        win_rate: statWinRate ? Number(statWinRate) : null,
        kd_ratio: statKd ? Number(statKd) : null,
        adr: statAdr ? Number(statAdr) : null,
        kast: statKast ? Number(statKast) : null,
        hs_pct: statHs ? Number(statHs) : null,
        opening_duel_pct: statOpen ? Number(statOpen) : null,
        utility_damage_per_round: statUtil ? Number(statUtil) : null,
        flash_assists_per_round: statFlash ? Number(statFlash) : null,
        clutch_win_pct: statClutch ? Number(statClutch) : null,
      });
      setProfile(updated);
      setShowAddStat(false);
      await onRefreshPlayers();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Could not save stat snapshot.');
    } finally {
      setBusy(false);
    }
  };

  const handleVisibilityChange = async (vis: 'COMMUNITY' | 'HOST_ONLY') => {
    if (!activeId) return;
    setBusy(true);
    try {
      const updated = await api.updateCardSettings(activeId, { stats_visibility: vis });
      setProfile(updated);
      await onRefreshPlayers();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Could not update visibility.');
    } finally {
      setBusy(false);
    }
  };

  const filteredPlayers = players.filter((p) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    const aliasHit = p.aliases.some(
      (a) => a.alias_name.toLowerCase().includes(q) || (a.previous_name && a.previous_name.toLowerCase().includes(q)),
    );
    return (
      p.display_name.toLowerCase().includes(q) ||
      (p.steam_id64 && p.steam_id64.includes(q)) ||
      (p.steam_persona_name && p.steam_persona_name.toLowerCase().includes(q)) ||
      aliasHit
    );
  });

  const filteredSnapshots = (profile?.stat_snapshots || []).filter((s) => {
    if (providerFilter !== 'all' && s.provider !== providerFilter) return false;
    if (scopeFilter !== 'all' && s.scope !== scopeFilter) return false;
    return true;
  });

  const renderMetricRow = (label: string, valA: number | null | undefined, valB: number | null | undefined, maxRef: number, suffix = '', decimals = 1) => {
    const pctA = valA != null ? Math.min(100, Math.max(4, (valA / maxRef) * 100)) : 0;
    const pctB = valB != null ? Math.min(100, Math.max(4, (valB / maxRef) * 100)) : 0;
    return (
      <div key={label} style={{ padding: '0.45rem 0', borderBottom: '1px solid var(--border)' }}>
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: '0.3rem' }}>
          <strong className="mono small" style={{ color: 'var(--team-a)' }}>
            {valA != null ? `${valA.toFixed(decimals)}${suffix}` : 'Unavailable'}
          </strong>
          <span className="small muted">{label}</span>
          <strong className="mono small" style={{ color: 'var(--team-b)' }}>
            {valB != null ? `${valB.toFixed(decimals)}${suffix}` : 'Unavailable'}
          </strong>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem', alignItems: 'center' }}>
          <div style={{ display: 'flex', justifyContent: 'flex-end', background: 'var(--bg-canvas)', height: '7px', borderRadius: '4px', overflow: 'hidden' }}>
            <div style={{ width: `${pctA}%`, background: 'var(--team-a)', height: '100%' }} />
          </div>
          <div style={{ background: 'var(--bg-canvas)', height: '7px', borderRadius: '4px', overflow: 'hidden' }}>
            <div style={{ width: `${pctB}%`, background: 'var(--team-b)', height: '100%' }} />
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="stack">
      <div className="card">
        <div className="card-header" style={{ marginBottom: 0 }}>
          <div>
            <h2>Player Stats & Intelligence</h2>
            <p className="muted" style={{ margin: '0.2rem 0 0' }}>
              Canonical SteamID64 identities, alias timelines, source-qualified combat stats, and side-by-side comparison.
            </p>
          </div>
          <div className="nav-tabs">
            <button className={`nav-tab ${mode === 'profile' ? 'active' : ''}`} onClick={() => setMode('profile')}>
              <Activity size={14} /> Player Profile
            </button>
            <button className={`nav-tab ${mode === 'compare' ? 'active' : ''}`} onClick={() => setMode('compare')}>
              <ArrowLeftRight size={14} /> Compare Players
            </button>
          </div>
        </div>
      </div>

      {players.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '2.5rem' }}>
          <p className="muted">No players registered yet. Add players or load Demo 10 in the Players or Match Room tab.</p>
        </div>
      ) : mode === 'compare' ? (
        <div className="card">
          <div className="grid-2" style={{ marginBottom: '1rem' }}>
            <div>
              <label className="field-label">Player A (Blue)</label>
              <select className="select" value={compareA} onChange={(e) => setCompareA(e.target.value)}>
                {players.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name} ({p.normalized_strength != null ? p.normalized_strength.toFixed(1) : 'Unranked'} • {p.primary_role || 'Flex'})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="field-label">Player B (Amber)</label>
              <select className="select" value={compareB} onChange={(e) => setCompareB(e.target.value)}>
                {players.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name} ({p.normalized_strength != null ? p.normalized_strength.toFixed(1) : 'Unranked'} • {p.primary_role || 'Flex'})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {compareData && (
            <div className="stack">
              <div className="grid-2">
                <div className="team-panel team-a">
                  <div className="row" style={{ gap: '0.6rem' }}>
                    <PlayerAvatar
                      name={compareData.player_a.player.display_name}
                      avatarUrl={compareData.player_a.player.avatar_url}
                      role={compareData.player_a.player.primary_role}
                      size={40}
                    />
                    <div>
                      <strong>{compareData.player_a.player.display_name}</strong>
                      <div className="small muted">
                        {compareData.player_a.card.primary_title} • Conf{' '}
                        {Math.round(compareData.player_a.player.confidence * 100)}%
                      </div>
                    </div>
                  </div>
                </div>
                <div className="team-panel team-b">
                  <div className="row" style={{ gap: '0.6rem' }}>
                    <PlayerAvatar
                      name={compareData.player_b.player.display_name}
                      avatarUrl={compareData.player_b.player.avatar_url}
                      role={compareData.player_b.player.primary_role}
                      size={40}
                    />
                    <div>
                      <strong>{compareData.player_b.player.display_name}</strong>
                      <div className="small muted">
                        {compareData.player_b.card.primary_title} • Conf{' '}
                        {Math.round(compareData.player_b.player.confidence * 100)}%
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="card" style={{ background: 'var(--bg-elevated)' }}>
                <p className="small muted" style={{ margin: '0 0 0.6rem' }}>
                  Normalized competitive strength uses verified CS2 ratings &amp; stats only (<code>norm_v2</code>). Missing metrics display Unavailable (never zero).
                </p>
                {renderMetricRow(
                  'Normalized Strength (0-100)',
                  compareData.player_a.player.normalized_strength,
                  compareData.player_b.player.normalized_strength,
                  100,
                )}
                {renderMetricRow(
                  'Aim Rating (Leetify)',
                  compareData.player_a.player.aim_rating,
                  compareData.player_b.player.aim_rating,
                  100,
                )}
                {renderMetricRow(
                  'Utility Rating (Leetify)',
                  compareData.player_a.player.utility_rating,
                  compareData.player_b.player.utility_rating,
                  100,
                )}
                {renderMetricRow(
                  'Win Rate (latest source)',
                  compareData.player_a.stat_snapshots[0]?.win_rate,
                  compareData.player_b.stat_snapshots[0]?.win_rate,
                  100,
                  '%',
                )}
                {renderMetricRow(
                  'ADR (latest source)',
                  compareData.player_a.stat_snapshots[0]?.adr,
                  compareData.player_b.stat_snapshots[0]?.adr,
                  120,
                )}
                {renderMetricRow(
                  'K/D Ratio (latest source)',
                  compareData.player_a.stat_snapshots[0]?.kd_ratio,
                  compareData.player_b.stat_snapshots[0]?.kd_ratio,
                  2.0,
                  '',
                  2,
                )}
                {renderMetricRow(
                  'KAST % (latest source)',
                  compareData.player_a.stat_snapshots[0]?.kast,
                  compareData.player_b.stat_snapshots[0]?.kast,
                  100,
                  '%',
                )}
                {renderMetricRow(
                  'Clutch Win % (latest source)',
                  compareData.player_a.stat_snapshots[0]?.clutch_win_pct,
                  compareData.player_b.stat_snapshots[0]?.clutch_win_pct,
                  50,
                  '%',
                )}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="room-layout">
          {/* Left Player Selector */}
          <div className="card">
            <div style={{ position: 'relative', marginBottom: '0.6rem' }}>
              <Search
                size={14}
                style={{ position: 'absolute', left: '0.65rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
              />
              <input
                className="input"
                style={{ paddingLeft: '2rem' }}
                placeholder="Search current name, alias, SteamID64..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="stack" style={{ gap: '0.4rem', maxHeight: '620px', overflowY: 'auto' }}>
              {filteredPlayers.map((p) => (
                <div
                  key={p.id}
                  className={`player-row ${p.id === activeId ? 'selected' : ''}`}
                  style={{ cursor: 'pointer' }}
                  onClick={() => onSelectPlayerId(p.id)}
                >
                  <div className="row" style={{ gap: '0.55rem', minWidth: 0 }}>
                    <PlayerAvatar name={p.display_name} avatarUrl={p.avatar_url} role={p.primary_role} size={32} />
                    <div style={{ minWidth: 0 }}>
                      <div className="row" style={{ gap: '0.35rem' }}>
                        <strong className="small">{p.display_name}</strong>
                        {p.primary_role && <span className="badge">{p.primary_role}</span>}
                      </div>
                      <div className="small muted mono">
                        {p.normalized_strength != null ? `Str ${p.normalized_strength.toFixed(1)}` : 'Insufficient Data'}
                        {p.aliases.length > 0 ? ` • ${p.aliases.length} alias` : ''}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right Profile View */}
          {profile && (
            <div className="stack">
              <div className="card">
                <div className="card-header">
                  <div className="row" style={{ gap: '0.75rem' }}>
                    <PlayerAvatar
                      name={profile.player.display_name}
                      avatarUrl={profile.player.avatar_url}
                      role={profile.player.primary_role}
                      size={52}
                    />
                    <div>
                      <div className="row" style={{ gap: '0.45rem' }}>
                        <h2>{profile.player.display_name}</h2>
                        {profile.player.primary_role && <span className="badge">{profile.player.primary_role}</span>}
                        <span className={`badge ${profile.player.steam_id64 ? 'badge-ok' : 'badge-warn'}`}>
                          {profile.player.identity_status}
                        </span>
                      </div>
                      <div className="small muted mono" style={{ marginTop: '0.2rem' }}>
                        {profile.player.steam_id64
                          ? `Canonical SteamID64: ${profile.player.steam_id64}`
                          : 'Manual-only profile (no SteamID64 linked)'}
                        {profile.player.steam_persona_name &&
                          ` • Steam Name: ${profile.player.steam_persona_name}`}
                      </div>
                      <div className="small muted" style={{ marginTop: '0.15rem' }}>
                        <Clock size={12} style={{ verticalAlign: 'text-bottom', marginRight: '0.25rem' }} />
                        Last updated:{' '}
                        {profile.player.last_successful_refresh_at
                          ? new Date(profile.player.last_successful_refresh_at).toLocaleString()
                          : 'Never refreshed from Steam'}{' '}
                        • Status: <strong>{profile.player.refresh_status}</strong>
                      </div>
                    </div>
                  </div>

                  <div className="row">
                    {profile.player.steam_profile_url && (
                      <a
                        className="btn btn-sm"
                        href={profile.player.steam_profile_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <ExternalLink size={13} /> Steam
                      </a>
                    )}
                    {profile.external_identities.map((ext) =>
                      ext.profile_url ? (
                        <a
                          key={ext.id}
                          className="btn btn-sm"
                          href={ext.profile_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <ExternalLink size={13} /> {ext.provider}
                        </a>
                      ) : null,
                    )}
                    <select
                      className="select"
                      style={{ width: 'auto', padding: '0.3rem 0.5rem', fontSize: '0.78rem' }}
                      value={refreshProvider}
                      onChange={(e) => setRefreshProvider(e.target.value)}
                      title="Select provider scope for individual refresh"
                    >
                      <option value="all">All Providers</option>
                      <option value="steam">Steam Only</option>
                      <option value="leetify">Leetify Only</option>
                      <option value="faceit">FACEIT Only</option>
                      <option value="cswatch">CSWatch Only</option>
                    </select>
                    <button className="btn btn-sm" disabled={busy} onClick={() => handleRefreshProfile(false)}>
                      <RefreshCw size={13} /> Refresh
                    </button>
                    <button className="btn btn-sm btn-primary" disabled={busy} onClick={() => handleRefreshProfile(true)}>
                      Force Refresh
                    </button>
                  </div>
                </div>

                {refreshResult && (
                  <div
                    className={`alert ${
                      refreshResult.status === 'SUCCESS' || refreshResult.status === 'OK' ? 'alert-ok' : 'alert-warn'
                    }`}
                    style={{ marginBottom: '0.75rem', padding: '0.55rem 0.75rem', flexDirection: 'column', alignItems: 'stretch', gap: '0.35rem' }}
                  >
                    <div className="row" style={{ justifyContent: 'space-between' }}>
                      <span className="small">
                        <strong>[{refreshResult.status}]</strong> {refreshResult.text}
                      </span>
                      <button className="btn btn-xs" onClick={() => setRefreshResult(null)}>
                        OK
                      </button>
                    </div>
                    {refreshResult.providers && refreshResult.providers.length > 0 && (
                      <div className="row" style={{ gap: '0.35rem', flexWrap: 'wrap' }}>
                        {refreshResult.providers.map((pr) => (
                          <span
                            key={pr.provider}
                            className={`badge ${pr.status === 'SUCCESS' ? 'badge-ok' : pr.status === 'FAILED' ? 'badge-danger' : 'badge-warn'}`}
                            title={pr.summary}
                          >
                            {pr.provider}: {pr.status}{pr.cache_hit ? ' (cache)' : ''}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Competitive Profile Scales (Distinct, never combined blindly) */}
                <div className="cs2-kpi-grid">
                  <div className="cs2-kpi">
                    <span className="small muted">Competitive Rank Strength</span>
                    <strong className="mono" style={{ color: 'var(--accent-amber)', fontSize: '1.25rem' }}>
                      {profile.player.normalized_strength != null ? profile.player.normalized_strength.toFixed(1) : 'Unavailable'}
                    </strong>
                    <span className="small muted">
                      {profile.player.strength_band} • Conf {Math.round(profile.player.confidence * 100)}%
                    </span>
                  </div>
                  <div className="cs2-kpi">
                    <span className="small muted">Premier CSR</span>
                    <strong className="mono">
                      {profile.player.premier_rating != null
                        ? profile.player.premier_rating.toLocaleString()
                        : 'Unavailable'}
                    </strong>
                    <span className="small muted">{profile.player.premier_source || 'No source'}</span>
                  </div>
                  <div className="cs2-kpi">
                    <span className="small muted">Leetify Rating</span>
                    <strong className="mono">
                      {profile.player.leetify_rating != null
                        ? `${profile.player.leetify_rating >= 0 ? '+' : ''}${profile.player.leetify_rating.toFixed(2)}`
                        : 'Unavailable'}
                    </strong>
                    <span className="small muted">Leetify Public v3</span>
                  </div>
                  <div className="cs2-kpi">
                    <span className="small muted">FACEIT ELO &amp; Level</span>
                    <strong className="mono">
                      {profile.player.faceit_elo != null
                        ? `${profile.player.faceit_elo}${profile.player.faceit_level ? ` (Lv ${profile.player.faceit_level})` : ''}`
                        : 'Unavailable'}
                    </strong>
                    <span className="small muted">FACEIT scale</span>
                  </div>
                </div>

                {/* Mechanical & Utility Summary Row */}
                <div className="cs2-kpi-grid" style={{ marginTop: '0.6rem' }}>
                  <div className="cs2-kpi">
                    <span className="small muted">Aim Rating</span>
                    <strong className="mono">
                      {profile.player.aim_rating != null ? profile.player.aim_rating.toFixed(1) : 'Unavailable'}
                    </strong>
                    <span className="small muted">Leetify Mechanics</span>
                  </div>
                  <div className="cs2-kpi">
                    <span className="small muted">Utility Rating</span>
                    <strong className="mono">
                      {profile.player.utility_rating != null ? profile.player.utility_rating.toFixed(1) : 'Unavailable'}
                    </strong>
                    <span className="small muted">Leetify Utility</span>
                  </div>
                  <div className="cs2-kpi">
                    <span className="small muted">Pre-aim / Reaction</span>
                    <strong className="mono">
                      {profile.player.latest_stats?.preaim != null ? `${profile.player.latest_stats.preaim.toFixed(1)}°` : 'Unavailable'}
                      {profile.player.latest_stats?.reaction_time_ms != null ? ` • ${Math.round(profile.player.latest_stats.reaction_time_ms)}ms` : ''}
                    </strong>
                    <span className="small muted">From available samples</span>
                  </div>
                  <div className="cs2-kpi">
                    <span className="small muted">Data Coverage</span>
                    <strong className="mono">{Math.round(profile.player.confidence * 100)}%</strong>
                    <span className="small muted">{profile.player.data_status || profile.player.strength_band}</span>
                  </div>
                </div>
              </div>

              {/* CS2 Player Card */}
              <PlayerCardTile
                player={profile.player}
                card={profile.card}
                onProfileUpdated={(updated) => {
                  setProfile(updated);
                  onRefreshPlayers();
                }}
                onError={onError}
              />

              {/* Alias History + Provider Availability */}
              <div className="grid-2">
                <div className="card">
                  <h4 style={{ marginBottom: '0.55rem' }}>
                    <History size={15} style={{ verticalAlign: 'text-bottom', marginRight: '0.35rem' }} />
                    Username & Alias History ({profile.aliases.length})
                  </h4>
                  {profile.aliases.length === 0 ? (
                    <p className="muted small" style={{ margin: 0 }}>
                      No alias changes observed yet. Refreshing Steam after a username change preserves previous names automatically.
                    </p>
                  ) : (
                    <div className="stack" style={{ gap: '0.4rem' }}>
                      {profile.aliases.map((al) => (
                        <div key={al.id} className="player-row" style={{ padding: '0.45rem 0.6rem' }}>
                          <div>
                            <div className="small">
                              {al.previous_name ? (
                                <>
                                  <span className="muted">{al.previous_name}</span> →{' '}
                                  <strong>{al.alias_name}</strong>
                                </>
                              ) : (
                                <strong>{al.alias_name}</strong>
                              )}
                            </div>
                            <div className="small muted">
                              {al.source} • {new Date(al.observed_at).toLocaleString()}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="card">
                  <div className="card-header" style={{ marginBottom: '0.5rem' }}>
                    <h4>
                      <Shield size={15} style={{ verticalAlign: 'text-bottom', marginRight: '0.35rem' }} />
                      Provider & Visibility
                    </h4>
                    <select
                      className="select"
                      style={{ width: 'auto', padding: '0.2rem 0.45rem', fontSize: '0.74rem' }}
                      value={profile.player.stats_visibility}
                      onChange={(e) => handleVisibilityChange(e.target.value as 'COMMUNITY' | 'HOST_ONLY')}
                    >
                      <option value="COMMUNITY">Visible to Community</option>
                      <option value="HOST_ONLY">Host-Only Notes/Stats</option>
                    </select>
                  </div>
                  {profile.provider_statuses.length === 0 ? (
                    <p className="muted small">No provider checks run yet. Click Refresh above.</p>
                  ) : (
                    <div className="stack" style={{ gap: '0.35rem' }}>
                      {profile.provider_statuses.map((ps) => (
                        <div key={ps.provider} className="player-row" style={{ padding: '0.4rem 0.6rem' }}>
                          <div>
                            <strong className="small">{ps.provider}</strong>
                            <div className="small muted">{ps.summary}</div>
                          </div>
                          <span className={`badge ${ps.status === 'OK' ? 'badge-ok' : ps.status === 'FLAGGED' ? 'badge-danger' : ''}`}>
                            {ps.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  {profile.player.notes && (
                    <div className="small muted" style={{ marginTop: '0.6rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border)' }}>
                      <Lock size={12} style={{ verticalAlign: 'text-bottom', marginRight: '0.25rem' }} />
                      <strong>Community Note:</strong> {profile.player.notes}
                    </div>
                  )}
                </div>
              </div>

              {/* Source-Qualified Combat Statistics */}
              <div className="card">
                <div className="card-header">
                  <div>
                    <h4>Combat Statistics & Provenance</h4>
                    <span className="small muted">
                      Missing metrics display &ldquo;Unavailable from this source&rdquo; and are never zero-filled.
                    </span>
                  </div>
                  <div className="row">
                    <select
                      className="select"
                      style={{ width: 'auto' }}
                      value={providerFilter}
                      onChange={(e) => setProviderFilter(e.target.value)}
                    >
                      <option value="all">All Providers</option>
                      <option value="community_match">Community Match</option>
                      <option value="faceit">FACEIT</option>
                      <option value="leetify">Leetify</option>
                    </select>
                    <select
                      className="select"
                      style={{ width: 'auto' }}
                      value={scopeFilter}
                      onChange={(e) => setScopeFilter(e.target.value)}
                    >
                      <option value="all">All Scopes</option>
                      <option value="recent">Recent</option>
                      <option value="lifetime">Lifetime</option>
                      <option value="season">Season</option>
                    </select>
                    <button className="btn btn-sm btn-primary" onClick={() => setShowAddStat(!showAddStat)}>
                      <Plus size={14} /> Log Match Stats
                    </button>
                  </div>
                </div>

                {showAddStat && (
                  <form
                    onSubmit={handleAddStat}
                    className="card"
                    style={{ background: 'var(--bg-canvas)', marginBottom: '0.85rem' }}
                  >
                    <div className="form-grid">
                      <div>
                        <label className="field-label">Matches Sample</label>
                        <input className="input mono" type="number" min={1} value={statMatches} onChange={(e) => setStatMatches(e.target.value)} />
                      </div>
                      <div>
                        <label className="field-label">Win Rate %</label>
                        <input className="input mono" type="number" step="0.1" value={statWinRate} onChange={(e) => setStatWinRate(e.target.value)} placeholder="e.g. 54.5" />
                      </div>
                      <div>
                        <label className="field-label">K/D Ratio</label>
                        <input className="input mono" type="number" step="0.01" value={statKd} onChange={(e) => setStatKd(e.target.value)} placeholder="e.g. 1.15" />
                      </div>
                      <div>
                        <label className="field-label">ADR</label>
                        <input className="input mono" type="number" step="0.1" value={statAdr} onChange={(e) => setStatAdr(e.target.value)} placeholder="e.g. 84.2" />
                      </div>
                      <div>
                        <label className="field-label">KAST %</label>
                        <input className="input mono" type="number" step="0.1" value={statKast} onChange={(e) => setStatKast(e.target.value)} placeholder="e.g. 72.0" />
                      </div>
                      <div>
                        <label className="field-label">HS %</label>
                        <input className="input mono" type="number" step="0.1" value={statHs} onChange={(e) => setStatHs(e.target.value)} placeholder="e.g. 49.0" />
                      </div>
                      <div>
                        <label className="field-label">Opening Duel %</label>
                        <input className="input mono" type="number" step="0.1" value={statOpen} onChange={(e) => setStatOpen(e.target.value)} placeholder="e.g. 52.0" />
                      </div>
                      <div>
                        <label className="field-label">Utility Dmg/Rd</label>
                        <input className="input mono" type="number" step="0.1" value={statUtil} onChange={(e) => setStatUtil(e.target.value)} placeholder="e.g. 19.5" />
                      </div>
                      <div>
                        <label className="field-label">Flash Assists/Rd</label>
                        <input className="input mono" type="number" step="0.01" value={statFlash} onChange={(e) => setStatFlash(e.target.value)} placeholder="e.g. 0.28" />
                      </div>
                      <div>
                        <label className="field-label">Clutch Win %</label>
                        <input className="input mono" type="number" step="0.1" value={statClutch} onChange={(e) => setStatClutch(e.target.value)} placeholder="e.g. 29.0" />
                      </div>
                    </div>
                    <div className="row" style={{ justifyContent: 'flex-end', marginTop: '0.65rem' }}>
                      <button type="button" className="btn btn-sm" onClick={() => setShowAddStat(false)}>Cancel</button>
                      <button type="submit" className="btn btn-sm btn-primary" disabled={busy}>Save Snapshot</button>
                    </div>
                  </form>
                )}

                {filteredSnapshots.length === 0 ? (
                  <p className="muted small" style={{ margin: 0 }}>
                    No combat stat snapshots recorded for this filter. External metrics require API keys or logged community match stats.
                  </p>
                ) : (
                  <div className="stack">
                    {filteredSnapshots.map((snap) => (
                      <div key={snap.id} className="card" style={{ background: 'var(--bg-elevated)', padding: '0.8rem' }}>
                        <div className="row" style={{ justifyContent: 'space-between', marginBottom: '0.55rem' }}>
                          <div className="row" style={{ gap: '0.4rem' }}>
                            <span className="badge badge-a">{snap.provider}</span>
                            <span className="badge">{snap.scope}</span>
                            <span className="badge">{snap.game_mode}</span>
                            {snap.is_sample_demo && <span className="badge badge-warn">DEMO SAMPLE</span>}
                          </div>
                          <span className="small muted">
                            Sample: {snap.sample_size ?? 'Unknown'} • {snap.freshness} •{' '}
                            {new Date(snap.captured_at).toLocaleDateString()}
                          </span>
                        </div>
                        <div className="cs2-stat-grid">
                          {METRIC_LABELS.map((m) => {
                            const raw = snap[m.key];
                            const formatted =
                              typeof raw === 'number'
                                ? `${raw.toFixed(m.decimals ?? 1)}${m.suffix || ''}`
                                : 'Unavailable from this source';
                            return (
                              <div key={String(m.key)} className="cs2-stat-cell">
                                <span className="small muted">{m.label}</span>
                                <strong className={typeof raw === 'number' ? 'mono' : 'small muted'}>
                                  {formatted}
                                </strong>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Recent External / Community Match History */}
              <div className="card">
                <h4 style={{ marginBottom: '0.55rem' }}>
                  Recent Match History ({profile.match_records.length})
                </h4>
                {profile.match_records.length === 0 ? (
                  <p className="muted small" style={{ margin: 0 }}>
                    No match history synced yet. Click Refresh on a linked SteamID64 to fetch public Leetify matches.
                  </p>
                ) : (
                  <div className="stack" style={{ gap: '0.35rem', maxHeight: '260px', overflowY: 'auto' }}>
                    {profile.match_records.map((m) => (
                      <div key={m.id} className="player-row" style={{ padding: '0.45rem 0.65rem' }}>
                        <div>
                          <div className="row" style={{ gap: '0.35rem' }}>
                            <strong className="small">{m.map_name || 'Unknown map'}</strong>
                            {m.outcome && (
                              <span className={`badge ${m.outcome === 'win' ? 'badge-ok' : m.outcome === 'loss' ? 'badge-danger' : ''}`}>
                                {m.outcome.toUpperCase()} {m.score_text || ''}
                              </span>
                            )}
                            <span className="badge">{m.provider}</span>
                          </div>
                          <div className="small muted mono">
                            ADR {m.adr != null ? m.adr.toFixed(1) : '—'} • K/D{' '}
                            {m.kd_ratio != null ? m.kd_ratio.toFixed(2) : '—'} • HS%{' '}
                            {m.hs_pct != null ? `${m.hs_pct.toFixed(0)}%` : '—'} •{' '}
                            {new Date(m.played_at).toLocaleDateString()}
                          </div>
                        </div>
                        {m.source_url && (
                          <a className="btn btn-xs" href={m.source_url} target="_blank" rel="noreferrer">
                            Match
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
