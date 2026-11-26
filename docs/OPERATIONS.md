# StackForge Operations, Security & Rollback

---

## 1. Local Launcher & Process Safety (`Start-StackForge.ps1` / `.bat`)

- **Default V2 Ports:** Backend `127.0.0.1:8001` (`uvicorn app.main:app`) · Frontend `127.0.0.1:5174` (`vite --strictPort`, `VITE_API_TARGET=http://127.0.0.1:8001`).
- **PID Ownership & Isolation:** Managed child PIDs are recorded in gitignored `.stackforge-pids.json` (`managed: true`). Running `-Stop` terminates *only* verified launcher-managed `uvicorn`/`vite` processes; unrelated apps holding either port are reported and left untouched.
- **Runtime Logs:** Written to gitignored `logs/backend.{out,err}.log` and `logs/frontend.{out,err}.log`.

---

## 2. Configuration, Credentials & Security Hardening

### Secret Management
- Optional provider credentials (`STEAM_API_KEY`, `FACEIT_API_KEY`, `LEETIFY_API_KEY`) live either in gitignored `backend/.env` or encrypted server-side via **Windows DPAPI** (`CryptProtectData` in `backend/app/services/secrets_service.py` -> gitignored `.stackforge_secrets.dpapi.json`).
- Secrets are **never** stored in `stackforge.db`, **never** echoed back to browser clients (only `configured: bool` and masked `****1234` hints via `GET /api/settings/credentials`), and **never** bundled into Vite frontend assets.

### Application Threat Controls
- **Identity & Alias Spoofing:** Global deduplication locks to canonical string `SteamID64` and logs historical nicknames in append-only `player_aliases` so name changes cannot evade records or create duplicate entries.
- **False Accusations & Harassment:** Integrity classes stay separated (`OFFICIAL_ENFORCEMENT` vs `THIRD_PARTY_REPUTATION` vs `COMMUNITY_REPORT` vs `HUMAN_REVIEWED_EVIDENCE`); missing/private profiles and unindexed CSWatch records stay `UNKNOWN`/`STALE`/`PRIVATE`, never converted into clean badges or cheat accusations.
- **Tenant & Data Isolation:** Community notes, ratings, standings, and trust/watchlist records scope strictly by `community_id`.
- **LLM Explanation Guard:** Match explanations are generated deterministically from optimizer snapshots; any optional prose formatter may only rephrase structured metrics without inventing numbers or accusations.
- **Future Demo Upload Hardening (`P3`):** Enforce max size `<= 250 MB`, Source2 `.dem` header check, SHA-256 deduplication, filename sanitization, and isolated background `ProcessPoolExecutor(max_workers=1)` execution before enabling demo parsing.

---

## 3. Scheduler, Rate Limiting & `Ops & Keys` Telemetry

- **Freshness Coordinator (`refresh_coordinator.py`):** Uses single-flight per-player/provider locks and TTL caching (`steam_profile`: `900s`, `steam_bans`: `900s`, `leetify`: `1800s`, `faceit`: `1800s`, `cswatch`: `3600s` with `25 req/min` sliding cap).
- **Auto Scheduler (`scheduler.py`):** Triggered cleanly in FastAPI lifespan (automatically disabled when `PYTEST_CURRENT_TEST` is set), runs startup/periodic `86400s` stale sweeps, and reports live state via `GET /api/health` (`"scheduler": "active"` / `scheduler_detail`).
- **Operational Visibility (`GET /api/ops/overview`):** Surfaces honest per-provider ingestion health (`HEALTHY`, `PARTIAL_COVERAGE`, `NOT_CONFIGURED`, `DEGRADED`), rate-limit/private counts, stale or insufficient-data players with one-click individual refresh, and DPAPI key status.

---

## 4. Failure Modes & Recovery

| Component | Failure Mode | Runtime Behavior & Recovery |
|---|---|---|
| **Steam Community / Web API** | Timeout, private profile, or unset `STEAM_API_KEY` | Preserves last known `steam_persona_name`/`avatar_url`; bans report `NOT_CONFIGURED` or `UNAVAILABLE`; Match Room continues without blocking. |
| **Leetify Public API** | HTTP `429` or `privacy_mode: "private"` | Bounded `Retry-After <= 5s` (max 3 attempts); profile-only success when `/matches` fails saves `PARTIAL`; stats remain `None` rather than `0`. |
| **FACEIT Data API v4** | Unset `FACEIT_API_KEY` or `401/403/429` | Reports `NOT_CONFIGURED` / `RATE_LIMITED` cleanly; falls back to Steam-linked FACEIT `elo`/`level` if returned by Leetify. |
| **CSWatch Public API** | Unindexed (`stored=false`), `stale=true` (>24h Steam), or `>=25/min` cap | Maps explicitly to `UNKNOWN`, `STALE` (noting convictions remain `CURRENT` while Steam cache is `STALE`), or `RATE_LIMITED`. |
| **Google Sheets / File Import** | Invalid URL/sheet permissions or unmatched row | Shows preview errors before commit; preserves existing player edits during idempotent re-sync. |
| **SQLite Schema Evolution** | Startup after pull/update | `run_migrations()` (`backend/app/migrations.py`) applies idempotent additive `ALTER TABLE` / `CREATE TABLE IF NOT EXISTS` statements preserving legacy rows. |

---

## 5. Rollback & Release Safety Checklist

1. **Before risky DB changes:** Back up `backend/stackforge.db` (keep `.bak` copies out of git commits). Migrations must remain additive and backwards-compatible — never destructively drop legacy columns (`manual_rating` remains safely ignored in SQLite).
2. **Code rollback:** Revert application code via `git` while keeping existing SQLite columns intact so older/reverted app versions read cleanly without schema breakage.
3. **Secret hygiene before commit/release:** Verify `.env`, `*.dpapi.json`, `logs/`, `.stackforge-pids.json`, and scratch test DBs stay untracked in `.gitignore` and never appear in `git diff`.
4. **Release gate:**
   - Run `backend\.venv\Scripts\python.exe -m pytest -v` and confirm `0` failures.
   - Run `npm run build` inside `frontend/` cleanly.
   - Re-verify CSWatch `/developers` vs `/terms` status (`CLARIFICATION_REQUIRED` until explicit response from `support@cswatch.gg`), Steam `GetPlayerBans`, FACEIT Data API v4 limits, and attribution links before any public/shared hosting.
