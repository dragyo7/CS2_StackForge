import React, { useState } from 'react';
import {
  Activity,
  CheckCircle2,
  Edit3,
  FileSpreadsheet,
  History,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  Trash2,
  Upload,
  UserCheck,
  UserX,
} from 'lucide-react';
import { api, ApiError } from '../api';
import type { BulkImportResponse, Player, RoleType } from '../types';
import { ROLES } from '../types';
import { CommunityImportPanel } from './CommunityImportPanel';
import { PlayerAvatar } from './PlayerAvatar';

interface Props {
  players: Player[];
  onRefresh: () => Promise<void>;
  onOpenProfile?: (playerId: string) => void;
  onError: (msg: string) => void;
}

export const PlayerRegistryView: React.FC<Props> = ({
  players,
  onRefresh,
  onOpenProfile,
  onError,
}) => {
  const [search, setSearch] = useState('');
  const [showImportPanel, setShowImportPanel] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [editing, setEditing] = useState<Player | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Add / Edit form fields
  const [displayName, setDisplayName] = useState('');
  const [steamInput, setSteamInput] = useState('');
  const [manualRating, setManualRating] = useState('55');
  const [premierRating, setPremierRating] = useState('');
  const [faceitElo, setFaceitElo] = useState('');
  const [leetifyRating, setLeetifyRating] = useState('');
  const [primaryRole, setPrimaryRole] = useState<RoleType | ''>('');
  const [notes, setNotes] = useState('');

  // Bulk import
  const [bulkText, setBulkText] = useState('');
  const [bulkDefaultRating, setBulkDefaultRating] = useState('50');
  const [allowManualNames, setAllowManualNames] = useState(true);
  const [bulkResult, setBulkResult] = useState<BulkImportResponse | null>(null);

  const openAdd = () => {
    setEditing(null);
    setFormError(null);
    setDisplayName('');
    setSteamInput('');
    setManualRating('55');
    setPremierRating('');
    setFaceitElo('');
    setLeetifyRating('');
    setPrimaryRole('');
    setNotes('');
    setShowAddForm(true);
  };

  const openEdit = (p: Player) => {
    setEditing(p);
    setFormError(null);
    setDisplayName(p.display_name);
    setSteamInput(p.steam_id64 || p.steam_profile_url || '');
    setManualRating(String(p.manual_rating));
    setPremierRating(p.premier_rating != null ? String(p.premier_rating) : '');
    setFaceitElo(p.faceit_elo != null ? String(p.faceit_elo) : '');
    setLeetifyRating(p.leetify_rating != null ? String(p.leetify_rating) : '');
    setPrimaryRole(p.primary_role || '');
    setNotes(p.notes || '');
    setShowAddForm(true);
  };

  const handleSavePlayer = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      const trimmedSteam = steamInput.trim();
      const isRawId = /^7656119\d{10}$/.test(trimmedSteam);
      const isUrl = trimmedSteam.includes('steamcommunity.com');

      if (editing) {
        await api.updatePlayer(editing.id, {
          display_name: displayName.trim(),
          steam_id64: isRawId ? trimmedSteam : trimmedSteam ? undefined : null,
          steam_profile_url: isUrl ? trimmedSteam : undefined,
          manual_rating: Number(manualRating) || 50,
          premier_rating: premierRating ? Number(premierRating) : undefined,
          clear_premier: !premierRating && editing.premier_rating != null,
          faceit_elo: faceitElo ? Number(faceitElo) : undefined,
          clear_faceit: !faceitElo && editing.faceit_elo != null,
          leetify_rating: leetifyRating ? Number(leetifyRating) : undefined,
          clear_leetify: !leetifyRating && editing.leetify_rating != null,
          primary_role: primaryRole || undefined,
          clear_primary_role: !primaryRole && editing.primary_role != null,
          notes: notes.trim(),
        });
      } else {
        await api.createPlayer({
          display_name: displayName.trim(),
          steam_id64: isRawId ? trimmedSteam : null,
          steam_profile_url: isUrl ? trimmedSteam : !isRawId && trimmedSteam ? trimmedSteam : null,
          manual_rating: Number(manualRating) || 50,
          premier_rating: premierRating ? Number(premierRating) : null,
          faceit_elo: faceitElo ? Number(faceitElo) : null,
          leetify_rating: leetifyRating ? Number(leetifyRating) : null,
          primary_role: primaryRole || null,
          notes: notes.trim() || null,
        });
      }
      setShowAddForm(false);
      await onRefresh();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to save player.';
      setFormError(msg);
      onError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (p: Player) => {
    if (!window.confirm(`Remove ${p.display_name} from this community? (Global Steam identity & match records are preserved.)`)) {
      return;
    }
    setBusy(true);
    try {
      await api.deletePlayer(p.id);
      await onRefresh();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Failed to remove player.');
    } finally {
      setBusy(false);
    }
  };

  const handleArchive = async (p: Player) => {
    const nextArchived = !p.is_archived;
    if (nextArchived && !window.confirm(`Archive ${p.display_name}? They will be hidden from active match selection until unarchived.`)) {
      return;
    }
    setBusy(true);
    try {
      await api.archivePlayer(p.id, nextArchived);
      await onRefresh();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Failed to update archive status.');
    } finally {
      setBusy(false);
    }
  };

  const handleRefreshAll = async () => {
    setBusy(true);
    try {
      await api.refreshAllPlayers(true);
      await onRefresh();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Batch refresh failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleBulkImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bulkText.trim()) return;
    setBusy(true);
    try {
      const res = await api.bulkImport(bulkText, Number(bulkDefaultRating) || 50, allowManualNames);
      setBulkResult(res);
      await onRefresh();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Bulk import failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleSeedDemo = async () => {
    setBusy(true);
    try {
      await api.seedDemoPlayers();
      await onRefresh();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Failed to seed demo players.');
    } finally {
      setBusy(false);
    }
  };

  const handleQuickRefresh = async (playerId: string) => {
    setBusy(true);
    try {
      await api.refreshPlayerProfile(playerId, true);
      await onRefresh();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Profile refresh failed.');
    } finally {
      setBusy(false);
    }
  };

  const filtered = players.filter((p) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    const aliasMatch = p.aliases.some(
      (a) =>
        a.alias_name.toLowerCase().includes(q) ||
        (a.previous_name && a.previous_name.toLowerCase().includes(q)),
    );
    return (
      p.display_name.toLowerCase().includes(q) ||
      (p.steam_id64 && p.steam_id64.includes(q)) ||
      (p.steam_persona_name && p.steam_persona_name.toLowerCase().includes(q)) ||
      (p.vanity_name && p.vanity_name.toLowerCase().includes(q)) ||
      (p.primary_role && p.primary_role.toLowerCase().includes(q)) ||
      aliasMatch
    );
  });

  return (
    <div className="stack">
      <div className="card">
        <div className="card-header">
          <div>
            <h2>Player Registry ({players.length})</h2>
            <p className="muted" style={{ margin: '0.2rem 0 0' }}>
              Persistent roster for your CS2 stack. SteamID64 is stored as a string; manual ratings work offline without API keys.
            </p>
          </div>
          <div className="row">
            <button
              className={`btn ${showImportPanel ? 'btn-primary' : ''}`}
              onClick={() => setShowImportPanel(!showImportPanel)}
              disabled={busy}
            >
              <FileSpreadsheet size={15} /> {showImportPanel ? 'Hide Sheet & Identity' : 'Sheet Import & Resolver'}
            </button>
            <button className="btn" onClick={handleRefreshAll} disabled={busy || players.length === 0}>
              <RefreshCw size={15} /> Refresh All
            </button>
            <button className="btn" onClick={handleSeedDemo} disabled={busy}>
              <Sparkles size={15} /> Load 10 Demo Players
            </button>
            <button
              className="btn"
              onClick={() => {
                setBulkResult(null);
                setShowBulkModal(true);
              }}
              disabled={busy}
            >
              <Upload size={15} /> Bulk Paste
            </button>
            <button className="btn btn-primary" onClick={openAdd} disabled={busy}>
              <Plus size={15} /> Add Player
            </button>
          </div>
        </div>

        {showImportPanel && (
          <div style={{ marginBottom: '1rem' }}>
            <CommunityImportPanel
              players={players}
              onImported={onRefresh}
              onError={onError}
              onOpenProfile={onOpenProfile}
            />
          </div>
        )}

        <div className="row" style={{ marginBottom: '0.85rem' }}>
          <div style={{ position: 'relative', flex: '1 1 280px' }}>
            <Search
              size={15}
              style={{ position: 'absolute', left: '0.7rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
            />
            <input
              className="input"
              style={{ paddingLeft: '2.1rem' }}
              placeholder="Search by nickname, SteamID64, or role..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        {filtered.length === 0 ? (
          <div className="card" style={{ background: 'var(--bg-canvas)', textAlign: 'center', padding: '2rem' }}>
            <p className="muted">
              {players.length === 0
                ? 'No saved players yet. Add your 10 players manually, paste SteamID64s in Bulk Import, or load the 10 labeled Demo Players.'
                : 'No players match that search filter.'}
            </p>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(330px, 1fr))', gap: '0.75rem' }}>
            {filtered.map((p) => {
              const prevAlias = p.aliases.find((a) => a.previous_name)?.previous_name;
              return (
                <div key={p.id} className="card" style={{ background: 'var(--bg-elevated)', padding: '0.85rem' }}>
                  <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div className="row" style={{ gap: '0.6rem', minWidth: 0 }}>
                      <PlayerAvatar name={p.display_name} avatarUrl={p.avatar_url} role={p.primary_role} size={38} />
                      <div style={{ minWidth: 0 }}>
                        <div className="row" style={{ gap: '0.35rem' }}>
                          <strong style={{ fontSize: '0.95rem' }}>{p.display_name}</strong>
                          {p.primary_role && <span className="badge">{p.primary_role}</span>}
                          {p.is_seeded && <span className="badge badge-warn">DEMO SAMPLE</span>}
                        </div>
                        <div className="small muted mono" style={{ marginTop: '0.15rem' }}>
                          {p.steam_id64 ? (
                            <span style={{ color: 'var(--ok)' }}>SteamID64: {p.steam_id64}</span>
                          ) : (
                            <span style={{ color: 'var(--warn)' }}>Manual only (no SteamID64 linked)</span>
                          )}
                        </div>
                        {prevAlias && (
                          <div className="small muted" style={{ marginTop: '0.12rem' }}>
                            <History size={11} style={{ verticalAlign: 'text-bottom', marginRight: '0.2rem' }} />
                            Previously: {prevAlias}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="row" style={{ gap: '0.25rem' }}>
                      {onOpenProfile && (
                        <button className="btn btn-xs btn-primary" title="Open profile & stats" onClick={() => onOpenProfile(p.id)}>
                          <Activity size={12} /> Profile
                        </button>
                      )}
                      {p.steam_id64 && (
                        <button className="btn btn-xs" title="Refresh Steam profile" onClick={() => handleQuickRefresh(p.id)} disabled={busy}>
                          <RefreshCw size={12} />
                        </button>
                      )}
                      <button className="btn btn-xs" title="Edit player" onClick={() => openEdit(p)}>
                        <Edit3 size={12} />
                      </button>
                      <button
                        className="btn btn-xs"
                        title={p.is_archived ? 'Unarchive player' : 'Archive player'}
                        onClick={() => handleArchive(p)}
                      >
                        {p.is_archived ? 'Unarchive' : 'Archive'}
                      </button>
                      <button className="btn btn-xs btn-danger" title="Remove from community" onClick={() => handleDelete(p)}>
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>

                  <div className="divider" style={{ margin: '0.55rem 0' }} />

                  <div className="row" style={{ justifyContent: 'space-between', fontSize: '0.8rem' }}>
                    <div>
                      <span className="muted">Normalized: </span>
                      <strong className="mono">{p.normalized_strength.toFixed(1)}</strong>{' '}
                      <span className="badge">{p.strength_band}</span>
                    </div>
                    <span className="small muted">
                      Conf {Math.round(p.confidence * 100)}% • Manual {p.manual_rating}
                    </span>
                  </div>

                  <div className="row" style={{ marginTop: '0.45rem', gap: '0.35rem', justifyContent: 'space-between' }}>
                    <div className="row" style={{ gap: '0.35rem' }}>
                      {p.premier_rating != null && (
                        <span className="badge">Premier {p.premier_rating.toLocaleString()}</span>
                      )}
                      {p.faceit_elo != null && <span className="badge">FACEIT {p.faceit_elo}</span>}
                      {p.leetify_rating != null && (
                        <span className="badge">
                          Leetify {p.leetify_rating >= 0 ? '+' : ''}{p.leetify_rating.toFixed(2)}
                        </span>
                      )}
                      {p.card && p.card.eligible_count > 0 && (
                        <span className="badge badge-a">{p.card.primary_title}</span>
                      )}
                    </div>
                    <span className="small muted">
                      {p.last_successful_refresh_at
                        ? `Updated ${new Date(p.last_successful_refresh_at).toLocaleDateString()}`
                        : p.refresh_status}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {showAddForm && (
        <div className="modal-backdrop">
          <div className="modal">
            <div className="card-header">
              <h3>{editing ? `Edit ${editing.display_name}` : 'Add Player'}</h3>
              <button className="btn btn-xs" onClick={() => setShowAddForm(false)}>
                Close
              </button>
            </div>
            {formError && (
              <div className="alert alert-danger" style={{ marginBottom: '0.75rem' }}>
                <span className="small">{formError}</span>
              </div>
            )}
            <form onSubmit={handleSavePlayer} className="stack">
              <div className="form-grid">
                <div>
                  <label className="field-label">Display Name / Nickname *</label>
                  <input
                    className="input"
                    required
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="e.g. Kairo"
                  />
                </div>
                <div>
                  <label className="field-label">SteamID64 or Profile URL (optional)</label>
                  <input
                    className="input mono"
                    value={steamInput}
                    onChange={(e) => setSteamInput(e.target.value)}
                    placeholder="7656119... or steamcommunity.com/profiles/..."
                  />
                </div>
                <div>
                  <label className="field-label">Manual Skill Rating (1–100) *</label>
                  <input
                    className="input mono"
                    type="number"
                    min={1}
                    max={100}
                    step="0.5"
                    required
                    value={manualRating}
                    onChange={(e) => setManualRating(e.target.value)}
                  />
                </div>
                <div>
                  <label className="field-label">Primary Role</label>
                  <select
                    className="select"
                    value={primaryRole}
                    onChange={(e) => setPrimaryRole(e.target.value as RoleType | '')}
                  >
                    <option value="">Unassigned</option>
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="field-label">Premier Rating (optional)</label>
                  <input
                    className="input mono"
                    type="number"
                    min={0}
                    max={45000}
                    value={premierRating}
                    onChange={(e) => setPremierRating(e.target.value)}
                    placeholder="e.g. 16500"
                  />
                </div>
                <div>
                  <label className="field-label">FACEIT ELO (optional)</label>
                  <input
                    className="input mono"
                    type="number"
                    min={100}
                    max={5000}
                    value={faceitElo}
                    onChange={(e) => setFaceitElo(e.target.value)}
                    placeholder="e.g. 1750"
                  />
                </div>
                <div>
                  <label className="field-label">Leetify Rating (optional)</label>
                  <input
                    className="input mono"
                    type="number"
                    step="0.01"
                    min={-1}
                    max={1}
                    value={leetifyRating}
                    onChange={(e) => setLeetifyRating(e.target.value)}
                    placeholder="e.g. 0.03"
                  />
                </div>
              </div>
              <div>
                <label className="field-label">Notes</label>
                <input
                  className="input"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Optional teammate notes"
                />
              </div>
              <div className="row" style={{ justifyContent: 'flex-end' }}>
                <button type="button" className="btn" onClick={() => setShowAddForm(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={busy}>
                  {busy ? 'Saving...' : editing ? 'Save Changes' : 'Create Player'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showBulkModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <div className="card-header">
              <h3>Bulk Import Players</h3>
              <button className="btn btn-xs" onClick={() => setShowBulkModal(false)}>
                Close
              </button>
            </div>
            <form onSubmit={handleBulkImport} className="stack">
              <p className="muted small" style={{ margin: 0 }}>
                Paste one entry per line: SteamID64, Steam <code>/profiles/</code> URL, Steam <code>/id/</code> URL,
                or nickname (supports <code>Name | 75 | AWPer</code>). Display names are never treated as verified Steam identities.
              </p>
              <textarea
                className="textarea mono"
                rows={7}
                value={bulkText}
                onChange={(e) => setBulkText(e.target.value)}
                placeholder={
                  '76561198000000001\nhttps://steamcommunity.com/profiles/76561198000000002\nhttps://steamcommunity.com/id/customvanity\nAlex | 72 | IGL'
                }
              />
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <label className="row small" style={{ cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={allowManualNames}
                    onChange={(e) => setAllowManualNames(e.target.checked)}
                  />
                  Save plain names as unverified manual profiles
                </label>
                <div className="row">
                  <span className="small muted">Default Rating</span>
                  <input
                    className="input mono"
                    style={{ width: '75px' }}
                    type="number"
                    min={1}
                    max={100}
                    value={bulkDefaultRating}
                    onChange={(e) => setBulkDefaultRating(e.target.value)}
                  />
                </div>
              </div>
              <div className="row" style={{ justifyContent: 'flex-end' }}>
                <button type="submit" className="btn btn-primary" disabled={busy || !bulkText.trim()}>
                  {busy ? 'Importing...' : 'Run Import'}
                </button>
              </div>
            </form>

            {bulkResult && (
              <div className="stack" style={{ marginTop: '1rem' }}>
                <div className="row">
                  <span className="badge badge-ok">Created: {bulkResult.created_count}</span>
                  <span className="badge badge-warn">Duplicates: {bulkResult.duplicate_count}</span>
                  <span className="badge">Unresolved: {bulkResult.unresolved_count}</span>
                  <span className="badge badge-danger">Invalid: {bulkResult.invalid_count}</span>
                </div>
                <div className="stack" style={{ gap: '0.4rem', maxHeight: '220px', overflowY: 'auto' }}>
                  {bulkResult.entries.map((entry, idx) => (
                    <div key={idx} className="player-row" style={{ padding: '0.45rem 0.6rem' }}>
                      <div style={{ minWidth: 0 }}>
                        <div className="mono small" style={{ wordBreak: 'break-all' }}>{entry.line}</div>
                        <div className="small muted">{entry.message}</div>
                      </div>
                      <span
                        className={`badge ${
                          entry.status.startsWith('CREATED')
                            ? 'badge-ok'
                            : entry.status === 'DUPLICATE'
                              ? 'badge-warn'
                              : entry.status === 'INVALID'
                                ? 'badge-danger'
                                : ''
                        }`}
                      >
                        {entry.status === 'CREATED_STEAM' && <UserCheck size={12} />}
                        {entry.status === 'CREATED_MANUAL' && <CheckCircle2 size={12} />}
                        {entry.status === 'DUPLICATE' && <ShieldAlert size={12} />}
                        {(entry.status === 'UNRESOLVED' || entry.status === 'INVALID') && <UserX size={12} />}
                        {entry.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
