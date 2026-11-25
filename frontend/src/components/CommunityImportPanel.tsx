import React, { useEffect, useState } from 'react';
import {
  CheckCircle2,
  FileSpreadsheet,
  Link2,
  RefreshCw,
  Search,
  ShieldAlert,
  Upload,
} from 'lucide-react';
import { api, ApiError } from '../api';
import type {
  ImportHistoryItem,
  Player,
  ResolveIdentityResponse,
  SpreadsheetPreview,
} from '../types';

const COMMUNITY_SHEET_URL =
  'https://docs.google.com/spreadsheets/d/1iakYU0vzcceZ1AYjgndrwwEkaeAt6Bym3dIjzS41reM/edit?usp=drivesdk';

interface Props {
  players: Player[];
  onImported: () => Promise<void>;
  onError: (msg: string) => void;
  onOpenProfile?: (playerId: string) => void;
}

export const CommunityImportPanel: React.FC<Props> = ({
  players,
  onImported,
  onError,
  onOpenProfile,
}) => {
  const [sheetUrl, setSheetUrl] = useState(COMMUNITY_SHEET_URL);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<SpreadsheetPreview | null>(null);
  const [previewSource, setPreviewSource] = useState<'gsheet' | 'file' | null>(null);
  const [overwriteManual, setOverwriteManual] = useState(false);
  const [defaultRating, setDefaultRating] = useState('55');
  const [history, setHistory] = useState<ImportHistoryItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [statusBanner, setStatusBanner] = useState<string | null>(null);

  // Universal identity resolver state
  const [resolveQuery, setResolveQuery] = useState('');
  const [resolveResult, setResolveResult] = useState<ResolveIdentityResponse | null>(null);
  const [linkTargetId, setLinkTargetId] = useState('');

  const loadHistory = async () => {
    try {
      setHistory(await api.importHistory());
    } catch {
      // ignore non-critical history error
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const handlePreviewSheet = async () => {
    setBusy(true);
    setStatusBanner(null);
    try {
      const res = await api.previewGoogleSheet(sheetUrl.trim(), null, Number(defaultRating) || 55);
      setPreview(res);
      setPreviewSource('gsheet');
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Could not preview Google Sheet.');
    } finally {
      setBusy(false);
    }
  };

  const handlePreviewFile = async (file: File) => {
    setSelectedFile(file);
    setBusy(true);
    setStatusBanner(null);
    try {
      const res = await api.previewFileImport(file, null, Number(defaultRating) || 55);
      setPreview(res);
      setPreviewSource('file');
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Could not preview uploaded spreadsheet.');
    } finally {
      setBusy(false);
    }
  };

  const handleCommit = async () => {
    if (!preview || !previewSource) return;
    setBusy(true);
    try {
      const res =
        previewSource === 'gsheet'
          ? await api.commitGoogleSheet(
              sheetUrl.trim(),
              preview.mapping,
              overwriteManual,
              Number(defaultRating) || 55,
            )
          : await api.commitFileImport(
              selectedFile!,
              JSON.stringify(preview.mapping),
              overwriteManual,
              Number(defaultRating) || 55,
            );
      setStatusBanner(
        `Import complete: Created ${res.summary.created}, Matched ${res.summary.matched}, Updated ${res.summary.updated}, Unresolved ${res.summary.unresolved}.`,
      );
      setPreview(null);
      await onImported();
      await loadHistory();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Spreadsheet commit failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleSyncNow = async (importId: string) => {
    setBusy(true);
    try {
      const res = await api.syncImport(importId, overwriteManual);
      setStatusBanner(
        `Sync complete (${res.changed_from_previous ? 'Changes detected' : 'No row changes'}): Created ${res.summary.created}, Matched ${res.summary.matched}.`,
      );
      await onImported();
      await loadHistory();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Google Sheet sync failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleResolve = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resolveQuery.trim()) return;
    setBusy(true);
    try {
      const res = await api.resolveIdentity(resolveQuery.trim(), true);
      setResolveResult(res);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Identity resolution failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleConfirmCandidate = async () => {
    if (!resolveResult || !linkTargetId) return;
    const sid = resolveResult.resolved_steam_id64;
    const prov = resolveResult.provider_discoveries.find((d) => d.external_id);
    if (!sid && !prov?.external_id) return;
    setBusy(true);
    try {
      await api.confirmIdentity({
        community_player_id: linkTargetId,
        provider: prov?.provider || 'steam',
        external_id: prov?.external_id || sid!,
        profile_url: prov?.profile_url || (sid ? `https://steamcommunity.com/profiles/${sid}` : null),
        steam_id64: sid,
      });
      setStatusBanner('Identity link confirmed and saved.');
      await onImported();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Could not confirm identity link.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      {statusBanner && (
        <div className="alert alert-ok">
          <span className="small">{statusBanner}</span>
          <button className="btn btn-xs" onClick={() => setStatusBanner(null)}>OK</button>
        </div>
      )}

      {/* Spreadsheet & Google Sheet Import */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3>
              <FileSpreadsheet size={16} style={{ verticalAlign: 'text-bottom', marginRight: '0.35rem' }} />
              Community Spreadsheet Import & Read-Only Sync
            </h3>
            <p className="muted small" style={{ margin: '0.2rem 0 0' }}>
              Import from Google Sheets, CSV, or XLSX with column mapping, preview, duplicate detection, and manual-edit preservation.
            </p>
          </div>
          <div className="row">
            <span className="small muted">Default Rating</span>
            <input
              className="input mono"
              style={{ width: '68px' }}
              type="number"
              min={1}
              max={100}
              value={defaultRating}
              onChange={(e) => setDefaultRating(e.target.value)}
            />
          </div>
        </div>

        <div className="stack" style={{ gap: '0.65rem' }}>
          <div className="row">
            <input
              className="input mono"
              style={{ flex: 1 }}
              value={sheetUrl}
              onChange={(e) => setSheetUrl(e.target.value)}
              placeholder="https://docs.google.com/spreadsheets/d/..."
            />
            <button className="btn btn-primary" disabled={busy || !sheetUrl.trim()} onClick={handlePreviewSheet}>
              Preview Google Sheet
            </button>
          </div>

          <div className="row" style={{ justifyContent: 'space-between' }}>
            <label className="btn btn-sm" style={{ cursor: 'pointer' }}>
              <Upload size={14} /> Upload CSV / XLSX
              <input
                type="file"
                accept=".csv,.xlsx"
                style={{ display: 'none' }}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handlePreviewFile(f);
                }}
              />
            </label>
            <label className="row small" style={{ cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={overwriteManual}
                onChange={(e) => setOverwriteManual(e.target.checked)}
              />
              Overwrite existing manual ratings/names on conflict
            </label>
          </div>
        </div>

        {preview && (
          <div className="card" style={{ background: 'var(--bg-canvas)', marginTop: '0.85rem' }}>
            <div className="card-header">
              <div className="row" style={{ gap: '0.4rem' }}>
                <strong>Preview ({preview.total_rows} rows)</strong>
                <span className="badge badge-ok">New: {preview.counts.NEW || 0}</span>
                <span className="badge">Matched: {preview.counts.MATCHED_EXISTING || 0}</span>
                <span className="badge badge-warn">Conflicts: {preview.counts.CONFLICT || 0}</span>
                <span className="badge badge-warn">Duplicates: {preview.counts.DUPLICATE_IN_SHEET || 0}</span>
                <span className="badge badge-danger">Unresolved: {preview.counts.UNRESOLVED || 0}</span>
              </div>
              <button className="btn btn-ok btn-sm" disabled={busy} onClick={handleCommit}>
                <CheckCircle2 size={14} /> Commit Import
              </button>
            </div>

            <div className="form-grid" style={{ marginBottom: '0.75rem' }}>
              {(['display_name', 'real_name', 'identity_url', 'steam_id64', 'manual_rating', 'primary_role'] as const).map((field) => (
                <div key={field}>
                  <label className="field-label">{field}</label>
                  <select
                    className="select"
                    value={preview.mapping[field] || ''}
                    onChange={(e) =>
                      setPreview({
                        ...preview,
                        mapping: { ...preview.mapping, [field]: e.target.value || null },
                      })
                    }
                  >
                    <option value="">(unmapped)</option>
                    {preview.headers.map((h) => (
                      <option key={h} value={h}>{h}</option>
                    ))}
                  </select>
                </div>
              ))}
            </div>

            <div className="stack" style={{ gap: '0.35rem', maxHeight: '260px', overflowY: 'auto' }}>
              {preview.rows.map((r) => (
                <div key={r.row_number} className="player-row" style={{ padding: '0.45rem 0.65rem' }}>
                  <div style={{ minWidth: 0 }}>
                    <div className="row" style={{ gap: '0.4rem' }}>
                      <span className="mono small muted">#{r.row_number}</span>
                      <strong>{r.normalized.display_name || '(no name)'}</strong>
                      {r.normalized.real_name && r.normalized.real_name !== r.normalized.display_name && (
                        <span className="small muted">({r.normalized.real_name})</span>
                      )}
                      {r.normalized.steam_id64 && (
                        <span className="mono small" style={{ color: 'var(--ok)' }}>{r.normalized.steam_id64}</span>
                      )}
                    </div>
                    <div className="small muted">{r.message}</div>
                  </div>
                  <span
                    className={`badge ${
                      r.status === 'NEW'
                        ? 'badge-ok'
                        : r.status === 'MATCHED_EXISTING'
                          ? ''
                          : r.status === 'UNRESOLVED' || r.status === 'INVALID'
                            ? 'badge-danger'
                            : 'badge-warn'
                    }`}
                  >
                    {r.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {history.length > 0 && (
          <div className="stack" style={{ marginTop: '0.85rem', gap: '0.35rem' }}>
            <strong className="small muted">RECENT IMPORTS & SAVED SYNCS</strong>
            {history.slice(0, 4).map((h) => (
              <div key={h.id} className="player-row" style={{ padding: '0.45rem 0.65rem' }}>
                <div>
                  <div className="row" style={{ gap: '0.4rem' }}>
                    <strong className="small">{h.source_label}</strong>
                    <span className="badge">{h.source_type}</span>
                    <span className="small muted mono">hash {h.content_hash.slice(0, 8)}</span>
                  </div>
                  <div className="small muted">
                    Last sync: {h.last_successful_sync_at ? new Date(h.last_successful_sync_at).toLocaleString() : 'Never'} •
                    Created {h.summary.created || 0}, Matched {h.summary.matched || 0}
                  </div>
                </div>
                {h.source_url && (
                  <button className="btn btn-xs btn-primary" disabled={busy} onClick={() => handleSyncNow(h.id)}>
                    <RefreshCw size={12} /> Sync Now
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Universal Identity Resolver */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3>
              <Link2 size={16} style={{ verticalAlign: 'text-bottom', marginRight: '0.35rem' }} />
              Universal Player Identity Resolver
            </h3>
            <p className="muted small" style={{ margin: '0.2rem 0 0' }}>
              Paste a SteamID64, Steam profile/vanity URL, CSStats URL, Leetify URL, FACEIT URL, or nickname to resolve & discover cross-provider profiles.
            </p>
          </div>
        </div>

        <form onSubmit={handleResolve} className="row">
          <div style={{ position: 'relative', flex: 1 }}>
            <Search
              size={14}
              style={{ position: 'absolute', left: '0.65rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
            />
            <input
              className="input mono"
              style={{ paddingLeft: '2rem' }}
              value={resolveQuery}
              onChange={(e) => setResolveQuery(e.target.value)}
              placeholder="https://csstats.gg/player/7656119... or SteamID64 / Leetify / FACEIT / nickname"
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={busy || !resolveQuery.trim()}>
            {busy ? 'Resolving...' : 'Resolve Identity'}
          </button>
        </form>

        {resolveResult && (
          <div className="card" style={{ background: 'var(--bg-canvas)', marginTop: '0.75rem' }}>
            <div className="row" style={{ justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <div className="row" style={{ gap: '0.4rem' }}>
                <span
                  className={`badge ${
                    resolveResult.confidence_state === 'VERIFIED'
                      ? 'badge-ok'
                      : resolveResult.confidence_state === 'CANDIDATE'
                        ? 'badge-warn'
                        : 'badge-danger'
                  }`}
                >
                  {resolveResult.confidence_state}
                </span>
                <span className="badge">{resolveResult.identifier_type}</span>
                {resolveResult.resolved_steam_id64 && (
                  <span className="mono small">SteamID64: {resolveResult.resolved_steam_id64}</span>
                )}
              </div>
              <span className="small muted">{resolveResult.message}</span>
            </div>

            {resolveResult.matched_existing.length > 0 && (
              <div className="stack" style={{ gap: '0.35rem', marginBottom: '0.6rem' }}>
                <strong className="small muted">MATCHED COMMUNITY PLAYERS</strong>
                {resolveResult.matched_existing.map((m) => (
                  <div key={m.community_player_id} className="player-row" style={{ padding: '0.4rem 0.6rem' }}>
                    <div>
                      <strong>{m.display_name}</strong>
                      <div className="small muted">{m.match_reason}</div>
                    </div>
                    <div className="row">
                      <span className="badge">{m.confidence_state}</span>
                      {onOpenProfile && (
                        <button className="btn btn-xs btn-primary" onClick={() => onOpenProfile(m.community_player_id)}>
                          Open Profile
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {resolveResult.provider_discoveries.length > 0 && (
              <div className="stack" style={{ gap: '0.35rem' }}>
                <strong className="small muted">CROSS-PROVIDER DISCOVERIES</strong>
                {resolveResult.provider_discoveries.map((d, idx) => (
                  <div key={idx} className="player-row" style={{ padding: '0.4rem 0.6rem' }}>
                    <div>
                      <div className="row" style={{ gap: '0.35rem' }}>
                        <strong className="small">{d.provider.toUpperCase()}</strong>
                        <span className={`badge ${d.status === 'OK' || d.status === 'VERIFIED_ID' ? 'badge-ok' : ''}`}>
                          {d.status}
                        </span>
                        {d.persona_name && <span className="small">{d.persona_name}</span>}
                        {d.premier_rating != null && <span className="badge">Premier {d.premier_rating}</span>}
                        {d.reputation_score != null && (
                          <span className="badge">CSWatch {d.reputation_score}/100 ({d.risk_level})</span>
                        )}
                      </div>
                      <div className="small muted">{d.summary}</div>
                    </div>
                    {d.profile_url && (
                      <a className="btn btn-xs" href={d.profile_url} target="_blank" rel="noreferrer">
                        Open
                      </a>
                    )}
                  </div>
                ))}
              </div>
            )}

            {players.length > 0 && resolveResult.resolved_steam_id64 && (
              <div className="row" style={{ marginTop: '0.65rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border)' }}>
                <ShieldAlert size={14} color="var(--warn)" />
                <span className="small muted">Confirm & attach to an existing manual player:</span>
                <select
                  className="select"
                  style={{ width: '210px' }}
                  value={linkTargetId}
                  onChange={(e) => setLinkTargetId(e.target.value)}
                >
                  <option value="">Choose player...</option>
                  {players.map((p) => (
                    <option key={p.id} value={p.id}>{p.display_name}</option>
                  ))}
                </select>
                <button className="btn btn-xs btn-primary" disabled={!linkTargetId || busy} onClick={handleConfirmCandidate}>
                  Confirm Link
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
