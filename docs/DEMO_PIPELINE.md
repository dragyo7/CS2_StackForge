# StackForge — Asynchronous CS2 `.dem` Replay Pipeline Architecture (Phase 6 Design)

Status: **Designed & Researched (Disabled until justified; Queue placeholder visible in Ops Health)**.

## 1. Parser Evaluation: `Awpy` vs `demoparser2` vs `demo-anticheat`

| Dimension | `pnxenopoulos/awpy` | `LaihoE/demoparser` (`demoparser2`) | `TimAnthonyAlexander/demo-anticheat` |
|---|---|---|---|
| **Docs / Repo** | https://awpy.readthedocs.io/en/latest/ | https://github.com/LaihoE/demoparser | https://github.com/TimAnthonyAlexander/demo-anticheat |
| **Core Engine** | Rust (`pbdems2`) + PyO3 Python emitting **Polars** DataFrames / Parquet | Native Rust core with Python (`demoparser2`), JS/TS, WASM bindings | Standalone **Go** CLI / analyzer |
| **License** | MIT License | MIT License | Open-source repo (verify commit `LICENSE` before reuse) |
| **Windows Compatibility** | Precompiled Windows wheels (Python 3.11–3.15); no Rust compiler needed | Precompiled Windows Python wheels (`pip install demoparser2`) | Separate Go binary / toolchain runtime |
| **CS2 `.dem` (`PBDEMS2`)** | Full CS2 demo support | Full CS2 demo support | CS2 demo support |
| **Out-of-the-Box Analytics** | **Round reconstruction, kills, damages, flash/smoke states, visibility & nav helpers, KAST, ADR, trades** | Raw database-style tick/property queries (`X,Y,Z`, viewangles, weapon events); custom KAST/trade code required | Heuristic/anomaly anti-cheat flags (research reference only) |
| **Processing Speed** | ~1–4s per 60–150 MB 5v5 `.dem` cleanly in background process | Extreme raw throughput (~328–740+ MB/s depending on NVMe/CPU) | Single-demo sweep |
| **Maintainability in StackForge** | **Best fit** for StackForge's Python 3.13 + FastAPI monolith | Good fallback only for custom tick-level analytics | Lower (cross-language IPC; non-authoritative verdicts) |
| **Recommendation** | **RECOMMENDED SINGLE PARSER** (`P3` default) | Fallback candidate only | **RESEARCH ONLY (never auto-labels players)** |

---

## 2. Target End-to-End Architecture (Modular Monolith Safe)

```
[.dem / .dem.bz2 Upload]
   │  (size <= 250 MB, magic header / HL2DEMO validation, SHA-256 hash dedup)
   ▼
[Immutable Demo Storage + `demo_uploads` DB row (`PENDING`)]
   │
   ▼
[Single-Process Async Background Worker (ProcessPoolExecutor max_workers=1)]
   │  (Runs completely outside FastAPI HTTP request lifecycle)
   ▼
[Parser: Awpy (pinned parser_version)]
   │
   ├──► [Metric Extractor: KAST, ADR, K/D, Opening Duels, Trade Kills, Traded Deaths, Flash Assists, Clutch 1vX, Util Dmg]
   │
   ├──► [Verified SteamID64 Matcher]
   │        • Match ONLY by SteamID64 extracted from demo player table
   │        • NEVER auto-merge on ambiguous display nicknames
   │
   └──► [Optional Behavioural Signals -> `DEMO_BEHAVIOURAL_SIGNAL`]
            • Must expose evidence, sample count, confidence & limitations
            • Never auto-convicts or punishes a member
   │
   ▼
[Matchroom Linkage + Immutable `player_stat_snapshots` (`provider="community_demo"`, `is_sample_demo=False`)]
   │  • Links to finalized `match_rooms` (`RESULT_RECORDED -> ANALYZED`)
   │  • Records `parser_version`, `demo_sha256`, `map_name`, `rounds_count`, `captured_at`
   ▼
[Community Internal Analytics (`GET /api/standings/community`)]
```

---

## 3. Non-Negotiable Safety & Integrity Guards

1. **No Live Room Blocking:** Uploading or parsing a demo never blocks `MatchRoom` creation, swaps, or team generation. Keep demo parsing disabled until safe isolated queueing is needed.
2. **File Validation & Size Bounds:** Verify HL2/Source2 `.dem` header bytes + max compressed/uncompressed cap (`250 MB`) + reject path traversal + compute `sha256` before queuing.
3. **Immutable Evidence:** Raw demo bytes remain read-only/immutable per job ID until retention expiry; failure transitions job to `FAILED` with structured error without mutating existing stats.
4. **Canonical Identity Only:** Player rows from `.dem` tick tables carry SteamID64; unknown SteamID64s either prompt host linking (`CANDIDATE` review) or remain unlinked (`UNRESOLVED`), never guessing by nickname.
5. **External Rating Separation:** Metrics extracted from private custom matches are tagged `provider="community_demo"` and feed community analytics independently of Valve Premier, FACEIT, or Leetify public ratings.
6. **Evidence Governance:** Any demo-derived behavioural anomaly belongs strictly to `DEMO_BEHAVIOURAL_SIGNAL` with explicit sample sizes and limitations — never automatic guilt or bans.

---

## 4. Implementation Estimate (Deferred Increment)

- **Backend migration + `demo_uploads` & `demo_jobs` tables + upload validation:** ~0.5 day
- **Background `ProcessPoolExecutor` worker + `awpy` metric extractor (`KAST`, trades, utility, clutches) + SteamID64 matcher:** ~1.5 days
- **UI upload panel inside `FINALIZED` / `RESULT_RECORDED` MatchRoom + job progress polling + tests on real trimmed CS2 demo fixture:** ~1 day
- **Total estimate:** **~3 engineering days** cleanly inside the existing monolith (no Redis/Kafka/microservices needed).
