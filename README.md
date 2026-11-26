# StackForge — CS2 Private 5v5 Match Organizer

StackForge helps an existing CS2 group select ten players, inspect real player data and separated integrity signals, generate balanced 5v5 teams across random maps (no map picker), negotiate swaps/remakes, and post a finalized Discord lineup.

---

## One-Click Local Startup & Shutdown (Windows V2 — Ports `8001` / `5174`)

StackForge includes a zero-touch Windows launcher in the repository root that starts the V2 backend (`http://127.0.0.1:8001`) and frontend (`http://127.0.0.1:5174/`), works from any working directory, isolates logs to `logs/`, and safely tracks only its own processes in `.stackforge-pids.json`.

### Start

- **Double-click** `Start-StackForge.bat` in `D:\CS2_StackForge`, or run from any terminal:

```cmd
D:\CS2_StackForge\Start-StackForge.bat
```

Or via PowerShell:

```powershell
D:\CS2_StackForge\Start-StackForge.ps1
```

**What the launcher does:**
1. Validates prerequisites (`backend\.venv\Scripts\python.exe`, `node`, `frontend\node_modules\vite\bin\vite.js`) without auto-reinstalling dependencies.
2. Checks `http://127.0.0.1:8001/api/health` (`status == "ok"` and `map_policy == "random_no_picker"`) and `http://127.0.0.1:5174/`.
3. **Reuses healthy StackForge instances** if already running (safe to click twice; never spawns duplicate servers).
4. **Never kills unrelated apps** — if port `8001` or `5174` is bound by another application, it prints the owning process/command and exits cleanly without terminating it.
5. Launches Uvicorn (`app.main:app`) in `D:\CS2_StackForge\backend` and Vite in `D:\CS2_StackForge\frontend` (`VITE_API_TARGET=http://127.0.0.1:8001`), waits for both health checks, writes `logs\{backend,frontend}.{out,err}.log`, records PIDs in `.stackforge-pids.json`, and opens `http://127.0.0.1:5174/`.

### Stop

```powershell
D:\CS2_StackForge\Start-StackForge.bat -Stop
# or
D:\CS2_StackForge\Start-StackForge.ps1 -Stop
```

Only processes marked `managed: true` in `.stackforge-pids.json` (and verified as StackForge `uvicorn`/`vite` processes) are terminated. Externally started or unrelated processes are left untouched.

### Optional Flags

| Flag | Default | Description |
|---|---|---|
| `-Stop` | off | Stop launcher-managed StackForge backend/frontend processes cleanly |
| `-NoBrowser` | off | Start and verify health without opening a browser tab |
| `-BackendPort <port>` | `8001` | Override backend listen port & Vite `/api` proxy target |
| `-FrontendPort <port>` | `5174` | Override frontend Vite listen port |

### Troubleshooting

- **Missing `.venv` or `node_modules`:** Create the virtualenv (`cd backend && python -m venv .venv && .\.venv\Scripts\pip install -r requirements.txt`) or install frontend deps (`cd frontend && npm install`), then re-run `Start-StackForge.bat`.
- **Port conflict with another app:** Pass custom ports without touching other services, e.g. `.\Start-StackForge.ps1 -BackendPort 8011 -FrontendPort 5184`.
- **Inspect runtime logs:** Check `logs\backend.out.log`, `logs\backend.err.log`, `logs\frontend.out.log`, and `logs\frontend.err.log`.

---

## Manual Run (Fallback)

### 1. Backend (FastAPI + SQLite)

```powershell
cd d:\CS2_StackForge\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

- Database: SQLite (`backend/stackforge.db`, automatically migrated on startup via `run_migrations`).
- Optional API keys (place in `backend/.env`, never commit):
  - `STEAM_API_KEY` — enables official Steam Web API `GetPlayerBans` & keyed summaries/vanity resolution (without it, StackForge falls back to read-only Steam Community `?xml=1` for personas/avatars/vanity URLs and reports `GetPlayerBans` as `NOT_CONFIGURED`).
  - `FACEIT_API_KEY` — enables FACEIT Data API v4 (`ELO`, level, CS2 lifetime stats); otherwise reported as `NOT_CONFIGURED`.
  - `LEETIFY_API_KEY` — optional key header for higher Leetify rate limits (public v3 works keyless with pacing/retry).

### 2. Frontend (React + Vite)

```powershell
cd d:\CS2_StackForge\frontend
$env:VITE_API_TARGET = "http://127.0.0.1:8001"
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

Open `http://127.0.0.1:5174/`.

### 3. Tests & Production Build

```powershell
cd d:\CS2_StackForge\backend
.\.venv\Scripts\python.exe -m pytest -v

cd d:\CS2_StackForge\frontend
npm run build
```

---

## Documentation

Read `Userflow.md`, `Rules.md`, then [docs/HANDOVER.md](docs/HANDOVER.md).

- **Critical product rule:** maps are random. There is no map picker or map veto. Map-specific performance is used privately to make team splits robust across the active map pool.
- **External integrations & Player Intelligence V2:**
  - Read-only APIs active without keys: **Steam Community XML** (`?xml=1` personas/avatars/vanity), **Leetify Public CS API v3** (`premier`, `leetify`, `aim`, `utility`, `positioning`, `preaim`, `reaction_time_ms`, accuracy, combat & recent matches with `Retry-After`/429 backoff), **CSWatch Public API** (25/min cap), and **Google Sheets CSV**.
  - Keyed APIs (`NOT_CONFIGURED` until keys set): Official Steam `GetPlayerBans` (`STEAM_API_KEY`) and FACEIT Data API v4 (`FACEIT_API_KEY`).
  - Unsupported / never scraped: `csstats.gg` (ID link extraction only), `tracker.gg`, `faceitanalyser.com`, `trustfactor.gg`.
  - Matchmaking excludes `manual_rating` (removed from UI/imports too), separates scales (`norm_v2`, `stackforge_126_v2`), wires `positioning_rating` + `traded_deaths_pct` cleanly, freezes computed sub-dimension scores per generation, supports single-player refresh (`POST /api/players/{id}/refresh`), runs an active 24h/startup/login stale-profile scheduler, supports post-match result recording & separate community standings, and includes an OS DPAPI optional credential vault in `Ops & Keys`.
  - See [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md), [docs/AUDIT_AND_ROADMAP.md](docs/AUDIT_AND_ROADMAP.md), [docs/API.md](docs/API.md), [docs/DEMO_PIPELINE.md](docs/DEMO_PIPELINE.md), [docs/features/PLAYER_INTELLIGENCE.md](docs/features/PLAYER_INTELLIGENCE.md), and [docs/features/MATCH_EXPLANATIONS.md](docs/features/MATCH_EXPLANATIONS.md).
