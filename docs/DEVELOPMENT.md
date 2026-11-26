# StackForge Development Guide, Dependencies & Testing

---

## 1. Supported Environment Baseline

| Layer | Manifests | Verified Baseline |
|---|---|---|
| **Backend Python** | `backend/requirements.txt` (runtime)<br>`backend/requirements-dev.txt` (test/dev)<br>`backend/pyproject.toml` | **`Python 3.12.10`** documented baseline (`requires-python = ">=3.11"`; verified cleanly in isolated `Python 3.12.10` venv and active `Python 3.13.5` `.venv`) |
| **Frontend Node** | `frontend/package.json`<br>`frontend/package-lock.json` | **`Node.js v24.11.1`** (`React 18.3.1`, `TypeScript 5.6.3`, `Vite 5.4.11`, `lucide-react 0.460.0`) |

---

## 2. Audited Python Dependencies (`backend/requirements*.txt`)

Derived by AST scanning all non-stdlib imports across `backend/app/` and verifying runtime FastAPI/Uvicorn entrypoints:

### `backend/requirements.txt` (Direct Runtime Dependencies Only)
- `fastapi==0.165.0` — REST API framework & OpenAPI schemas
- `httpx==0.28.1` — Async external provider HTTP client (`TestClient` test transport support)
- `openpyxl==3.1.5` — `.xlsx` spreadsheet import parsing (`import_service.py`)
- `pydantic==2.14.4` — Typed configuration and request/response validation
- `python-multipart==0.0.34` — FastAPI multipart `UploadFile` / `Form` parsing (`routes/platform.py`)
- `SQLAlchemy==2.1.9` — ORM models and additive SQLite schema management
- `uvicorn[standard]==0.54.0` — ASGI runtime server used by the launcher and manual startup

### `backend/requirements-dev.txt`
- `-r requirements.txt` plus `pytest==9.2.0` (`anyio` plugin arrives transitively via FastAPI/HTTPX).

### Scheduler Implementation Note
- **`APScheduler` (or any external job scheduler library) is NOT used or required.** Periodic stale-player sweeps in `backend/app/services/scheduler.py` use Python standard-library `asyncio` tasks (`asyncio.Task`, `asyncio.sleep`, `asyncio.create_task`).

---

## 3. Manual Environment Setup & Run Commands

### Backend Setup & Server (`http://127.0.0.1:8001`)

```powershell
cd D:\CS2_StackForge\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

### Frontend Setup & Dev Server (`http://127.0.0.1:5174/`)

```powershell
cd D:\CS2_StackForge\frontend
npm install
$env:VITE_API_TARGET = "http://127.0.0.1:8001"
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

Verify dependency upgrades in a **disposable temporary virtualenv** rather than modifying `backend/.venv` or `backend/stackforge.db` directly.

---

## 4. Testing, Build Commands & Triage

### Standard Verification Commands

```powershell
# 1. Dependency integrity check
cd D:\CS2_StackForge\backend
.\.venv\Scripts\python.exe -m pip check

# 2. Backend automated test suite (isolated temp/in-memory DB fixtures)
.\.venv\Scripts\python.exe -m pytest -v

# 3. Frontend TypeScript typecheck & Vite production build
cd D:\CS2_StackForge\frontend
npm run build
```

> **Note:** When running ad-hoc `python -c "from app.main import app"` checks outside `backend/`, set `DATABASE_URL` to a temporary SQLite path so SQLAlchemy never initializes an unwanted `stackforge.db` in the working directory.

### Implemented Backend Suites (`backend/tests/`)
- `test_providers.py` — provider `NOT_CONFIGURED` / `NOT_LINKED` fail-safe checks.
- `test_identity_and_cards.py` — `SteamID64` deduplication, append-only `PlayerAlias` lookup, cache retention on provider outage, additive `run_migrations()`, and `card_rules_v1` sample thresholds.
- `test_optimizer.py` — `norm_v2` missing-unknown handling, 126 unique partitions, deterministic seed repeatability, hard constraints, and regeneration exhaustion.
- `test_api_workflow.py` — full match-room flow (`create -> fill 10 -> preflight -> generate -> swap -> lock/regenerate -> restore -> finalize -> share`).
- `test_onboarding_and_cs2_explanations.py` — duplicate prevention, CSWatch flag isolation, and CS2-native explanation checks.
- `test_platform_evolution.py` — CSV/XLSX/Google Sheet import, identity resolver, separated watchlist reviews, and auth sessions.
- `test_player_intelligence_v2.py` — individual refresh scoping, removal of `manual_rating` from team balancing, Leetify `429` backoff, and DPAPI/Ops telemetry.
- `test_pipeline_validation.py` — canonical metric bounds, `positioning_rating` + `traded_deaths_pct` lineage, post-match results (`RESULT_RECORDED`, `/api/standings/community`), scheduler active-state behavior, and CSWatch `UNKNOWN`/`STALE`/`FLAGGED` + separate Steam vs conviction freshness semantics.

### Bug Triage Checklist
Record for every bug fix: (1) reproduction steps, (2) expected vs actual state/snapshots, (3) root cause & new regression test in `backend/tests/`, and (4) confirmation of safe migration/rollback behavior.
