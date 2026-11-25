import React from 'react';
import { History, Plus, Shield, Swords, Users } from 'lucide-react';
import type { HealthResponse, MatchRoom, Player } from '../types';
import { PlayerCardTile } from './PlayerCardTile';

interface Props {
  health: HealthResponse | null;
  players: Player[];
  rooms: MatchRoom[];
  newRoomTitle: string;
  onNewRoomTitleChange: (val: string) => void;
  onCreateRoom: (e: React.FormEvent) => void;
  onOpenRoom: (roomId: string) => void;
  onOpenProfile: (playerId: string) => void;
  onOpenPlayers: () => void;
  onError: (msg: string) => void;
  onRefreshPlayers: () => Promise<void>;
}

export const DashboardView: React.FC<Props> = ({
  health,
  players,
  rooms,
  newRoomTitle,
  onNewRoomTitleChange,
  onCreateRoom,
  onOpenRoom,
  onOpenProfile,
  onOpenPlayers,
  onError,
  onRefreshPlayers,
}) => {
  const verifiedSteamCount = players.filter((p) => Boolean(p.steam_id64)).length;
  const finalizedCount = rooms.filter((r) => r.status === 'FINALIZED').length;
  const statsTrackedCount = players.filter((p) => p.latest_stats != null).length;

  const featured =
    players.find((p) => p.card && p.card.eligible_count > 0) || players[0] || null;

  const recentAliases = players
    .flatMap((p) =>
      p.aliases
        .filter((a) => a.previous_name)
        .map((a) => ({ playerId: p.id, currentName: p.display_name, ...a })),
    )
    .sort((a, b) => new Date(b.observed_at).getTime() - new Date(a.observed_at).getTime())
    .slice(0, 6);

  return (
    <div className="stack">
      {/* Top KPI Summary */}
      <div className="card">
        <div className="card-header">
          <div>
            <h2>Community Tactical Hub</h2>
            <p className="muted" style={{ margin: '0.2rem 0 0' }}>
              Organize private 10-man 5v5 matches with canonical SteamID64 tracking, source-qualified stats, and 126-partition balancing.
            </p>
          </div>
          <form onSubmit={onCreateRoom} className="row">
            <input
              className="input"
              style={{ width: '230px' }}
              placeholder="New match room title..."
              value={newRoomTitle}
              onChange={(e) => onNewRoomTitleChange(e.target.value)}
            />
            <button type="submit" className="btn btn-primary">
              <Plus size={15} /> Quick Create Match
            </button>
          </form>
        </div>

        <div className="cs2-kpi-grid">
          <div className="cs2-kpi">
            <span className="small muted">Registered Players</span>
            <strong className="mono" style={{ fontSize: '1.3rem' }}>{players.length}</strong>
            <span className="small muted">{verifiedSteamCount} with SteamID64</span>
          </div>
          <div className="cs2-kpi">
            <span className="small muted">Match Rooms</span>
            <strong className="mono" style={{ fontSize: '1.3rem' }}>{rooms.length}</strong>
            <span className="small muted">{finalizedCount} finalized lineups</span>
          </div>
          <div className="cs2-kpi">
            <span className="small muted">Combat Stat Profiles</span>
            <strong className="mono" style={{ fontSize: '1.3rem' }}>{statsTrackedCount}</strong>
            <span className="small muted">Source-qualified snapshots</span>
          </div>
          <div className="cs2-kpi">
            <span className="small muted">External Providers</span>
            <div className="row" style={{ gap: '0.3rem', marginTop: '0.2rem' }}>
              <span className={`badge ${health?.providers.steam === 'configured' ? 'badge-ok' : ''}`}>
                Steam: {health?.providers.steam === 'configured' ? 'OK' : 'Off'}
              </span>
              <span className={`badge ${health?.providers.faceit === 'configured' ? 'badge-ok' : ''}`}>
                FACEIT: {health?.providers.faceit === 'configured' ? 'OK' : 'Off'}
              </span>
            </div>
            <span className="small muted">Manual mode always available</span>
          </div>
        </div>
      </div>

      <div className="grid-2">
        {/* Recent Match Rooms */}
        <div className="card">
          <div className="card-header">
            <h3>
              <Swords size={16} style={{ verticalAlign: 'text-bottom', marginRight: '0.35rem' }} />
              Recent Match Rooms
            </h3>
            <span className="badge">Maps: Random</span>
          </div>

          {rooms.length === 0 ? (
            <div className="card" style={{ background: 'var(--bg-canvas)', textAlign: 'center', padding: '1.5rem' }}>
              <p className="muted small">No match rooms yet. Create one above to assemble your 5v5.</p>
            </div>
          ) : (
            <div className="stack" style={{ gap: '0.5rem' }}>
              {rooms.slice(0, 6).map((r) => (
                <div key={r.id} className="player-row">
                  <div>
                    <div className="row" style={{ gap: '0.4rem' }}>
                      <strong>{r.title}</strong>
                      <span className={`badge ${r.status === 'FINALIZED' ? 'badge-ok' : ''}`}>{r.status}</span>
                      <span className="badge mono">{r.selected_count}/10</span>
                    </div>
                    <div className="small muted">
                      Proposals: {r.proposals.length}
                      {r.finalized_lineup
                        ? ` • Finalized Diff ${r.finalized_lineup.strength_diff.toFixed(2)}`
                        : ''}
                    </div>
                  </div>
                  <button className="btn btn-sm btn-primary" onClick={() => onOpenRoom(r.id)}>
                    Open
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Featured CS2 Player Card */}
        <div className="stack">
          {featured && featured.card ? (
            <div>
              <div className="row" style={{ justifyContent: 'space-between', marginBottom: '0.45rem' }}>
                <strong className="small muted">FEATURED PLAYER CARD</strong>
                <button className="btn btn-xs" onClick={onOpenPlayers}>
                  <Users size={12} /> All Players
                </button>
              </div>
              <PlayerCardTile
                player={featured}
                card={featured.card}
                compact
                onOpenProfile={onOpenProfile}
                onProfileUpdated={() => onRefreshPlayers()}
                onError={onError}
              />
            </div>
          ) : (
            <div className="card" style={{ textAlign: 'center', padding: '2rem' }}>
              <p className="muted">Add players or load the 10 Demo Players to preview CS2 Player Cards.</p>
            </div>
          )}

          {/* Alias Changes */}
          <div className="card">
            <h4 style={{ marginBottom: '0.5rem' }}>
              <History size={15} style={{ verticalAlign: 'text-bottom', marginRight: '0.35rem' }} />
              Recent Username / Alias Observations
            </h4>
            {recentAliases.length === 0 ? (
              <p className="muted small" style={{ margin: 0 }}>
                <Shield size={12} style={{ verticalAlign: 'text-bottom', marginRight: '0.25rem' }} />
                No username changes recorded yet. Steam persona updates are tracked append-only here.
              </p>
            ) : (
              <div className="stack" style={{ gap: '0.35rem' }}>
                {recentAliases.map((a) => (
                  <div
                    key={a.id}
                    className="player-row"
                    style={{ padding: '0.4rem 0.6rem', cursor: 'pointer' }}
                    onClick={() => onOpenProfile(a.playerId)}
                  >
                    <span className="small">
                      <strong>{a.currentName}</strong>:{' '}
                      <span className="muted">{a.previous_name}</span> → <strong>{a.alias_name}</strong>
                    </span>
                    <span className="small muted">{a.source}</span>
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
