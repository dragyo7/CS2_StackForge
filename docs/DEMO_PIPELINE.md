# StackForge — Asynchronous CS2 `.dem` Replay Pipeline Architecture (Phase 6 Design)

Status: **Designed & Researched (Deferred from immediate runtime; Queue placeholder visible in Ops Health)**.

## 1. Parser Evaluation: `awpy` vs `demoparser2`

| Dimension | `pnxenopoulos/awpy` | `LaihoE/demoparser` (`demoparser2`) |
|---|---|---|
| **Core Engine** | Rust (`pbdems2`) + PyO3 Python outputting Polars DataFrames / Parquet | Native Rust core with Python (`demoparser2`), JS/TS, WASM bindings |
| **License** | MIT License | MIT License |
| **Out-of-the-Box Analytics** | Round reconstruction, kills, damages, flash/smoke states, visibility & nav helpers | Ultra-fast raw tick & game-event extraction (`X,Y,Z`, viewangles, weapon events) |
| **Compute Cost per 5v5 `.dem`** | ~1–4s per full competitive demo (~60–150 MB) in worker thread/process | ~0.3–1.2s for targeted kill/damage/round event sweeps |
| **Recommendation** | **Recommended default parser** for KAST / trade / utility / round analytics | **Optional fast-path extractor** if minimal Python deps or tick-level heatmaps are needed |

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
[Parser (`awpy` / `demoparser2`, pinned parser_version)]
   │
   ├──► [Metric Extractor: KAST, ADR, K/D, Opening Duels, Trade Kills, Traded Deaths, Flash Assists, Clutch 1vX, Util Dmg]
   │
   └──► [Verified SteamID64 Matcher]
            • Match ONLY by SteamID64 extracted from demo player table
            • NEVER auto-merge on ambiguous display nicknames
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

1. **No Live Room Blocking:** Uploading or parsing a demo never blocks `MatchRoom` creation, swaps, or team generation.
2. **File Validation & Size Bounds:** Verify HL2/Source2 `.dem` header bytes + max compressed/uncompressed cap (`250 MB`) + reject path traversal + compute `sha256` before queuing.
3. **Immutable Evidence:** Raw demo bytes remain read-only/immutable per job ID until retention expiry; failure transitions job to `FAILED` with structured error without mutating existing stats.
4. **Canonical Identity Only:** Player rows from `.dem` tick tables carry SteamID64; unknown SteamID64s either prompt host linking (`CANDIDATE` review) or remain unlinked (`UNRESOLVED`), never guessing by nickname.
5. **External Rating Separation:** Metrics extracted from private custom matches are tagged `provider="community_demo"` and feed community analytics independently of Valve Premier, FACEIT, or Leetify public ratings.

---

## 4. Implementation Estimate (Deferred Increment)

- **Backend migration + `demo_uploads` & `demo_jobs` tables + upload validation:** ~0.5 day
- **Background `ProcessPoolExecutor` worker + `awpy` metric extractor (`KAST`, trades, utility, clutches) + SteamID64 matcher:** ~1.5 days
- **UI upload panel inside `FINALIZED` / `RESULT_RECORDED` MatchRoom + job progress polling + tests on real trimmed CS2 demo fixture:** ~1 day
- **Total estimate:** **~3 engineering days** with zero microservices or external broker infrastructure required.
