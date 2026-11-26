# StackForge — CS2 Private 5v5 Match Organizer

StackForge helps a private CS2 community select ten players, inspect source-qualified player statistics and separated integrity signals, generate explainable 5v5 teams across random maps, negotiate swaps/remakes, finalize a shareable Discord lineup, and record private community match outcomes.

---

## Core Guarantees

- **Random maps only:** No map picker, map veto, or pre-match map recommendation exists; historical map statistics act strictly as internal pool-robustness inputs.
- **Real data over manual ratings:** Matchmaking (`norm_v2` / `stackforge_126_v2`) uses fetched CS2 statistics and competitive ladder scales, leaving unavailable metrics as explicit unknowns (`None`) rather than zeroes or manual ratings.
- **Separated integrity evidence:** Official enforcement (`Steam GetPlayerBans`, FACEIT bans), third-party reputation (`CSWatch`, currently `CLARIFICATION_REQUIRED`), community reports, and moderator reviews remain distinct; no stat anomaly or third-party score equals a cheat verdict or Valve Trust Factor.
- **Read-only integrations:** StackForge never injects into CS2, reads game memory, automates Valve queues, or scrapes Cloudflare-gated/prohibited websites.

---

## Quick Start (Windows Local V2 — Ports `8001` / `5174`)

Double-click [Start-StackForge.bat](file:///d:/CS2_StackForge/Start-StackForge.bat) in `D:\CS2_StackForge`, or run:

```powershell
D:\CS2_StackForge\Start-StackForge.bat
# Stop launcher-managed processes cleanly:
D:\CS2_StackForge\Start-StackForge.bat -Stop
```

Open `http://127.0.0.1:5174/`. Supports `-NoBrowser`, `-BackendPort <port>`, and `-FrontendPort <port>` (details in [Operations Guide](docs/OPERATIONS.md)). For manual environment setup, dependency installation (`Python 3.12.10` baseline), testing, and production builds, see [Development Guide](docs/DEVELOPMENT.md).

---

## Maintained Documentation

StackForge keeps exactly five maintained Markdown documents, each with strict single-source ownership:

- [Architecture, Metrics, Matchmaking & Trust Model](docs/ARCHITECTURE.md) — system boundaries, verified file map, SQLite schema, canonical 24-metric registry, `norm_v2`/`stackforge_126_v2` engine, match lifecycle, integrity/card model, ADRs, REST endpoints, and deferred `.dem` design.
- [Development, Dependencies, Commands & Testing](docs/DEVELOPMENT.md) — supported `Python 3.12.10` / Node `24.11.1` baseline, audited `requirements*.txt` (stdlib `asyncio` scheduler; no external scheduler library), manual setup, `pytest` / `npm run build` commands, and acceptance checklist.
- [External Integrations, Credentials & Compliance](docs/INTEGRATIONS.md) — provider behaviour, official API checks, DPAPI/`backend/.env` key acquisition, CSWatch `CLARIFICATION_REQUIRED` review (with draft non-sent email), candidate demo parsers, and evaluated ecosystem sources.
- [Operations, Launcher, Backups & Troubleshooting](docs/OPERATIONS.md) — Windows launcher & PID isolation, DPAPI secret storage, runtime scheduler telemetry, SQLite backups/migrations, failure recovery, troubleshooting, and rollback checklist.
