# Feature: CS2 Tactical Design System

**Status:** Implemented (`frontend/src/styles.css` + modular React views)

## Purpose
Provide a cohesive, dark, high-contrast tactical utility aesthetic inspired by competitive CS2 utilities without copying proprietary Valve artwork or logos.

## Design Tokens & Visual Language
- **Surfaces:** Deep graphite canvas (`#0b0f17`), slate panel (`#111723`), elevated metallic container (`#172030`), crisp `1px` borders (`#243044` / `#32425c`).
- **Accents:** Warm tactical amber (`#e89b2d`), Team A steel-cyan (`#38bdf8`), Team B amber-gold (`#f59e0b`), verified emerald (`#10b981`), danger rose (`#ef4444`).
- **Typography:** `Space Grotesk` headings, `Inter` UI copy, `JetBrains Mono` for `SteamID64`, ratings, strength diffs, and combat metrics.

## Navigation & Layout
- Five primary views in sticky top navigation: **Dashboard**, **Match Room**, **Players**, **Player Stats**, and **Player Cards** (plus read-only **Shared Lineup** view via `?share=<slug>`).
- Responsive grid rules enforce `min-width: 0` and wrapping `<pre>` blocks so both desktop (`1280px+`) and mobile (`390px`) render with zero horizontal overflow.

## Implemented vs Deferred
- **Implemented:** Tactical cards, KPI strips, PlayerAvatar monograms/Steam avatars, side-by-side team panels, responsive mobile layout.
- **Deferred:** Custom user-selectable theme presets and post-match scoreboard timeline charts (pending post-match recording feature).
