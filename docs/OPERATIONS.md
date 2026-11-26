# StackForge Operations, Launcher, Backups & Troubleshooting

---

## 1. Local Windows Launcher (`Start-StackForge.ps1` / `.bat`)

- **Default V2 Ports:** Backend `127.0.0.1:8001` (`uvicorn app.main:app`) · Frontend `127.0.0.1:5174` (`vite --strictPort`, `VITE_API_TARGET=http://127.0.0.1:8001`).
- **Process Ownership Safety:** Managed child PIDs are written to gitignored `.stackforge-pids.json` (`managed: true`). `-Stop` terminates *only* verified StackForge-owned `uvicorn`/`vite` processes; unrelated listeners on port `8001` or `5174` are reported and never killed.
- **Flags:** `-Stop`, `-NoBrowser`, `-BackendPort <port>`, `-FrontendPort <port>`.
- **Logs:** Written to gitignored `logs/backend.{out,err}.log` and `logs/frontend.{out,err}.log`.

---

## 2. Deployment Secrets & Security Controls

### Server-Side Secret Vault
- Optional API keys (`STEAM_API_KEY`, `FACEIT_API_KEY`, `LEETIFY_API_KEY`) live either in gitignored `backend/.env` or encrypted server-side via **Windows DPAPI** (`CryptProtectData` in `backend/app/services/secrets_service.py` -> gitignored `.stackforge_secrets.dpapi.json`).
- Keys are never stored inside `backend/stackforge.db`, never logged or returned in plaintext (`GET /api/settings/credentials` exposes `configured: bool` and masked `****1234` hints only), and never bundled into `frontend/`.

### Operational Security Controls
- Community data (`notes`, ratings snapshot views, community standings, trust reports/watchlist) stays scoped by `community_id`.
- `.env`, `*.dpapi.json`, `.stackforge-pids.json`, and `logs/` remain gitignored; temporary test DBs should stay in system temp directories via `DATABASE_URL`.
- Future `.dem` uploads (`P3`, currently disabled) require `<= 250 MB` limit, Source2 header validation, SHA-256 deduplication, filename sanitization, and single-process background execution (`ProcessPoolExecutor(max_workers=1)`).

---

## 3. Runtime Scheduler & `Ops & Keys` Telemetry

- **Freshness Coordinator (`refresh_coordinator.py`):** Per-player/provider single-flight locks and cache TTLs (`steam_profile`: `900s`, `steam_bans`: `900s`, `leetify`: `1800s`, `faceit`: `1800s`, `cswatch`: `3600s` with `25 req/min` sliding cap).
- **In-Process Asyncio Scheduler (`scheduler.py`):** Uses Python standard-library `asyncio` (no external scheduler package), runs startup and periodic `86400s` stale sweeps, disables cleanly when `STACKFORGE_DISABLE_SCHEDULER=1` or `"pytest" in sys.modules`, and reports state via `GET /api/health`.
- **`Ops & Keys` (`GET /api/ops/overview`):** Surfaces honest per-provider health (`HEALTHY`, `PARTIAL_COVERAGE`, `NOT_CONFIGURED`, `DEGRADED`), rate-limit/private counts, stale/insufficient players with one-click refresh, and DPAPI key status.

---

## 4. Troubleshooting, Failure Recovery & SQLite Backups

| Issue / Failure | Runtime Behaviour & Troubleshooting Action |
|---|---|
| **Port `8001` or `5174` occupied** | Re-run with custom ports, e.g. `.\Start-StackForge.ps1 -BackendPort 8011 -FrontendPort 5184`. |
| **Missing `.venv` or `node_modules`** | Recreate backend `.venv` on `Python 3.12.10` (`pip install -r backend\requirements-dev.txt`) or run `npm install` in `frontend/`. |
| **Steam Community / Web API errors** | Preserves cached persona/avatar; missing `STEAM_API_KEY` reports `NOT_CONFIGURED` cleanly without blocking Match Room flows. |
| **Leetify `429` or private profile** | Bounded `Retry-After <= 5s` (max 3 attempts); profile-only success when `/matches` fails stores `PARTIAL`; missing fields stay `None`. |
| **FACEIT `NOT_CONFIGURED` / `429`** | Falls back safely without blocking; Steam-linked FACEIT ELO/level still ingests via Leetify when exposed. |
| **CSWatch `UNKNOWN` / `STALE` / `>=25/min`** | Maps explicitly to `UNKNOWN`, `STALE` (preserving current convictions vs >24h Steam cache), or `RATE_LIMITED`. |
| **SQLite backups & migrations** | Keep manual backups (`backend/stackforge.db.bak*`) outside git commits. Startup `run_migrations()` (`migrations.py`) executes idempotent additive `ALTER TABLE` / `CREATE TABLE IF NOT EXISTS` statements preserving legacy rows. |

---

## 5. Rollback & Release Checklist

1. **Database safety:** Back up `backend/stackforge.db` before schema changes; keep migrations strictly additive (never drop legacy columns such as `manual_rating`).
2. **Code rollback:** Revert application commits via `git` cleanly — additive SQLite schema remains backwards-compatible.
3. **Release verification gate:**
   - Run `pip check` and `pytest -v` in `backend/` (`0` failures).
   - Run `npm run build` inside `frontend/`.
   - Confirm secret hygiene (`git status`, `.gitignore`) and review [Integrations Compliance](INTEGRATIONS.md) before any shared/public hosting (CSWatch remains `CLARIFICATION_REQUIRED`).
