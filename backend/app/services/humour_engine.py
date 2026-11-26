from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CARD_RULES_VERSION = "card_rules_v1"


@dataclass(frozen=True)
class CardMetricContext:
    display_name: str
    primary_role: str | None
    normalized_strength: float | None
    strength_band: str
    sample_size: int
    provider_label: str | None
    win_rate: float | None = None
    kd_ratio: float | None = None
    adr: float | None = None
    kast: float | None = None
    hs_pct: float | None = None
    opening_duel_pct: float | None = None
    utility_damage_per_round: float | None = None
    flash_assists_per_round: float | None = None
    clutch_win_pct: float | None = None
    trade_kills_per_match: float | None = None
    multi_kill_rate: float | None = None


@dataclass(frozen=True)
class TitleRule:
    key: str
    title: str
    badge_label: str
    min_samples: int
    is_negative: bool
    priority: int
    taglines: dict[str, tuple[str, ...]]  # intensity -> variants


RULES: tuple[TitleRule, ...] = (
    TitleRule(
        key="utility_investor",
        title="Utility Damage Investor",
        badge_label="HE & Molly Baron",
        min_samples=5,
        is_negative=False,
        priority=90,
        taglines={
            "MILD": (
                "Consistently chips opponents down with grenades before the duel even starts.",
                "Brings reliable grenade value every single buy round.",
            ),
            "SPICY": (
                "Financing the enemy team's medical expenses one grenade at a time.",
                "Does half a rifle's work from behind a smoke without peeking.",
            ),
            "SAVAGE": (
                "Treaty-violating HE spammer who deals more damage from spawn than most rifles do on site.",
                "Enemy ankles have filed a formal complaint with Valve over these Molotovs.",
            ),
        },
    ),
    TitleRule(
        key="flashbang_dept",
        title="Flashbang Support Dept.",
        badge_label="Optics Specialist",
        min_samples=5,
        is_negative=False,
        priority=88,
        taglines={
            "MILD": (
                "Sets up teammates with well-timed flashes on site executes.",
                "Quietly generates free kills with crisp pop-flashes.",
            ),
            "SPICY": (
                "Enemy screens stay white longer than a winter morning on Office.",
                "Runs an unofficial ophthalmology clinic for opposing site anchors.",
            ),
            "SAVAGE": (
                "Your enemies are blind, your teammates are squinting, and the scoreboard calls it teamwork.",
                "Throws pop-flashes so bright even the observer needs sunglasses.",
            ),
        },
    ),
    TitleRule(
        key="clutch_dept",
        title="The Clutch Department",
        badge_label="1vX Closer",
        min_samples=5,
        is_negative=False,
        priority=95,
        taglines={
            "MILD": (
                "Keeps composure in late-round situations and converts tight clutches.",
                "Calm under pressure when the round comes down to the final seconds.",
            ),
            "SPICY": (
                "Delivers under pressure. Occasionally after three business days.",
                "Somehow plays twice as sharp the moment four teammates start backseat-coaching.",
            ),
            "SAVAGE": (
                "Needs all four teammates dead just to wake up and start hitting shots.",
                "Turns 1v3 disasters into highlight reels purely out of spite.",
            ),
        },
    ),
    TitleRule(
        key="entry_collector",
        title="Entry Tax Collector",
        badge_label="First Contact",
        min_samples=5,
        is_negative=False,
        priority=87,
        taglines={
            "MILD": (
                "Takes opening space fearlessly and wins the first duel for the team.",
                "Reliable opener who turns dry executes into 5v4 advantages.",
            ),
            "SPICY": (
                "Walks through the smoke first and hands the enemy team an immediate respawn timer.",
                "Collects the first kill before the IGL even finishes calling the strat.",
            ),
            "SAVAGE": (
                "Kicks the bombsite door off its hinges while everyone else is still checking corners in spawn.",
                "Doesn't ask for a flash — simply deletes the anchor and asks why the bomb is slow.",
            ),
        },
    ),
    TitleRule(
        key="entry_taxpayer",
        title="The Entry Frag Taxpayer",
        badge_label="Human UAV",
        min_samples=8,
        is_negative=True,
        priority=82,
        taglines={
            "MILD": (
                "Takes tough opening duels to gather info and make space for trades.",
                "Always first through the choke point so teammates can trade.",
            ),
            "SPICY": (
                "Pays the entry fee every round. Usually with their own life.",
                "Provides invaluable enemy-position intel via the killfeed.",
            ),
            "SAVAGE": (
                "A generous philanthropist donating first bloods to the opposing economy since round 1.",
                "Runs onto site at Mach 2 to verify where all five CTs are aiming.",
            ),
        },
    ),
    TitleRule(
        key="one_tap_philosopher",
        title="The One-Tap Philosopher",
        badge_label="Headshot Purist",
        min_samples=5,
        is_negative=False,
        priority=84,
        taglines={
            "MILD": (
                "High headshot discipline with clean crosshair placement.",
                "Prioritizes crisp headshots over wild spray transfers.",
            ),
            "SPICY": (
                "Believes every tactical problem can be solved with one bullet to the helmet.",
                "Body shots are considered an admission of defeat.",
            ),
            "SAVAGE": (
                "Would rather die aiming for the eyebrow than spray someone in the chest.",
                "Spends 90% of warmup on aim_botz and it shows in the killfeed.",
            ),
        },
    ),
    TitleRule(
        key="save_economist",
        title="The Save-Round Economist",
        badge_label="Exit Frag Broker",
        min_samples=8,
        is_negative=True,
        priority=83,
        taglines={
            "MILD": (
                "Preserves rifles wisely in lost rounds to protect team economy.",
                "Strong individual duel stats paired with cautious late-round positioning.",
            ),
            "SPICY": (
                "Knows exactly when to save. Unfortunately, also knows when everyone else needed help.",
                "Protects that AK-47 like a family heirloom while the bomb ticks down.",
            ),
            "SAVAGE": (
                "Has a 1.3+ K/D and hasn't stepped onto a retake site since CS:GO.",
                "Already hiding in T-spawn before the entry fragger finishes hitting the floor.",
            ),
        },
    ),
    TitleRule(
        key="unpaid_carry",
        title="Team's Unpaid Carry",
        badge_label="Back-Pain Hazard",
        min_samples=5,
        is_negative=False,
        priority=93,
        taglines={
            "MILD": (
                "High-impact anchor putting up strong numbers and consistent wins.",
                "Heavy lifting across both ADR and win-rate metrics.",
            ),
            "SPICY": (
                "Someone schedule a chiropractor — this server bill is getting heavy.",
                "Quietly doing two players' jobs for the exact same zero dollars.",
            ),
            "SAVAGE": (
                "If this player leaves the lobby, the team loses 300 ELO and three rounds of brainpower.",
                "Carrying four teammates like luggage through airport security.",
            ),
        },
    ),
    TitleRule(
        key="damage_distributor",
        title="Damage Distributor",
        badge_label="Heavy Firepower",
        min_samples=5,
        is_negative=False,
        priority=85,
        taglines={
            "MILD": (
                "Consistently outputs high ADR across recent matches.",
                "Reliable multi-frag pressure every half.",
            ),
            "SPICY": (
                "Turns every eco and buy round into an unexpected boss fight.",
                "Leaves opponents permanently tagged under 20 HP.",
            ),
            "SAVAGE": (
                "Deals so much ADR that enemy armor doesn't even get a chance to break.",
                "Shoots first, asks questions never, tops the damage chart anyway.",
            ),
        },
    ),
    TitleRule(
        key="last_man_standing",
        title="The Last Man Standing",
        badge_label="Late-Round Lurker",
        min_samples=5,
        is_negative=False,
        priority=80,
        taglines={
            "MILD": (
                "Patient lurker who finds late-round timing and clutches.",
                "Punishes over-rotations when rounds stretch thin.",
            ),
            "SPICY": (
                "Has perfected the art of being alive after everyone else is gone.",
                "Appears behind the enemy team right when they forgot there was a fifth player.",
            ),
            "SAVAGE": (
                "Walks across the map at 10 units/sec until four teammates have finished spectating.",
                "Shoots people in the back with the patience of a tax auditor.",
            ),
        },
    ),
    TitleRule(
        key="prof_spectator",
        title="Professional Spectator",
        badge_label="Moral Support",
        min_samples=10,
        is_negative=True,
        priority=70,
        taglines={
            "MILD": (
                "Tough recent statistical stretch — prime candidate for a bounce-back match.",
                "Numbers have been cold across the last 10+ games; due for a heater.",
            ),
            "SPICY": (
                "Provides elite voice-chat callouts from the comfort of the death camera.",
                "Paying full price for Kevlar just to watch teammates play.",
            ),
            "SAVAGE": (
                "Has memorized every teammate's crosshair placement from spectating so much.",
                "Bringing vibes, callouts, and an inspiring refusal to let stats dictate confidence.",
            ),
        },
    ),
)

RULE_MAP = {r.key: r for r in RULES}


def _evaluate_matches(ctx: CardMetricContext) -> list[tuple[TitleRule, str]]:
    matches: list[tuple[TitleRule, str]] = []
    n = ctx.sample_size

    if ctx.clutch_win_pct is not None and ctx.clutch_win_pct >= 28.0 and n >= 5:
        matches.append((
            RULE_MAP["clutch_dept"],
            f"Clutch win rate {ctx.clutch_win_pct:.1f}% across {n} matches ({ctx.provider_label})",
        ))

    if ctx.normalized_strength is not None and ctx.normalized_strength >= 76.0 and ctx.win_rate is not None and ctx.win_rate >= 54.0 and n >= 5:
        matches.append((
            RULE_MAP["unpaid_carry"],
            f"Normalized strength {ctx.normalized_strength:.1f} & {ctx.win_rate:.1f}% win rate ({n} matches)",
        ))

    if ctx.utility_damage_per_round is not None and ctx.utility_damage_per_round >= 17.5 and n >= 5:
        matches.append((
            RULE_MAP["utility_investor"],
            f"{ctx.utility_damage_per_round:.1f} utility dmg/round across {n} matches ({ctx.provider_label})",
        ))

    if ctx.flash_assists_per_round is not None and ctx.flash_assists_per_round >= 0.22 and n >= 5:
        matches.append((
            RULE_MAP["flashbang_dept"],
            f"{ctx.flash_assists_per_round:.2f} flash assists/round across {n} matches ({ctx.provider_label})",
        ))

    if ctx.opening_duel_pct is not None and ctx.opening_duel_pct >= 54.0 and n >= 5:
        matches.append((
            RULE_MAP["entry_collector"],
            f"{ctx.opening_duel_pct:.1f}% opening duel success ({n} matches, {ctx.provider_label})",
        ))
    elif ctx.primary_role == "Entry" and ctx.opening_duel_pct is not None and ctx.opening_duel_pct < 45.0 and n >= 8:
        matches.append((
            RULE_MAP["entry_taxpayer"],
            f"Entry role with {ctx.opening_duel_pct:.1f}% opening duel success across {n} matches",
        ))

    if ctx.adr is not None and ctx.adr >= 84.0 and n >= 5:
        matches.append((
            RULE_MAP["damage_distributor"],
            f"{ctx.adr:.1f} ADR across {n} matches ({ctx.provider_label})",
        ))

    if ctx.hs_pct is not None and ctx.hs_pct >= 55.0 and n >= 5:
        matches.append((
            RULE_MAP["one_tap_philosopher"],
            f"{ctx.hs_pct:.1f}% headshot rate across {n} matches ({ctx.provider_label})",
        ))

    if (
        ctx.kd_ratio is not None
        and ctx.kast is not None
        and ctx.kd_ratio >= 1.22
        and ctx.kast < 67.0
        and n >= 8
    ):
        matches.append((
            RULE_MAP["save_economist"],
            f"{ctx.kd_ratio:.2f} K/D with {ctx.kast:.1f}% KAST across {n} matches",
        ))

    if ctx.primary_role == "Lurker" and ctx.clutch_win_pct is not None and ctx.clutch_win_pct >= 20.0 and n >= 5:
        matches.append((
            RULE_MAP["last_man_standing"],
            f"Lurker role with {ctx.clutch_win_pct:.1f}% clutch win rate ({n} matches)",
        ))

    # Strict threshold so missing data or 1 bad match NEVER triggers a negative roast
    if (
        ctx.adr is not None
        and ctx.kd_ratio is not None
        and ctx.adr < 58.0
        and ctx.kd_ratio < 0.78
        and n >= 10
    ):
        matches.append((
            RULE_MAP["prof_spectator"],
            f"{ctx.adr:.1f} ADR and {ctx.kd_ratio:.2f} K/D across {n} matches",
        ))

    matches.sort(key=lambda item: item[0].priority, reverse=True)
    return matches


def generate_player_card(
    ctx: CardMetricContext,
    humour_enabled: bool = True,
    humour_intensity: str = "SPICY",
    hidden_badges: list[str] | None = None,
    variant: int = 0,
) -> dict[str, Any]:
    """
    Deterministic evidence-based player card generator.
    Missing stats are unknown (never zero) and never yield negative titles.
    """
    hidden_set = set(hidden_badges or [])
    intensity = humour_intensity if humour_intensity in ("MILD", "SPICY", "SAVAGE") else "SPICY"

    if not humour_enabled:
        return {
            "rules_version": CARD_RULES_VERSION,
            "humour_enabled": False,
            "humour_intensity": intensity,
            "primary_title": f"{ctx.primary_role or 'CS2'} Competitor",
            "tagline": "Humour mode is disabled for this profile. Competitive stats remain visible.",
            "evidence_summary": (
                f"{ctx.sample_size} match(es) recorded ({ctx.provider_label})."
                if ctx.sample_size > 0
                else "No external or community combat sample recorded yet."
            ),
            "badges": [],
            "eligible_count": 0,
            "discord_card_text": (
                f"**{ctx.display_name}** [{ctx.primary_role or 'Flex'}] • Strength "
                + (f"{ctx.normalized_strength:.1f}" if ctx.normalized_strength is not None else "Insufficient Data")
                + f" ({ctx.strength_band})"
            ),
        }

    matched = _evaluate_matches(ctx)

    if not matched:
        fallback_title = "Uncharted Operative" if ctx.sample_size == 0 else "Balanced All-Rounder"
        fallback_tagline = (
            "Insufficient verified combat samples for an evidence-based title — missing stats are unknown, not a slump."
            if ctx.sample_size < 5
            else f"Steady numbers across {ctx.sample_size} matches without extreme statistical quirks."
        )
        role_badge = (
            {
                "key": "role_badge",
                "label": f"{ctx.primary_role} Main",
                "evidence": f"Community role: {ctx.primary_role}",
                "hidden": "role_badge" in hidden_set,
            }
            if ctx.primary_role
            else None
        )
        badges = [role_badge] if role_badge else []
        return {
            "rules_version": CARD_RULES_VERSION,
            "humour_enabled": True,
            "humour_intensity": intensity,
            "primary_title": fallback_title,
            "tagline": fallback_tagline,
            "evidence_summary": (
                "No combat match sample available yet (minimum 5 matches required for statistical titles)."
                if ctx.sample_size < 5
                else f"Evaluated {ctx.sample_size} matches from {ctx.provider_label}."
            ),
            "badges": badges,
            "eligible_count": 0,
            "discord_card_text": (
                f"**{ctx.display_name}** — *{fallback_title}*\n"
                f"> {fallback_tagline}\n"
                f"Strength: {f'{ctx.normalized_strength:.1f}' if ctx.normalized_strength is not None else 'Insufficient Data'} ({ctx.strength_band}) | Role: {ctx.primary_role or 'Unassigned'}"
            ),
        }

    primary_rule, primary_evidence = matched[0]
    options = primary_rule.taglines[intensity]
    chosen_tagline = options[variant % len(options)]

    badges = []
    for rule, ev in matched[:4]:
        badges.append(
            {
                "key": rule.key,
                "label": rule.badge_label,
                "evidence": ev,
                "hidden": rule.key in hidden_set,
            }
        )

    visible_badges = [b["label"] for b in badges if not b["hidden"]]
    badge_line = f" | Badges: {', '.join(visible_badges)}" if visible_badges else ""
    discord_text = (
        f"**{ctx.display_name}** — *{primary_rule.title}*\n"
        f"> {chosen_tagline}\n"
        f"Evidence: {primary_evidence}{badge_line}"
    )

    return {
        "rules_version": CARD_RULES_VERSION,
        "humour_enabled": True,
        "humour_intensity": intensity,
        "primary_title": primary_rule.title,
        "tagline": chosen_tagline,
        "evidence_summary": primary_evidence,
        "badges": badges,
        "eligible_count": len(matched),
        "discord_card_text": discord_text,
    }
