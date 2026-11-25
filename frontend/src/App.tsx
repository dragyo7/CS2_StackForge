import React, { useEffect, useState } from 'react';
import {
  Activity,
  Award,
  LayoutDashboard,
  LogIn,
  LogOut,
  Plus,
  Shield,
  Swords,
  Users,
} from 'lucide-react';
import { api, ApiError, setStoredToken } from './api';
import { DashboardView } from './components/DashboardView';
import { LandingAuthView } from './components/LandingAuthView';
import { MatchRoomView } from './components/MatchRoomView';
import { PlayerCardsView } from './components/PlayerCardsView';
import { PlayerRegistryView } from './components/PlayerRegistryView';
import { PlayerStatsView } from './components/PlayerStatsView';
import { SharedLineupView } from './components/SharedLineupView';
import { TrustWatchView } from './components/TrustWatchView';
import type { AuthState, FinalizedLineup, HealthResponse, MatchRoom, Player } from './types';

type Tab = 'landing' | 'dashboard' | 'room' | 'players' | 'stats' | 'cards' | 'trust';

export const App: React.FC = () => {
  const [tab, setTab] = useState<Tab>('room');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [auth, setAuth] = useState<AuthState>({ authenticated: false, mode: 'local_dev_host', user: null });
  const [players, setPlayers] = useState<Player[]>([]);
  const [rooms, setRooms] = useState<MatchRoom[]>([]);
  const [activeRoomId, setActiveRoomId] = useState<string | null>(null);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [newRoomTitle, setNewRoomTitle] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [sharedView, setSharedView] = useState<{ roomTitle: string; lineup: FinalizedLineup } | null>(
    null,
  );

  const loadAll = async () => {
    try {
      const [h, me, ps, rs] = await Promise.all([
        api.health(),
        api.authMe(),
        api.listPlayers(),
        api.listRooms(),
      ]);
      setHealth(h);
      setAuth(me);
      setPlayers(ps);
      setRooms(rs);
      if (rs.length > 0 && (!activeRoomId || !rs.some((r) => r.id === activeRoomId))) {
        setActiveRoomId(rs[0].id);
      }
      if (ps.length > 0 && !selectedProfileId) {
        setSelectedProfileId(ps[0].id);
      }
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : 'Unable to reach StackForge backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const shareSlug = params.get('share');
    if (shareSlug) {
      api
        .getSharedLineup(shareSlug)
        .then((res) => {
          setSharedView({ roomTitle: res.room_title, lineup: res.lineup });
        })
        .catch(() => setErrorMsg('Shared lineup not found.'))
        .finally(() => setLoading(false));
    }
    loadAll();
  }, []);

  const handleOpenShareSlug = async (slug: string) => {
    try {
      const res = await api.getSharedLineup(slug);
      setSharedView({ roomTitle: res.room_title, lineup: res.lineup });
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : 'Unable to load shared lineup.');
    }
  };

  const handleOpenProfile = (playerId: string) => {
    setSelectedProfileId(playerId);
    setSharedView(null);
    setTab('stats');
  };

  const handleCreateRoom = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const title = newRoomTitle.trim() || `5v5 Match #${rooms.length + 1}`;
    try {
      const created = await api.createRoom(title);
      setRooms((prev) => [created, ...prev]);
      setActiveRoomId(created.id);
      setNewRoomTitle('');
      setTab('room');
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : 'Failed to create match room.');
    }
  };

  const handleRoomUpdated = (updated: MatchRoom) => {
    setRooms((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
    setActiveRoomId(updated.id);
  };

  const refreshPlayers = async () => {
    const ps = await api.listPlayers();
    setPlayers(ps);
  };

  const handleLogout = async () => {
    try {
      await api.authLogout();
    } catch {
      // ignore
    }
    setStoredToken(null);
    setAuth({ authenticated: false, mode: 'local_dev_host', user: null });
  };

  const activeRoom = rooms.find((r) => r.id === activeRoomId) || rooms[0] || null;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div
          className="brand"
          style={{ cursor: 'pointer' }}
          onClick={() => {
            setSharedView(null);
            setTab('landing');
          }}
        >
          <div className="brand-mark">SF</div>
          <div>
            <div className="brand-title">StackForge</div>
            <div className="brand-sub">CS2 Private 5v5 Intelligence • Random Maps</div>
          </div>
        </div>

        <nav className="nav-tabs" style={{ flexWrap: 'wrap' }}>
          <button
            className={`nav-tab ${tab === 'dashboard' && !sharedView ? 'active' : ''}`}
            onClick={() => {
              setSharedView(null);
              setTab('dashboard');
            }}
          >
            <LayoutDashboard size={15} /> Dashboard
          </button>
          <button
            className={`nav-tab ${tab === 'room' && !sharedView ? 'active' : ''}`}
            onClick={() => {
              setSharedView(null);
              setTab('room');
            }}
          >
            <Swords size={15} /> Match Room
          </button>
          <button
            className={`nav-tab ${tab === 'players' && !sharedView ? 'active' : ''}`}
            onClick={() => {
              setSharedView(null);
              setTab('players');
            }}
          >
            <Users size={15} /> Players ({players.length})
          </button>
          <button
            className={`nav-tab ${tab === 'stats' && !sharedView ? 'active' : ''}`}
            onClick={() => {
              setSharedView(null);
              setTab('stats');
            }}
          >
            <Activity size={15} /> Player Stats
          </button>
          <button
            className={`nav-tab ${tab === 'cards' && !sharedView ? 'active' : ''}`}
            onClick={() => {
              setSharedView(null);
              setTab('cards');
            }}
          >
            <Award size={15} /> Player Cards
          </button>
          <button
            className={`nav-tab ${tab === 'trust' && !sharedView ? 'active' : ''}`}
            onClick={() => {
              setSharedView(null);
              setTab('trust');
            }}
          >
            <Shield size={15} /> Trust Watch
          </button>
        </nav>

        <div className="topbar-meta">
          {health && (
            <>
              <span className={`badge ${health.providers.leetify !== 'not_configured' ? 'badge-ok' : ''}`}>
                Leetify: {health.providers.leetify === 'configured' ? 'Keyed' : 'Public'}
              </span>
              <span className={`badge ${health.providers.steam === 'configured' ? 'badge-ok' : ''}`}>
                Steam: {health.providers.steam === 'configured' ? 'Keyed' : 'Off'}
              </span>
            </>
          )}
          {auth.authenticated && auth.user ? (
            <button className="btn btn-xs" onClick={handleLogout} title="Sign out">
              <LogOut size={12} /> {auth.user.username}
            </button>
          ) : (
            <button
              className="btn btn-xs btn-primary"
              onClick={() => {
                setSharedView(null);
                setTab('landing');
              }}
            >
              <LogIn size={12} /> Account
            </button>
          )}
        </div>
      </header>

      <main className="main-content">
        {errorMsg && (
          <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>
            <span>{errorMsg}</span>
            <button className="btn btn-xs" onClick={() => setErrorMsg(null)}>
              Dismiss
            </button>
          </div>
        )}

        {loading ? (
          <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
            <p className="muted">Loading StackForge...</p>
          </div>
        ) : sharedView ? (
          <SharedLineupView
            roomTitle={sharedView.roomTitle}
            lineup={sharedView.lineup}
            onBack={() => {
              setSharedView(null);
              window.history.replaceState({}, '', '/');
            }}
          />
        ) : tab === 'landing' ? (
          <LandingAuthView
            auth={auth}
            onAuthChanged={setAuth}
            onEnterApp={() => setTab('room')}
            onError={setErrorMsg}
          />
        ) : tab === 'dashboard' ? (
          <DashboardView
            health={health}
            players={players}
            rooms={rooms}
            newRoomTitle={newRoomTitle}
            onNewRoomTitleChange={setNewRoomTitle}
            onCreateRoom={handleCreateRoom}
            onOpenRoom={(roomId) => {
              setActiveRoomId(roomId);
              setTab('room');
            }}
            onOpenProfile={handleOpenProfile}
            onOpenPlayers={() => setTab('players')}
            onError={setErrorMsg}
            onRefreshPlayers={refreshPlayers}
          />
        ) : tab === 'players' ? (
          <PlayerRegistryView
            players={players}
            onRefresh={refreshPlayers}
            onOpenProfile={handleOpenProfile}
            onError={setErrorMsg}
          />
        ) : tab === 'stats' ? (
          <PlayerStatsView
            players={players}
            selectedPlayerId={selectedProfileId}
            onSelectPlayerId={setSelectedProfileId}
            onRefreshPlayers={refreshPlayers}
            onError={setErrorMsg}
          />
        ) : tab === 'cards' ? (
          <PlayerCardsView
            players={players}
            onRefreshPlayers={refreshPlayers}
            onOpenProfile={handleOpenProfile}
            onError={setErrorMsg}
          />
        ) : tab === 'trust' ? (
          <TrustWatchView
            players={players}
            onOpenProfile={handleOpenProfile}
            onError={setErrorMsg}
          />
        ) : activeRoom ? (
          <div className="stack">
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <div className="row">
                <span className="small muted">Active Room:</span>
                <select
                  className="select"
                  style={{ width: '240px' }}
                  value={activeRoom.id}
                  onChange={(e) => setActiveRoomId(e.target.value)}
                >
                  {rooms.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.title} ({r.selected_count}/10 • {r.status})
                    </option>
                  ))}
                </select>
              </div>
              <form onSubmit={handleCreateRoom} className="row">
                <input
                  className="input"
                  style={{ width: '190px' }}
                  placeholder="New room title..."
                  value={newRoomTitle}
                  onChange={(e) => setNewRoomTitle(e.target.value)}
                />
                <button type="submit" className="btn btn-sm">
                  <Plus size={14} /> New Room
                </button>
              </form>
            </div>
            <MatchRoomView
              room={activeRoom}
              players={players}
              onRoomUpdated={handleRoomUpdated}
              onRefreshPlayers={refreshPlayers}
              onError={setErrorMsg}
              onOpenShareSlug={handleOpenShareSlug}
              onOpenProfile={handleOpenProfile}
            />
          </div>
        ) : (
          <div className="card" style={{ textAlign: 'center', padding: '3rem 1.5rem', maxWidth: '640px', margin: '1rem auto' }}>
            <h2>Start Your CS2 5v5 Match Room</h2>
            <p className="muted" style={{ margin: '0.6rem auto 1.2rem' }}>
              Create a match room, pick 10 players from your saved roster (or import your Google Sheet),
              generate balanced teams across all 126 partitions, handle swaps/remakes, and copy the Discord lineup.
            </p>
            <form onSubmit={handleCreateRoom} className="row" style={{ justifyContent: 'center' }}>
              <input
                className="input"
                style={{ width: '260px' }}
                placeholder="Match room name (e.g. Tonight's 5v5)"
                value={newRoomTitle}
                onChange={(e) => setNewRoomTitle(e.target.value)}
              />
              <button type="submit" className="btn btn-primary">
                <Plus size={16} /> Create Match Room
              </button>
            </form>
          </div>
        )}
      </main>
    </div>
  );
};
