# StackForge Development Guide, Rules & Testing

---

## 1. Binding Product, Data & Trust Rules

1. **Primary Match Workflow:** Optimize around selecting **10 unique players** cleanly (`0/10` -> `10/10` slots, no duplicate `player_id` or `steam_id64` in a room).
2. **Strict Random-Map Policy:** Never add a map selector, map veto, or pre-match map prediction to Match Room creation, balancing, or team explanations.
3. **Canonical Identity & Alias History:** Canonically key global players by string `SteamID64`; handle `/profiles/...`, `/id/...`, Leetify/CSWatch/FACEIT/CSStats URLs deterministically; log persona changes in append-only `player_aliases` rather than overwriting history or duplicating players.
4. **Source-Qualified Statistics Only:** Store `provider`, `scope`, `sample_size`, `captured_at`, and `freshness`. Unknown or unavailable metrics remain `None` / `Unavailable` (`kast` on Leetify v3 is unavailable and must stay `None` unless supplied by a demo or manual log). Legacy `manual_rating` never enters balancing (`norm_v2`).
5. **Separated Integrity Evidence Policy:**
   - **Never accuse:** StackForge reports *facts and external sources* (`OFFICIAL_ENFORCEMENT`, `THIRD_PARTY_REPUTATION`, `COMMUNITY_REPORT`, `DEMO_BEHAVIOURAL_SIGNAL`, `HUMAN_REVIEWED_EVIDENCE`), never guilty verdicts.
   - **Allowed language:** *"Public Steam record: 1 VAC ban recorded"* (with date/days), *"Public Steam record: 1 game ban recorded (app/game not specified)"*, *"CSWatch external reputation: High Risk (cswatch.gg) — third-party signal, not an official Valve verdict."*
   - **Forbidden language:** *"Confirmed cheater"* (from game ban or stats alone), *"Banned from CS2"* (without game context), *"Valve Trust Factor"* (for third-party estimates).
   - **No skill-to-cheat conflation:** High `ADR`, `HS%`, `aim_rating`, or fast `reaction_time_ms` never alter trust flags or trigger automatic watch entries; trust signals never alter skill ratings in team balancing.
6. **CS2 Player Cards (`card_rules_v1`):**
   - Positive/style titles require `sample_size >= 5`; negative roasts require `sample_size >= 8` or `>= 10`.
   - Players with missing stats or `< 5` matches default safely to *Uncharted Operative* / *Balanced All-Rounder* with zero negative roasts.
   - Humour stays strictly game-mechanics banter (utility, clutches, entries, saving) — never cheat insinuations — and supports per-player toggle (`humour_enabled`, `Mild`/`Spicy`/`Savage`, badge hiding, tagline reroll).

---

## 2. Dependencies & Development Environment

| Layer | Manifests | Verified Runtime Notes |
|---|---|---|
| **Backend Python** | `backend/requirements.txt` (runtime)<br>`backend/requirements-dev.txt` (test/dev)<br>`backend/pyproject.toml` | `requires-python = ">=3.11"` (project `.venv` runs `Python 3.13.5`; compatible with Python `3.12+`) |
| **Frontend Node** | `frontend/package.json`<br>`frontend/package-lock.json` | Verified on `Node.js v24.11.1`; React `18.3.1`, TypeScript `5.6.3`, Vite `5.4.11`, `lucide-react` `0.460.0` |

### Audited Direct Python Runtime Packages (`backend/requirements.txt`)
Derived from static AST import scanning of `backend/app/` and runtime entrypoints (`uvicorn` launch + FastAPI multipart uploads + `.xlsx` spreadsheet import):
- `fastapi` (web framework & OpenAPI)
- `uvicorn[standard]` (ASGI server invoked by launcher & manual run)
- `SQLAlchemy` (ORM & additive SQLite schema management)
- `pydantic` (request/response validation)
- `httpx` (async HTTP client for Steam, Leetify, FACEIT, CSWatch, Google Sheets)
- `openpyxl` (`.xlsx` workbook parsing in `import_service.py`)
- `python-multipart` (required at runtime by FastAPI `UploadFile` / `Form` endpoints in `routes/platform.py`)

### Audited Test/Dev Addition (`backend/requirements-dev.txt`)
- Includes `-r requirements.txt` plus `pytest` for automated verification (`backend/tests/`).

Note: `backend/stackforge.db` and `backend/.venv` contain live local state and preinstalled packages; verify dependency changes in a **temporary clean virtual environment** rather than altering production state.

---

## 3. Canonical CS2 Metric Registry (`metric_registry.py`)

`GET /api/metrics/registry` exposes the authoritative schema for all 24 tracked dimensions, ensuring unit parity between providers, SQLite storage, normalization, and UI cards:
- **Ladder Scales:** `premier_rating`, `leetify_rating` (normalized across profile rank vs match decimal scales), `faceit_elo`, `faceit_level` (`1–10`).
- **Mechanics & Aim (`[0, 100]` / units):** `aim_rating`, `utility_rating`, `positioning_rating`, `preaim` (`0–180°`), `reaction_time_ms` (`50–2500 ms`; converts Leetify match `reaction_time` seconds -> ms), `spotted_accuracy`, `spray_accuracy`, `hs_pct`.
- **Combat & Teamplay:** `adr` (`0–300`), `kd_ratio` (`0–10`), `win_rate`, `opening_duel_pct`, `trade_kills_per_match`, `traded_deaths_pct` (blended with `positioning_rating` into `positioning_score`), `utility_damage_per_round`, `flash_assists_per_round` (calibrated to `[0.002, 0.080]`/rd), `enemies_flashed_per_round`, `clutch_win_pct`, `consistency_score` (`counter_strafing_good_shots_ratio`), `kast` (`None` on Leetify v3 until demo/manual data exists).

Out-of-range or corrupt upstream numbers are sanitized to `None` rather than clamping into plausible fake values or `0`.

---

## 4. Testing Strategy & Acceptance Checklist

### Implemented Test Suites (`backend/tests/`)
- `test_providers.py` — Provider fail-safe defaults (`NOT_CONFIGURED` / `NOT_LINKED`) when credentials or IDs are absent.
- `test_identity_and_cards.py` — Canonical SteamID64 deduplication, alias history preservation on Steam rename, cache retention on provider failure, additive SQLite migrations, and `card_rules_v1` sample thresholds.
- `test_optimizer.py` — `norm_v2` scaling, missing-data unknown handling, 126-partition uniqueness, deterministic seed replay, hard constraints, and regeneration exhaustion.
- `test_api_workflow.py` — Match-room end-to-end API flow: create room -> fill 10 -> preflight -> generate -> swap preview & swap -> lock/regenerate -> restore -> finalize -> share slug.
- `test_onboarding_and_cs2_explanations.py` — Real-roster onboarding deduplication, CSWatch flag isolation, and CS2-native explanation grounding.
- `test_platform_evolution.py` — Auth sessions, Google Sheet preview/commit/sync, watchlist flows, and multi-route platform checks.
- `test_player_intelligence_v2.py` — Individual refresh scoping, `manual_rating` removal from matchmaking, DPAPI vault encryption behavior, and `Ops & Keys` telemetry.
- `test_pipeline_validation.py` — End-to-end canonical metric lineage, `positioning_rating` + `traded_deaths_pct` wiring, post-match lifecycle (`RESULT_RECORDED`, `GET /api/standings/community`), scheduler active-state behavior, and CSWatch `UNKNOWN`/`STALE`/`FLAGGED` + conviction-freshness semantics.

### Standard Pre-Commit Checks

```powershell
# 1. Backend full test suite
cd D:\CS2_StackForge\backend
.\.venv\Scripts\python.exe -m pytest -v

# 2. Frontend TypeScript typecheck + Vite production bundle
cd D:\CS2_StackForge\frontend
npm run build
```

### Bug Triage Checklist
When reporting or fixing a regression, record:
1. **Reproduction steps** + affected endpoints/components
2. **Expected vs actual behavior** (including SQLite/provider snapshot evidence)
3. **Root cause** & **regression test** added in `backend/tests/`
4. **Rollback / mitigation** check confirming no irreversible DB corruption.
