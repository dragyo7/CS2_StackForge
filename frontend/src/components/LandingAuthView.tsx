import React, { useState } from 'react';
import { ArrowRight, Lock, LogIn, Shield, Sparkles, Swords, UserPlus, Users } from 'lucide-react';
import { api, ApiError, setStoredToken } from '../api';
import type { AuthState } from '../types';

interface Props {
  auth: AuthState;
  onAuthChanged: (next: AuthState) => void;
  onEnterApp: () => void;
  onError: (msg: string) => void;
}

export const LandingAuthView: React.FC<Props> = ({
  auth,
  onAuthChanged,
  onEnterApp,
  onError,
}) => {
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const res =
        mode === 'signup'
          ? await api.authSignup(email, username, password)
          : await api.authLogin(email, password);
      setStoredToken(res.token);
      onAuthChanged({ authenticated: true, mode: 'authenticated', user: res.user });
      onEnterApp();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Authentication failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <section className="hero-panel">
        <div className="grid-2" style={{ alignItems: 'center', gap: '1.5rem' }}>
          <div className="stack">
            <div className="row" style={{ gap: '0.45rem' }}>
              <span className="badge badge-a">CS2 5v5 Community Platform</span>
              <span className="badge">Read-Only & Anti-Cheat Safe</span>
              <span className="badge">Random Maps</span>
            </div>
            <h1 style={{ fontSize: '2rem', lineHeight: 1.15 }}>
              Know who is playing. Balance every 10-man with proof.
            </h1>
            <p className="muted" style={{ margin: 0, fontSize: '0.94rem' }}>
              StackForge connects your community spreadsheet, canonical SteamID64 identities, live Leetify & CSWatch
              intelligence, transparent 126-partition 5v5 optimization, and evidence-backed player cards in one tactical hub.
            </p>
            <div className="row" style={{ gap: '0.6rem' }}>
              <button className="btn btn-primary" onClick={onEnterApp}>
                <Swords size={16} /> Open Match Room <ArrowRight size={15} />
              </button>
              <span className="small muted">
                {auth.authenticated
                  ? `Signed in as ${auth.user?.username}`
                  : 'Local-dev host mode active (sign in optional)'}
              </span>
            </div>
          </div>

          <div className="card" style={{ background: 'rgba(11, 15, 23, 0.85)' }}>
            <div className="card-header" style={{ marginBottom: '0.65rem' }}>
              <div className="row" style={{ gap: '0.4rem' }}>
                <Lock size={15} color="var(--accent-amber)" />
                <strong>{auth.authenticated ? 'Account Active' : mode === 'login' ? 'Sign In' : 'Create Account'}</strong>
              </div>
              {!auth.authenticated && (
                <div className="row" style={{ gap: '0.3rem' }}>
                  <button
                    type="button"
                    className={`btn btn-xs ${mode === 'login' ? 'btn-primary' : ''}`}
                    onClick={() => setMode('login')}
                  >
                    Login
                  </button>
                  <button
                    type="button"
                    className={`btn btn-xs ${mode === 'signup' ? 'btn-primary' : ''}`}
                    onClick={() => setMode('signup')}
                  >
                    Sign Up
                  </button>
                </div>
              )}
            </div>

            {auth.authenticated && auth.user ? (
              <div className="stack">
                <div className="player-row">
                  <div>
                    <strong>{auth.user.username}</strong>
                    <div className="small muted">{auth.user.email} • Role: {auth.user.role}</div>
                  </div>
                  <span className="badge badge-ok">Authenticated</span>
                </div>
                <button className="btn btn-primary" onClick={onEnterApp}>
                  Continue to StackForge
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="stack" style={{ gap: '0.55rem' }}>
                <div>
                  <label className="field-label">Email</label>
                  <input
                    className="input"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="host@stackforge.gg"
                  />
                </div>
                {mode === 'signup' && (
                  <div>
                    <label className="field-label">Display Handle</label>
                    <input
                      className="input"
                      required
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="e.g. Drago7"
                    />
                  </div>
                )}
                <div>
                  <label className="field-label">Password (8+ chars)</label>
                  <input
                    className="input"
                    type="password"
                    minLength={8}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                  />
                </div>
                <button type="submit" className="btn btn-primary" disabled={busy}>
                  {mode === 'login' ? <LogIn size={15} /> : <UserPlus size={15} />}
                  {busy ? 'Working...' : mode === 'login' ? 'Sign In' : 'Create Account'}
                </button>
              </form>
            )}
          </div>
        </div>
      </section>

      {/* Feature Preview Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.85rem' }}>
        <div className="card">
          <div className="row" style={{ gap: '0.45rem', marginBottom: '0.4rem' }}>
            <Users size={16} color="var(--team-a)" />
            <strong>Spreadsheet & Identity Sync</strong>
          </div>
          <p className="muted small" style={{ margin: 0 }}>
            Import Google Sheets, CSV, or XLSX directly. Resolves SteamID64, CSStats, Leetify, and FACEIT without duplicating changing usernames.
          </p>
        </div>
        <div className="card">
          <div className="row" style={{ gap: '0.45rem', marginBottom: '0.4rem' }}>
            <Sparkles size={16} color="var(--accent-amber)" />
            <strong>Explainable 126-Split Balancer</strong>
          </div>
          <p className="muted small" style={{ margin: 0 }}>
            Evaluates all 126 unique 5v5 partitions with role coverage, recent form, hidden map-pool robustness, and clear trade-off explanations.
          </p>
        </div>
        <div className="card">
          <div className="row" style={{ gap: '0.45rem', marginBottom: '0.4rem' }}>
            <Shield size={16} color="var(--ok)" />
            <strong>Trust & Account Watch</strong>
          </div>
          <p className="muted small" style={{ margin: 0 }}>
            Separates official Steam enforcement from CSWatch third-party signals and private community reviews. Never auto-convicts from incomplete data.
          </p>
        </div>
      </div>
    </div>
  );
};
