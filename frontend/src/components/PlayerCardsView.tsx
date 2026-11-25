import React from 'react';
import { Award, Flame, ShieldAlert, Sparkles } from 'lucide-react';
import type { Player } from '../types';
import { PlayerCardTile } from './PlayerCardTile';

interface Props {
  players: Player[];
  onRefreshPlayers: () => Promise<void>;
  onOpenProfile: (playerId: string) => void;
  onError: (msg: string) => void;
}

export const PlayerCardsView: React.FC<Props> = ({
  players,
  onRefreshPlayers,
  onOpenProfile,
  onError,
}) => {
  const playersWithStats = players.filter((p) => p.latest_stats != null);

  const bestAdr = [...playersWithStats].sort(
    (a, b) => (b.latest_stats?.adr ?? -1) - (a.latest_stats?.adr ?? -1),
  )[0];
  const bestClutch = [...playersWithStats].sort(
    (a, b) => (b.latest_stats?.clutch_win_pct ?? -1) - (a.latest_stats?.clutch_win_pct ?? -1),
  )[0];
  const bestUtil = [...playersWithStats].sort(
    (a, b) =>
      (b.latest_stats?.utility_damage_per_round ?? -1) -
      (a.latest_stats?.utility_damage_per_round ?? -1),
  )[0];
  const bestFlash = [...playersWithStats].sort(
    (a, b) =>
      (b.latest_stats?.flash_assists_per_round ?? -1) -
      (a.latest_stats?.flash_assists_per_round ?? -1),
  )[0];

  return (
    <div className="stack">
      <div className="card">
        <div className="card-header">
          <div>
            <h2>CS2 Player Cards & Evidence-Based Awards</h2>
            <p className="muted" style={{ margin: '0.2rem 0 0' }}>
              Titles and roasts are generated deterministically from verified statistics with minimum sample thresholds. Missing data never produces negative titles.
            </p>
          </div>
          <span className="badge">card_rules_v1</span>
        </div>

        {playersWithStats.length === 0 ? (
          <div className="alert alert-warn">
            <span>
              <ShieldAlert size={14} style={{ verticalAlign: 'text-bottom', marginRight: '0.35rem' }} />
              No match statistics recorded yet — community awards appear once match stats are logged or synced.
            </span>
          </div>
        ) : (
          <>
            <div className="small muted" style={{ fontWeight: 700, letterSpacing: '0.04em', marginBottom: '0.45rem' }}>
              COMMUNITY STAT LEADERS
            </div>
            <div className="cs2-kpi-grid">
            {bestAdr?.latest_stats?.adr != null && (
              <div className="cs2-kpi">
                <span className="small muted">
                  <Flame size={12} style={{ verticalAlign: 'text-bottom' }} /> Highest ADR
                </span>
                <strong>{bestAdr.display_name}</strong>
                <span className="mono small" style={{ color: 'var(--accent-amber)' }}>
                  {bestAdr.latest_stats.adr.toFixed(1)} ADR
                </span>
              </div>
            )}
            {bestClutch?.latest_stats?.clutch_win_pct != null && (
              <div className="cs2-kpi">
                <span className="small muted">
                  <Award size={12} style={{ verticalAlign: 'text-bottom' }} /> Clutch Leader
                </span>
                <strong>{bestClutch.display_name}</strong>
                <span className="mono small" style={{ color: 'var(--team-a)' }}>
                  {bestClutch.latest_stats.clutch_win_pct.toFixed(1)}% 1vX
                </span>
              </div>
            )}
            {bestUtil?.latest_stats?.utility_damage_per_round != null && (
              <div className="cs2-kpi">
                <span className="small muted">
                  <Sparkles size={12} style={{ verticalAlign: 'text-bottom' }} /> Utility Specialist
                </span>
                <strong>{bestUtil.display_name}</strong>
                <span className="mono small" style={{ color: 'var(--ok)' }}>
                  {bestUtil.latest_stats.utility_damage_per_round.toFixed(1)} Util Dmg/Rd
                </span>
              </div>
            )}
            {bestFlash?.latest_stats?.flash_assists_per_round != null && (
              <div className="cs2-kpi">
                <span className="small muted">Flash Support</span>
                <strong>{bestFlash.display_name}</strong>
                <span className="mono small">
                  {bestFlash.latest_stats.flash_assists_per_round.toFixed(2)} Flashes/Rd
                </span>
              </div>
            )}
            </div>
          </>
        )}
      </div>

      {players.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '2.5rem' }}>
          <p className="muted">No players available. Add players or load Demo 10 in Players / Match Room.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '0.9rem' }}>
          {players.map(
            (p) =>
              p.card && (
                <PlayerCardTile
                  key={p.id}
                  player={p}
                  card={p.card}
                  onProfileUpdated={() => onRefreshPlayers()}
                  onOpenProfile={onOpenProfile}
                  onError={onError}
                />
              ),
          )}
        </div>
      )}
    </div>
  );
};
