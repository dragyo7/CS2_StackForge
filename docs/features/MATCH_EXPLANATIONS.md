# Feature: Match Explanations & Trade-Off Analysis

**Status:** Implemented (`backend/app/optimizer/engine.py`, `MatchRoomView.tsx`)

## Deterministic Explanation Structure
- **Overall balance:** Team A/B strengths, gap, balance indicator (`Very Tight`, `Balanced`, `Slight Edge`, `Skewed`), confidence, and data coverage %.
- **Role distribution:** Counts across `AWPer`, `IGL`, `Entry`, `Support`, `Rifler`, `Lurker`.
- **Player contributions:** Top anchor and pairing notes per team.
- **Recent form & map-pool robustness:** Evaluates hidden active map pool (`active_duty_v1`) without selecting or revealing a match map.
- **Trade-offs & alternative comparisons:** Explains what the optimizer prioritized/sacrificed and lists moved players + skill/role deltas for every alternative.
- **Discord share output:** Concise summary included in finalized Discord text while excluding hidden map internals and private trust notes.
