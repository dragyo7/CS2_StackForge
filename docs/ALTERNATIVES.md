# Alternatives Considered

## Frontend
- **Chosen:** React + TypeScript + Vite.
- Alternative: Next.js. Useful for SEO/server rendering, but not required for an authenticated match-room-first application.
- Alternative: Vue/Svelte. Viable, but team familiarity and ecosystem favour React.

## Backend
- **Chosen:** FastAPI modular monolith.
- Alternative: Node/NestJS. Viable, but Python is convenient for stats and demo parsing.
- Alternative: microservices. Rejected until independently scaling workloads justify them.

## Database
- **Chosen:** PostgreSQL.
- Alternative: MongoDB. Rejected as primary store because player/community/match/generation relationships and integrity constraints are relational.
- JSONB is acceptable for provider-specific raw snapshots, not as a replacement for typed core fields.

## Team optimization
- **Chosen:** Exhaustive evaluation of 126 unique splits for ten players.
- Alternative: genetic algorithm/ML. Rejected for MVP; unnecessary and less explainable.
- Alternative: random split. Rejected because it cannot explain fairness or respect constraints.
- Alternative: greedy draft. Useful as a game mode later, not the default optimizer.

## Skill model
- **Chosen:** Transparent, normalized, confidence-aware multi-source model.
- Alternative: raw weighted sum of Premier ELO + FACEIT ELO + Leetify rating. Rejected because scales are incompatible.
- Alternative: pure K/D. Rejected because it ignores round impact, utility, role and sample size.
- Alternative: ML win prediction immediately. Deferred until sufficient community match outcomes exist.

## Map handling
- **Chosen:** Hidden map-pool robustness adjustment. No map picker or veto.
- Alternative: ask host to select map. Rejected because actual map is random.
- Alternative: ignore map performance. Rejected because map-specific strengths can produce lopsided teams on some random maps.

## Premier data
- **Chosen:** Provider adapter with source-qualified Premier stats; optional future GSI capture.
- Alternative: assume Steam Web API exposes complete Premier rating/history. Rejected; no dependable supported public endpoint verified.
- Alternative: scrape tracker websites. Rejected unless explicitly authorized and terms permit.
- Alternative: manual entry only. Retain as fallback, not primary.

## Trust data
- **Chosen:** Steam official ban API + authorized FACEIT/Leetify data + third-party reputation as optional attributed signal + demo evidence + human review.
- Alternative: one third-party "cheat score" as verdict. Rejected because opaque scores can false-positive.
- Alternative: infer cheating from private profile, low hours or high rank. Rejected.
- Alternative: scrape anti-cheat sites. Rejected unless permitted by their API/terms.

## Hosting
- **Chosen:** Managed PostgreSQL + containerized FastAPI + static frontend hosting initially.
- Alternative: Kubernetes. Rejected for MVP complexity.
- Redis/worker queue added only when async tasks are real requirements.

## Desktop companion
- **Chosen:** Deferred optional local companion using CS2 GSI for opt-in local capture.
- Alternative: require desktop app for all users. Rejected; web-first and cross-device use are core.
