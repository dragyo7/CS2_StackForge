# Feature: CS2 Player Cards & Evidence-Based Humour

**Status:** Implemented (`card_rules_v1` deterministic rules engine)

## Purpose
Give each player a fun, CS2-themed trading card with titles, badges, and banter strictly derived from actual recorded statistics and minimum sample thresholds.

## User Flow
1. View cards on the **Player Cards** tab, **Dashboard** featured card, or inside a player's **Profile**.
2. Adjust controls per player: **Reroll Roast** (cycles deterministic tagline variants from the same verified evidence), **Mild / Spicy / Savage** intensity, **Enable/Disable Humour**, **Hide/Show individual badges**, or **Copy Card** for Discord.

## Data Requirements & Rules (`card_rules_v1`)
- Evaluates `PlayerStatSnapshot` metrics (`sample_size >= 5` for positive/style titles such as *Utility Damage Investor*, *Flashbang Support Dept.*, *The Clutch Department*, *Entry Tax Collector*, *Damage Distributor*, *The One-Tap Philosopher*, *Team's Unpaid Carry*, *The Last Man Standing*; `sample_size >= 8` or `>= 10` for negative roasts such as *The Entry Frag Taxpayer*, *The Save-Round Economist*, *Professional Spectator*).
- **Safety invariant:** Missing statistics or small samples (`< 5` matches) never trigger negative titles; the fallback card is *Uncharted Operative* / *Balanced All-Rounder*.
- **No cheat accusations:** Humour themes stay strictly within in-game CS2 banter (saving, utility, entries, clutches, whiffs).

## API Contracts
- `PATCH /api/players/{id}/card-settings` accepts `humour_enabled`, `humour_intensity`, `hidden_badges`, `regenerate_tagline`.
- Card payload returned on `PlayerOut.card` and `PlayerProfileOut.card`.

## UI Behaviour
- Tactical trading card displaying avatar, role, normalized strength, primary title, roast description, evidence summary, toggleable badges, and stat strip (`ADR`, `K/D`, `HS%`, `Clutch`).
- Community Awards header highlights *Highest ADR*, *Clutch Leader*, *Utility Specialist*, and *Flash Support* only when recorded stats exist.

## Failure Handling & Privacy
- Humour never fabricates numbers or claims unverified match history; disabling humour displays a neutral competitive card.

## Acceptance Criteria
- Titles include exact supporting evidence string.
- Players with missing stats never receive negative titles.
- Hiding badges and regenerating roast taglines persist across reloads.
