from __future__ import annotations

from dataclasses import dataclass, field

NORMALIZER_VERSION = "norm_v2"

# Provider-specific calibration anchors -> comparable internal [0.0, 100.0] scale.
# Premier CSR, FACEIT ELO, and Leetify Rating are never summed raw.
PREMIER_ANCHORS: list[tuple[float, float]] = [
    (1000.0, 14.0),
    (5000.0, 28.0),
    (10000.0, 44.0),
    (15000.0, 58.0),
    (20000.0, 74.0),
    (25000.0, 88.0),
    (30000.0, 96.0),
    (35000.0, 100.0),
]

FACEIT_ANCHORS: list[tuple[float, float]] = [
    (300.0, 14.0),
    (650.0, 26.0),
    (1000.0, 40.0),
    (1350.0, 54.0),
    (1700.0, 68.0),
    (2000.0, 79.0),
    (2400.0, 89.0),
    (2800.0, 96.0),
    (3300.0, 100.0),
]

LEETIFY_ANCHORS: list[tuple[float, float]] = [
    (-0.10, 16.0),
    (-0.04, 36.0),
    (0.00, 50.0),
    (0.04, 66.0),
    (0.08, 82.0),
    (0.12, 94.0),
    (0.16, 100.0),
]

AIM_RATING_ANCHORS: list[tuple[float, float]] = [
    (25.0, 26.0),
    (45.0, 44.0),
    (60.0, 58.0),
    (75.0, 74.0),
    (88.0, 88.0),
    (98.0, 97.0),
]

UTILITY_RATING_ANCHORS: list[tuple[float, float]] = [
    (20.0, 26.0),
    (40.0, 44.0),
    (55.0, 58.0),
    (70.0, 74.0),
    (85.0, 88.0),
    (96.0, 96.0),
]

RATING_SOURCE_WEIGHTS: dict[str, float] = {
    "premier": 0.36,
    "faceit": 0.36,
    "leetify": 0.32,
}


def _piecewise_linear(value: float, anchors: list[tuple[float, float]]) -> float:
    if value <= anchors[0][0]:
        return anchors[0][1]
    if value >= anchors[-1][0]:
        return anchors[-1][1]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if x0 <= value <= x1:
            t = (value - x0) / (x1 - x0)
            return round(y0 + t * (y1 - y0), 3)
    return anchors[-1][1]


def _inverse_linear(value: float, anchors_desc: list[tuple[float, float]]) -> float:
    """Lower input is better (e.g. pre-aim degrees or reaction time ms)."""
    if value >= anchors_desc[0][0]:
        return anchors_desc[0][1]
    if value <= anchors_desc[-1][0]:
        return anchors_desc[-1][1]
    for (x0, y0), (x1, y1) in zip(anchors_desc, anchors_desc[1:]):
        if x1 <= value <= x0:
            t = (x0 - value) / (x0 - x1)
            return round(y0 + t * (y1 - y0), 3)
    return anchors_desc[-1][1]


def normalize_premier(rating: int | float) -> float:
    return _piecewise_linear(float(rating), PREMIER_ANCHORS)


def normalize_faceit(elo: int | float) -> float:
    return _piecewise_linear(float(elo), FACEIT_ANCHORS)


def normalize_leetify(rating: float) -> float:
    val = float(rating)
    # Leetify v3 ranks.leetify uses percentage points (e.g. +2.84) while match ratings use decimal (+0.0284)
    if abs(val) > 0.5:
        val = val / 100.0
    return _piecewise_linear(val, LEETIFY_ANCHORS)


def _weighted_blend(pairs: list[tuple[float | None, float]]) -> float | None:
    valid = [(v, w) for v, w in pairs if v is not None and w > 0.0]
    if not valid:
        return None
    w_sum = sum(w for _, w in valid)
    return round(sum(v * w for v, w in valid) / w_sum, 2)


@dataclass(frozen=True)
class PlayerInput:
    community_player_id: str
    display_name: str
    steam_id64: str | None
    identity_status: str
    # Legacy field kept only for backwards schema/test call compatibility; NEVER used in matchmaking.
    manual_rating: float | None = None
    premier_rating: int | None = None
    premier_source: str | None = None
    premier_season: str | None = None
    faceit_elo: int | None = None
    faceit_level: int | None = None
    leetify_rating: float | None = None
    aim_rating: float | None = None
    utility_rating: float | None = None
    positioning_rating: float | None = None
    recent_form: float | None = None
    primary_role: str | None = None
    secondary_role: str | None = None
    map_ratings: dict[str, float] = field(default_factory=dict)
    # Source-qualified combat & mechanical stats (optional, missing = None)
    adr: float | None = None
    kd_ratio: float | None = None
    kast: float | None = None
    hs_pct: float | None = None
    preaim: float | None = None
    reaction_time_ms: float | None = None
    spotted_accuracy: float | None = None
    spray_accuracy: float | None = None
    opening_duel_pct: float | None = None
    trade_kills_per_match: float | None = None
    traded_deaths_pct: float | None = None
    utility_damage_per_round: float | None = None
    flash_assists_per_round: float | None = None
    enemies_flashed_per_round: float | None = None
    clutch_win_pct: float | None = None
    consistency_score: float | None = None
    win_rate: float | None = None
    stats_sample_size: int = 0
    stats_stale: bool = False


@dataclass(frozen=True)
class NormalizedPlayer:
    community_player_id: str
    display_name: str
    steam_id64: str | None
    identity_status: str
    # None when external statistics are insufficient; never fabricated from manual_rating
    normalized_strength: float | None
    confidence: float
    strength_band: str
    data_status: str  # OK | LOW_CONFIDENCE | INSUFFICIENT_DATA
    sources_used: list[str]
    missing_sources: list[str]
    component_scores: dict[str, float]
    recent_form_normalized: float
    has_recent_form: bool
    primary_role: str | None
    secondary_role: str | None
    map_adjustments: dict[str, float]
    # Sub-dimension scores (0..100 when genuinely sampled, else None)
    aim_score: float | None = None
    utility_score: float | None = None
    positioning_score: float | None = None
    damage_score: float | None = None
    survival_score: float | None = None
    entry_score: float | None = None
    trade_score: float | None = None
    clutch_score: float | None = None
    # Raw verified metrics retained for CS2-native explanations & display
    aim_rating: float | None = None
    utility_rating: float | None = None
    positioning_rating: float | None = None
    preaim: float | None = None
    reaction_time_ms: float | None = None
    spotted_accuracy: float | None = None
    spray_accuracy: float | None = None
    hs_pct: float | None = None
    adr: float | None = None
    kd_ratio: float | None = None
    kast: float | None = None
    opening_duel_pct: float | None = None
    trade_kills_per_match: float | None = None
    traded_deaths_pct: float | None = None
    utility_damage_per_round: float | None = None
    flash_assists_per_round: float | None = None
    enemies_flashed_per_round: float | None = None
    clutch_win_pct: float | None = None
    consistency_score: float | None = None
    win_rate: float | None = None
    stats_sample_size: int = 0
    stats_stale: bool = False


def _strength_band(score: float | None, data_status: str) -> str:
    if score is None or data_status == "INSUFFICIENT_DATA":
        return "Insufficient Data"
    if score >= 82.0:
        return "Elite"
    if score >= 68.0:
        return "High"
    if score >= 52.0:
        return "Solid"
    if score >= 36.0:
        return "Mid"
    return "Developing"


def normalize_player(player: PlayerInput) -> NormalizedPlayer:
    """
    Multi-dimensional CS2 normalization using verified provider ratings & stats ONLY.
    - Never reads or falls back to `manual_rating`.
    - Missing metrics remain None (unknown), never zero.
    - Returns normalized_strength = None and data_status = 'INSUFFICIENT_DATA'
      when a player lacks sufficient external ratings/statistics.
    """
    component_scores: dict[str, float] = {}
    missing_sources: list[str] = []

    if player.premier_rating is not None:
        component_scores["premier"] = normalize_premier(player.premier_rating)
    else:
        missing_sources.append("premier")

    if player.faceit_elo is not None:
        component_scores["faceit"] = normalize_faceit(player.faceit_elo)
    else:
        missing_sources.append("faceit")

    if player.leetify_rating is not None:
        component_scores["leetify"] = normalize_leetify(player.leetify_rating)
    else:
        missing_sources.append("leetify")

    # Dimension sub-scores (each normalized on CS2 reference scales; None when unavailable)
    aim_rating_norm = _piecewise_linear(player.aim_rating, AIM_RATING_ANCHORS) if player.aim_rating is not None else None
    preaim_norm = _inverse_linear(player.preaim, [(18.0, 26.0), (13.0, 46.0), (9.5, 66.0), (7.0, 82.0), (4.5, 95.0)]) if player.preaim is not None else None
    rt_norm = _inverse_linear(player.reaction_time_ms, [(800.0, 28.0), (660.0, 48.0), (570.0, 66.0), (490.0, 82.0), (410.0, 94.0)]) if player.reaction_time_ms is not None else None
    spot_norm = _piecewise_linear(player.spotted_accuracy, [(20.0, 28.0), (30.0, 46.0), (38.0, 62.0), (46.0, 78.0), (56.0, 92.0)]) if player.spotted_accuracy is not None else None
    spray_norm = _piecewise_linear(player.spray_accuracy, [(20.0, 30.0), (32.0, 48.0), (42.0, 66.0), (52.0, 84.0), (62.0, 94.0)]) if player.spray_accuracy is not None else None
    # Headshot % carries strictly minor weight so high HS% is never treated as complete aim skill
    hs_norm = _piecewise_linear(player.hs_pct, [(20.0, 32.0), (38.0, 48.0), (50.0, 62.0), (62.0, 78.0), (75.0, 90.0)]) if player.hs_pct is not None else None
    aim_score = _weighted_blend([
        (aim_rating_norm, 0.50),
        (preaim_norm, 0.18),
        (rt_norm, 0.14),
        (spot_norm, 0.08),
        (spray_norm, 0.05),
        (hs_norm, 0.05),
    ])

    util_rating_norm = _piecewise_linear(player.utility_rating, UTILITY_RATING_ANCHORS) if player.utility_rating is not None else None
    # Utility damage alone is capped conservatively; flash efficiency calibrated to per-round rates
    util_dmg_norm = _piecewise_linear(player.utility_damage_per_round, [(4.0, 30.0), (11.0, 48.0), (18.0, 66.0), (26.0, 84.0), (36.0, 94.0)]) if player.utility_damage_per_round is not None else None
    flash_ast_norm = _piecewise_linear(player.flash_assists_per_round, [(0.002, 32.0), (0.010, 50.0), (0.025, 68.0), (0.045, 84.0), (0.080, 95.0)]) if player.flash_assists_per_round is not None else None
    flashed_norm = _piecewise_linear(player.enemies_flashed_per_round, [(0.15, 34.0), (0.35, 50.0), (0.55, 68.0), (0.80, 86.0)]) if player.enemies_flashed_per_round is not None else None
    utility_score = _weighted_blend([
        (util_rating_norm, 0.56),
        (util_dmg_norm, 0.18),
        (flash_ast_norm, 0.14),
        (flashed_norm, 0.12),
    ])

    pos_rating_norm = _piecewise_linear(player.positioning_rating, [(25.0, 26.0), (42.0, 44.0), (55.0, 58.0), (68.0, 74.0), (80.0, 88.0), (92.0, 96.0)]) if player.positioning_rating is not None else None
    traded_death_norm = _piecewise_linear(player.traded_deaths_pct, [(25.0, 32.0), (42.0, 50.0), (55.0, 66.0), (68.0, 82.0), (80.0, 92.0)]) if player.traded_deaths_pct is not None else None
    positioning_score = _weighted_blend([
        (pos_rating_norm, 0.72),
        (traded_death_norm, 0.28),
    ])

    adr_norm = _piecewise_linear(player.adr, [(50.0, 28.0), (70.0, 50.0), (85.0, 70.0), (100.0, 88.0), (115.0, 96.0)]) if player.adr is not None else None
    cons_norm = _piecewise_linear(player.consistency_score, [(52.0, 34.0), (66.0, 50.0), (78.0, 68.0), (88.0, 86.0), (95.0, 95.0)]) if player.consistency_score is not None else None
    damage_score = _weighted_blend([(adr_norm, 0.72), (cons_norm, 0.28)])

    kd_norm = _piecewise_linear(player.kd_ratio, [(0.65, 26.0), (0.90, 44.0), (1.05, 55.0), (1.25, 72.0), (1.50, 88.0), (1.80, 96.0)]) if player.kd_ratio is not None else None
    kast_norm = _piecewise_linear(player.kast, [(55.0, 30.0), (68.0, 50.0), (76.0, 68.0), (84.0, 86.0)]) if player.kast is not None else None
    survival_score = _weighted_blend([(kd_norm, 0.55), (kast_norm, 0.45)])

    entry_score = _piecewise_linear(player.opening_duel_pct, [(32.0, 32.0), (42.0, 46.0), (50.0, 56.0), (58.0, 72.0), (68.0, 88.0)]) if player.opening_duel_pct is not None else None
    trade_score = _piecewise_linear(player.trade_kills_per_match, [(22.0, 34.0), (38.0, 50.0), (50.0, 66.0), (62.0, 82.0), (75.0, 92.0)]) if player.trade_kills_per_match is not None else None
    clutch_score = _piecewise_linear(player.clutch_win_pct, [(8.0, 32.0), (16.0, 48.0), (24.0, 64.0), (34.0, 82.0), (45.0, 92.0)]) if player.clutch_win_pct is not None else None

    if aim_rating_norm is not None:
        component_scores["aim"] = aim_score  # type: ignore[assignment]
    if util_rating_norm is not None:
        component_scores["utility"] = utility_score  # type: ignore[assignment]
    if pos_rating_norm is not None and positioning_score is not None:
        component_scores["positioning"] = positioning_score

    sources_used = [s for s in ("premier", "faceit", "leetify") if s in component_scores]
    external_rating_count = len(sources_used)

    has_form = player.recent_form is not None
    sample_factor = min(1.0, max(0.0, player.stats_sample_size / 20.0)) if player.stats_sample_size > 0 else 0.0
    if has_form:
        # Dampen small samples so 1-2 matches never swing form wildly
        damping = max(0.25, sample_factor)
        form_norm = max(-1.0, min(1.0, float(player.recent_form))) * 10.0 * damping
    else:
        form_norm = 0.0
        missing_sources.append("recent_form")

    combat_composite = _weighted_blend([
        (damage_score, 0.28),
        (survival_score, 0.20),
        (aim_score, 0.21),
        (utility_score, 0.13),
        (positioning_score, 0.08),
        (entry_score, 0.05),
        (clutch_score, 0.05),
    ])

    normalized_strength: float | None = None
    data_status = "INSUFFICIENT_DATA"
    confidence = 0.0

    if external_rating_count > 0:
        weighted_sum = sum(RATING_SOURCE_WEIGHTS[s] * component_scores[s] for s in sources_used)
        total_w = sum(RATING_SOURCE_WEIGHTS[s] for s in sources_used)
        base_strength = weighted_sum / total_w

        # Avoid double-counting Leetify rating with its own sub-metrics: apply smaller combat shrinkage
        # when Leetify is already in base_strength, slightly higher when only Premier/FACEIT is present.
        if combat_composite is not None and player.stats_sample_size >= 5:
            max_shrink = 0.14 if "leetify" in component_scores else 0.24
            shrink = min(max_shrink, 0.06 + (min(player.stats_sample_size, 30) / 30.0) * (max_shrink - 0.06))
            if player.stats_stale:
                shrink *= 0.5
            base_strength = (1.0 - shrink) * base_strength + shrink * combat_composite

        if has_form and player.stats_sample_size >= 5:
            base_strength += (form_norm / 10.0) * 1.4

        normalized_strength = round(max(0.0, min(100.0, base_strength)), 2)

        conf = {1: 0.68, 2: 0.84, 3: 0.94}.get(external_rating_count, 0.94)
        if player.stats_sample_size >= 15:
            conf = min(0.98, conf + 0.04)
        elif player.stats_sample_size < 5:
            conf = round(max(0.45, conf - 0.12), 2)
        if player.stats_stale:
            conf = round(max(0.40, conf - 0.15), 2)

        confidence = round(conf, 2)
        data_status = "LOW_CONFIDENCE" if confidence < 0.62 else "OK"

    elif combat_composite is not None and player.stats_sample_size >= 5:
        # Combat stats exist without ladder rating (still mark low confidence, never pretend high certainty)
        normalized_strength = round(max(0.0, min(100.0, combat_composite)), 2)
        sources_used.append("combat_stats")
        confidence = round(min(0.54, 0.32 + sample_factor * 0.20) * (0.8 if player.stats_stale else 1.0), 2)
        data_status = "LOW_CONFIDENCE"
    else:
        normalized_strength = None
        confidence = 0.0
        data_status = "INSUFFICIENT_DATA"

    # Optional per-map adjustments (strictly private active-duty map pool robustness)
    map_adj = {
        m: round(max(-15.0, min(15.0, float(v))) * 0.65, 3)
        for m, v in (player.map_ratings or {}).items()
        if isinstance(v, (int, float))
    }

    return NormalizedPlayer(
        community_player_id=player.community_player_id,
        display_name=player.display_name,
        steam_id64=player.steam_id64,
        identity_status=player.identity_status,
        normalized_strength=normalized_strength,
        confidence=confidence,
        strength_band=_strength_band(normalized_strength, data_status),
        data_status=data_status,
        sources_used=sources_used,
        missing_sources=missing_sources,
        component_scores=component_scores,
        recent_form_normalized=round(form_norm, 3),
        has_recent_form=has_form,
        primary_role=player.primary_role,
        secondary_role=player.secondary_role,
        map_adjustments=map_adj,
        aim_score=aim_score,
        utility_score=utility_score,
        positioning_score=positioning_score,
        damage_score=damage_score,
        survival_score=survival_score,
        entry_score=entry_score,
        trade_score=trade_score,
        clutch_score=clutch_score,
        aim_rating=player.aim_rating,
        utility_rating=player.utility_rating,
        positioning_rating=player.positioning_rating,
        preaim=player.preaim,
        reaction_time_ms=player.reaction_time_ms,
        spotted_accuracy=player.spotted_accuracy,
        spray_accuracy=player.spray_accuracy,
        hs_pct=player.hs_pct,
        adr=player.adr,
        kd_ratio=player.kd_ratio,
        kast=player.kast,
        opening_duel_pct=player.opening_duel_pct,
        trade_kills_per_match=player.trade_kills_per_match,
        traded_deaths_pct=player.traded_deaths_pct,
        utility_damage_per_round=player.utility_damage_per_round,
        flash_assists_per_round=player.flash_assists_per_round,
        enemies_flashed_per_round=player.enemies_flashed_per_round,
        clutch_win_pct=player.clutch_win_pct,
        consistency_score=player.consistency_score,
        win_rate=player.win_rate,
        stats_sample_size=player.stats_sample_size,
        stats_stale=player.stats_stale,
    )
