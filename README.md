# StackForge — CS2 Private 5v5 Match Organizer

StackForge helps an existing CS2 community select ten players, inspect source-qualified player statistics and separated integrity signals, generate explainable 5v5 teams across random maps, negotiate swaps/remakes, finalize a shareable Discord lineup, and record private community match outcomes.

---

## Non-Negotiable Product & Safety Rules

- **Random maps only:** StackForge never provides a map picker, map veto, or pre-match map recommendation. Historical map statistics remain internal robustness inputs across the active map pool.
- **Real data over manual ratings:** Matchmaking (`norm_v2` / `stackforge_126_v2`) uses fetched CS2 statistics and competitive ladder scales rather than manual host ratings. Missing values remain explicit (`Unavailable` / `None`), never zero-filled.
- **Separated integrity evidence:** Official enforcement (`Steam GetPlayerBans`, FACEIT bans), third-party reputation (`CSWatch`), community reports, and moderator reviews are stored and displayed separately. No stat anomaly, missing profile, or third-party score is an automatic cheat conviction or equivalent to Valve Trust Factor.
- **Read-only integrations:** StackForge never injects into CS2, reads game memory, automates Valve queues, or scrapes Cloudflare-gated/prohibited sites.

---

## One-Click Local Startup & Shutdown (Windows)

StackForge includes a Windows launcher in the repository root that manages only its own Uvicorn backend (`http://127.0.0.1:8001`) and Vite frontend (`http://127.0.0.1:5174/`), isolates output under `logs/`, and tracks managed PIDs in `.stackforge-pids.json`.

### Start

Double-click `Start-StackForge.bat` in `D:\CS2_StackForge`, or run:

```cmd
D:\CS2_StackForge\Start-StackForge.bat
```

Or via PowerShell:

```powershell
D:\CS2_StackForge\Start-StackForge.ps1
```

Key launcher behaviours:
1. Checks prerequisites (`backend\.venv\Scripts\python.exe`, `node`, `frontend\node_modules\vite\bin\vite.js`) without silently reinstalling packages.
2. Checks `http://127.0.0.1:8001/api/health` (`status == "ok"` and `map_policy == "random_no_picker"`) and `http://127.0.0.1:5174/`.
3. Reuses already-healthy StackForge processes and refuses to terminate unrelated processes if another app holds port `8001` or `5174`.
4. Starts FastAPI (`uvicorn app.main:app`) in `backend/` and Vite (`VITE_API_TARGET=http://127.0.0.1:8001`) in `frontend/`, writes `logs\{backend,frontend}.{out,err}.log`, records managed PIDs, and opens the browser.

### Stop

```powershell
D:\CS2_StackForge\Start-StackForge.bat -Stop
# or
D:\CS2_StackForge\Start-StackForge.ps1 -Stop
```

### Optional Flags

| Flag | Default | Description |
|---|---|---|
| `-Stop` | off | Stop launcher-managed StackForge backend/frontend processes cleanly |
| `-NoBrowser` | off | Start and verify health without opening a browser tab |
| `-BackendPort <port>` | `8001` | Override backend listen port & Vite `/api` proxy target |
| `-FrontendPort <port>` | `5174` | Override frontend Vite listen port |

---

## Manual Setup, Run & Verification

### 1. Backend (FastAPI + SQLite)

```powershell
cd D:\CS2_StackForge\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

- Uses `backend/stackforge.db` (SQLite, automatically evolved via additive `run_migrations()` on startup).
- Works keyless out of the box using Steam Community `?xml=1`, Leetify Public CS API v3, CSWatch Public API (see [permission review note](docs/INTEGRATIONS.md#cswatch)), and Google Sheets CSV exports.
- Optional server-side API keys (`STEAM_API_KEY`, `FACEIT_API_KEY`, `LEETIFY_API_KEY`) can be entered in the **Ops & Keys** tab (Windows DPAPI vault) or placed in `backend/.env` (never commit secrets).

### 2. Frontend (React + TypeScript + Vite)

```powershell
cd D:\CS2_StackForge\frontend
npm install
$env:VITE_API_TARGET = "http://127.0.0.1:8001"
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

Open `http://127.0.0.1:5174/`.

### 3. Tests & Production Build

```powershell
cd D:\CS2_StackForge\backend
.\.venv\Scripts\python.exe -m pytest -v

cd D:\CS2_StackForge\frontend
npm run build
```

---

## Maintained Documentation

StackForge keeps exactly five maintained Markdown documents:

- [Architecture, Data Model & API Reference](docs/ARCHITECTURE.md) — system boundaries, verified file map, SQLite schema, `norm_v2`/`stackforge_126_v2` balancing, match lifecycle, architecture decisions, and REST endpoints.
- [Development, Product Rules & Testing](docs/DEVELOPMENT.md) — binding product/trust rules, card rules (`card_rules_v1`), canonical metric registry, Python/Node packaging, and test acceptance criteria.
- [External Integrations & Ecosystem Compliance](docs/INTEGRATIONS.md) — official/keyless/rejected CS2 sources, CSWatch ToS vs `/developers` compliance analysis (`CLARIFICATION_REQUIRED`), official API verification, and demo-parser comparison (`Awpy` vs `demoparser2`).
- [Operations, Security & Rollback](docs/OPERATIONS.md) — launcher operations, Windows DPAPI secret storage, scheduler & `Ops & Keys` telemetry, threat model, failure recovery, and rollback checklist.
