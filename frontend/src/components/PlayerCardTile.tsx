import React, { useState } from 'react';
import { Award, Check, Copy, Eye, EyeOff, RefreshCw, Sparkles } from 'lucide-react';
import { api, ApiError } from '../api';
import type { HumourIntensity, Player, PlayerCard, PlayerProfile } from '../types';
import { PlayerAvatar } from './PlayerAvatar';

interface Props {
  player: Player;
  card: PlayerCard;
  onProfileUpdated?: (profile: PlayerProfile) => void;
  onError?: (msg: string) => void;
  compact?: boolean;
  onOpenProfile?: (playerId: string) => void;
}

export const PlayerCardTile: React.FC<Props> = ({
  player,
  card,
  onProfileUpdated,
  onError,
  compact = false,
  onOpenProfile,
}) => {
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const updateSettings = async (payload: {
    humour_enabled?: boolean;
    humour_intensity?: HumourIntensity;
    hidden_badges?: string[];
    regenerate_tagline?: boolean;
  }) => {
    setBusy(true);
    try {
      const updated = await api.updateCardSettings(player.id, payload);
      onProfileUpdated?.(updated);
    } catch (err) {
      onError?.(err instanceof ApiError ? err.message : 'Could not update player card settings.');
    } finally {
      setBusy(false);
    }
  };

  const toggleBadgeVisibility = (key: string) => {
    const currentHidden = card.badges.filter((b) => b.hidden).map((b) => b.key);
    const nextHidden = currentHidden.includes(key)
      ? currentHidden.filter((k) => k !== key)
      : [...currentHidden, key];
    updateSettings({ hidden_badges: nextHidden });
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(card.discord_card_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  const latestAlias = player.aliases.find((a) => a.previous_name);
  const visibleBadges = card.badges.filter((b) => !b.hidden);
  const hiddenBadges = card.badges.filter((b) => b.hidden);

  return (
    <div className="cs2-card">
      <div className="cs2-card-stripe" />
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'nowrap', gap: '0.6rem' }}>
        <div className="row" style={{ gap: '0.65rem', minWidth: 0, flex: 1 }}>
          <PlayerAvatar name={player.display_name} avatarUrl={player.avatar_url} role={player.primary_role} size={44} />
          <div style={{ minWidth: 0 }}>
            <div className="row" style={{ gap: '0.35rem' }}>
              <strong
                style={{ fontSize: '1rem', cursor: onOpenProfile ? 'pointer' : 'default' }}
                onClick={() => onOpenProfile?.(player.id)}
              >
                {player.display_name}
              </strong>
              {player.primary_role && <span className="badge">{player.primary_role}</span>}
              {player.is_seeded && <span className="badge badge-warn">DEMO SAMPLE</span>}
            </div>
            <div className="small muted" style={{ marginTop: '0.15rem' }}>
              {player.steam_persona_name && player.steam_persona_name !== player.display_name && (
                <span>Steam: {player.steam_persona_name} • </span>
              )}
              {latestAlias?.previous_name && <span>aka {latestAlias.previous_name} • </span>}
              <span className="mono">{player.steam_id64 ? 'SteamID64' : 'Manual Profile'}</span>
            </div>
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          <div className="mono" style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--accent-amber)' }}>
            {player.normalized_strength != null ? player.normalized_strength.toFixed(1) : '—'}
          </div>
          <div className="small muted">{player.strength_band}</div>
        </div>
      </div>

      <div className="cs2-card-title-box">
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: '0.25rem' }}>
          <span className="row" style={{ gap: '0.35rem', color: 'var(--accent-amber)', fontWeight: 700, fontSize: '0.92rem' }}>
            <Award size={15} /> {card.primary_title}
          </span>
          <span className="badge mono">{card.humour_enabled ? card.humour_intensity : 'HUMOUR OFF'}</span>
        </div>
        <p style={{ margin: '0.2rem 0 0', fontSize: '0.86rem', color: 'var(--text-primary)' }}>
          {card.tagline}
        </p>
        <div className="small muted" style={{ marginTop: '0.4rem' }}>
          <strong>Evidence:</strong> {card.evidence_summary}
        </div>
      </div>

      {card.badges.length > 0 && (
        <div className="row" style={{ gap: '0.35rem', marginTop: '0.55rem' }}>
          {visibleBadges.map((b) => (
            <span key={b.key} className="badge badge-a" title={b.evidence}>
              <Sparkles size={11} /> {b.label}
              {!compact && onProfileUpdated && (
                <button
                  type="button"
                  onClick={() => toggleBadgeVisibility(b.key)}
                  title="Hide badge"
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'inherit',
                    cursor: 'pointer',
                    padding: 0,
                    marginLeft: '0.2rem',
                    display: 'inline-flex',
                  }}
                >
                  <EyeOff size={11} />
                </button>
              )}
            </span>
          ))}
          {!compact &&
            onProfileUpdated &&
            hiddenBadges.map((b) => (
              <button
                key={b.key}
                type="button"
                className="btn btn-xs"
                onClick={() => toggleBadgeVisibility(b.key)}
                title={`Show hidden badge: ${b.label}`}
              >
                <Eye size={11} /> {b.label}
              </button>
            ))}
        </div>
      )}

      {player.latest_stats && (
        <div className="cs2-stat-strip">
          <div>
            <span className="small muted">ADR</span>
            <strong className="mono">{player.latest_stats.adr != null ? player.latest_stats.adr.toFixed(1) : '—'}</strong>
          </div>
          <div>
            <span className="small muted">K/D</span>
            <strong className="mono">{player.latest_stats.kd_ratio != null ? player.latest_stats.kd_ratio.toFixed(2) : '—'}</strong>
          </div>
          <div>
            <span className="small muted">HS%</span>
            <strong className="mono">{player.latest_stats.hs_pct != null ? `${player.latest_stats.hs_pct.toFixed(0)}%` : '—'}</strong>
          </div>
          <div>
            <span className="small muted">Clutch</span>
            <strong className="mono">
              {player.latest_stats.clutch_win_pct != null ? `${player.latest_stats.clutch_win_pct.toFixed(0)}%` : '—'}
            </strong>
          </div>
        </div>
      )}

      <div className="row" style={{ justifyContent: 'space-between', marginTop: '0.65rem' }}>
        <div className="row" style={{ gap: '0.3rem' }}>
          {!compact && onProfileUpdated && (
            <>
              <button
                className="btn btn-xs"
                disabled={busy || !card.humour_enabled}
                onClick={() => updateSettings({ regenerate_tagline: true })}
                title="Regenerate funny description from same evidence"
              >
                <RefreshCw size={12} /> Reroll Roast
              </button>
              <select
                className="select"
                style={{ width: 'auto', padding: '0.2rem 0.4rem', fontSize: '0.73rem' }}
                value={card.humour_intensity}
                disabled={busy || !card.humour_enabled}
                onChange={(e) => updateSettings({ humour_intensity: e.target.value as HumourIntensity })}
              >
                <option value="MILD">Mild</option>
                <option value="SPICY">Spicy</option>
                <option value="SAVAGE">Savage</option>
              </select>
              <button
                className="btn btn-xs"
                disabled={busy}
                onClick={() => updateSettings({ humour_enabled: !card.humour_enabled })}
              >
                {card.humour_enabled ? 'Disable Humour' : 'Enable Humour'}
              </button>
            </>
          )}
        </div>

        <div className="row" style={{ gap: '0.3rem' }}>
          <button className="btn btn-xs" onClick={handleCopy}>
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? 'Copied' : 'Copy Card'}
          </button>
          {onOpenProfile && (
            <button className="btn btn-xs btn-primary" onClick={() => onOpenProfile(player.id)}>
              Profile
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
