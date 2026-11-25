# StackForge — CS2 Private 5v5 Match Organizer

StackForge helps an existing CS2 group select ten players, inspect real player data and separated integrity signals, generate balanced 5v5 teams across random maps (no map picker), negotiate swaps/remakes, and post a finalized Discord lineup.

## Quick Start (How to Run)

### 1. Backend (FastAPI + SQLite)

```powershell
cd d:\CS2_StackForge\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- Database: SQLite (`backend/stackforge.db`, automatically migrated on startup via `run_migrations`).
- Optional API keys (place in `backend/.env`, never commit):
  - `STEAM_API_KEY` — enables official Steam Web API `GetPlayerBans` & keyed summaries/vanity resolution (without it, StackForge falls back to read-only Steam Community `?xml=1` for personas/avatars/vanity URLs and reports `GetPlayerBans` as `NOT_CONFIGURED`).
  - `FACEIT_API_KEY` — enables FACEIT Data API v4 (`ELO`, level, CS2 lifetime stats); otherwise reported as `NOT_CONFIGURED`.
  - `LEETIFY_API_KEY` — optional key header for higher Leetify rate limits (public v3 works keyless with pacing/retry).

### 2. Frontend (React + Vite)

```powershell
cd d:\CS2_StackForge\frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173/`.

### 3. Tests & Production Build

```powershell
cd d:\CS2_StackForge\backend
.\.venv\Scripts\python.exe -m pytest -v

cd d:\CS2_StackForge\frontend
npm run build
```

## Documentation

Read `Userflow.md`, `Rules.md`, then [docs/HANDOVER.md](docs/HANDOVER.md).

- **Critical product rule:** maps are random. There is no map picker or map veto. Map-specific performance is used privately to make team splits robust across the active map pool.
- **External integrations:** see [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) for active APIs (`Steam XML`, `Leetify Public v3`, `CSWatch Public API`, `Google Sheets CSV`), keyed-only APIs (`Steam Bans`, `FACEIT v4`), and link-only/unsupported sites (no scraping of `csstats.gg`, `tracker.gg`, `faceitanalyser.com`, or `trustfactor.gg`).
