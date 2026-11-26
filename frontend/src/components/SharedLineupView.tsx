import React from 'react';
import { ArrowLeft, Check, Copy, ShieldCheck } from 'lucide-react';
import type { FinalizedLineup } from '../types';

interface Props {
  roomTitle: string;
  lineup: FinalizedLineup;
  onBack: () => void;
}

export const SharedLineupView: React.FC<Props> = ({ roomTitle, lineup, onBack }) => {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(lineup.discord_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="stack" style={{ maxWidth: '920px', margin: '0 auto' }}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <button className="btn" onClick={onBack}>
          <ArrowLeft size={15} /> Back to StackForge
        </button>
        <span className="badge badge-ok">
          <ShieldCheck size={13} /> Finalized Proposal #{lineup.proposal_number}
        </span>
      </div>

      <div className="card">
        <div className="card-header">
          <div>
            <h2>{roomTitle}</h2>
            <p className="muted" style={{ margin: '0.2rem 0 0' }}>
              Finalized by {lineup.finalized_by} • Maps are random (active map pool) • Strength Diff{' '}
              <strong className="mono">{lineup.strength_diff.toFixed(2)}</strong>
            </p>
          </div>
          <button className="btn btn-primary" onClick={handleCopy}>
            {copied ? <Check size={15} /> : <Copy size={15} />}
            {copied ? 'Copied Discord Format!' : 'Copy Discord Lineup'}
          </button>
        </div>

        <div className="grid-2">
          <div className="team-panel team-a">
            <div className="card-header">
              <h3 style={{ color: 'var(--team-a)' }}>TEAM A</h3>
              <span className="badge badge-a mono">Avg {lineup.team_a_strength.toFixed(1)}</span>
            </div>
            {lineup.team_a.map((p) => (
              <div key={p.id} className="team-player-card">
                <div>
                  <strong>{p.display_name}</strong>
                  {p.primary_role && <span className="badge" style={{ marginLeft: '0.4rem' }}>{p.primary_role}</span>}
                </div>
                <span className="mono small muted">{p.normalized_strength != null ? p.normalized_strength.toFixed(1) : 'Unranked'}</span>
              </div>
            ))}
          </div>

          <div className="team-panel team-b">
            <div className="card-header">
              <h3 style={{ color: 'var(--team-b)' }}>TEAM B</h3>
              <span className="badge badge-b mono">Avg {lineup.team_b_strength.toFixed(1)}</span>
            </div>
            {lineup.team_b.map((p) => (
              <div key={p.id} className="team-player-card">
                <div>
                  <strong>{p.display_name}</strong>
                  {p.primary_role && <span className="badge" style={{ marginLeft: '0.4rem' }}>{p.primary_role}</span>}
                </div>
                <span className="mono small muted">{p.normalized_strength != null ? p.normalized_strength.toFixed(1) : 'Unranked'}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="divider" />
        <pre
          className="mono small"
          style={{
            background: 'var(--bg-canvas)',
            padding: '0.85rem',
            borderRadius: '8px',
            border: '1px solid var(--border)',
            overflowX: 'auto',
            margin: 0,
            whiteSpace: 'pre-wrap',
          }}
        >
          {lineup.discord_text}
        </pre>
      </div>
    </div>
  );
};
