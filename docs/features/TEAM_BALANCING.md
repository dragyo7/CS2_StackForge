# Feature: Explainable Team Balancing

## Goal
Create two fair 5-player teams from ten selected players and explain the result.

## Inputs
- normalized Premier performance;
- FACEIT ELO/level and match stats;
- Leetify overall/component metrics;
- recent form;
- community Elo and verified private-match outcomes;
- roles/preferences;
- map-specific performance across active map pool (hidden);
- hard locks, together pairs and opponent pairs.

## Normalization
Each source dimension uses its own cohort and normalizer version. Never add raw source scales. Apply sample-size shrinkage, freshness decay and confidence. Missing values are unknown and lower confidence.

## Objective
Minimize overall team strength difference, role imbalance, recent-form imbalance, player-pair chemistry imbalance and map-pool expected/worst-case imbalance. Weights are versioned and configurable. Validate with historical outcomes.

## Search
For ten players enumerate 126 unique partitions. Remove mirrored duplicates. Apply hard constraints first. Rank remaining partitions. Select one recommended split and up to N materially distinct alternatives.

## Explanation
Return objective components, normalized strengths, role coverage, confidence, source coverage, constraints and map-pool robustness. No uncalibrated win percentage.

## Remake
Every regeneration creates a new immutable proposal. Use seed and history to avoid repeats. Preserve locks. Support swap preview with before/after objective delta.

## Acceptance
- deterministic for same input/seed/version;
- no player duplicated or omitted;
- five players per team;
- hard constraints always satisfied;
- unsatisfiable constraints explain why;
- prior generations remain restorable.
