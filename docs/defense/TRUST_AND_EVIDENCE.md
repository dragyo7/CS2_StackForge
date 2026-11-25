# Defense: Trust, Cheating Signals and Evidence Policy

## Purpose
Protect private-match communities from known enforcement risks while avoiding false accusations and reputational harm.

## What StackForge can know
- Steam API reports ban fields.
- FACEIT API may report FACEIT player bans.
- Third-party services may publish reputation/conviction signals.
- Demos contain observable game events and player states.
- Community members may submit reports.

## What StackForge cannot know from public data alone
- Whether an account is currently using a cheat in a live match.
- Whether a generic Steam game ban was specifically for CS2 cheating without scope/reason evidence.
- Valve's private Trust Factor.
- Whether an account with no ban record is clean.
- Whether an aim anomaly is cheating rather than skill, sound, callouts, map knowledge or sample noise.
- Whether a player uses DMA/hardware cheats from ordinary public stats.

## Language policy
Use:
- "Steam reports 1 VAC ban; last reported X days ago."
- "Steam reports a game ban; game context unavailable."
- "Third-party source labels this account high risk; see source."
- "Demo signal flagged for human review."
- "No ban record returned by checked source as of timestamp."
Never use:
- "100% cheater" based on a score.
- "Clean" based on no ban.
- "Valve Trust Factor is X."
- "Confirmed CS2 cheater" without explicit, scoped official evidence or documented review standard.

## Demo evidence requirements
Each finding records:
- demo/match ID and provenance;
- round/tick/time;
- player SteamID;
- signal type;
- relevant context (visibility, smoke, sound/teammate info where inferable);
- baseline cohort and sample size;
- confidence and known limitations;
- reviewer decision and rationale.

## Governance
- reports private by default;
- reviewer independence where possible;
- player appeal and correction path;
- audit all status changes;
- do not publish global accusation lists in MVP;
- delete/retain data according to policy and applicable law.
