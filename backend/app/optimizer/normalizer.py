from __future__ import annotations

from dataclasses import dataclass, field

NORMALIZER_VERSION = "norm_v1"

# Piecewise linear cohort calibration curves -> normalized [0.0, 100.0]
PREMIER_ANCHORS: list[tuple[float, float]] = [
    (1000.0, 12.0),
    (5000.0, 26.0),
    (10000.0, 42.0),
    (15000.0, 58.0),
    (20000.0, 75.0),
    (25000.0, 88.0),
    (30000.0, 96.0),
    (35000.0, 100.0),
]

FACEIT_ANCHORS: list[tuple[float, float]] = [
    (300.0, 12.0),
    (650.0, 24.0),
    (1000.0, 38.0),
    (1350.0, 52.0),
    (1700.0, 66.0),
    (2000.0, 78.0),
    (2400.0, 89.0),
    (2800.0, 96.0),
    (3300.0, 100.0),
]

LEETIFY_ANCHORS: list[tuple[float, float]] = [
    (-0.10, 15.0),
    (-0.04, 35.0),
    (0.00, 50.0),
    (0.04, 66.0),
    (0.08, 82.0),
    (0.12, 94.0),
    (0.16, 100.0),
]

SOURCE_WEIGHTS: dict[str, float] = {
    "premier": 0.35,
    "faceit": 0.35,
    "leetify": 0.30,
    "manual": 0.20,
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


def normalize_manual(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 3)


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


@dataclass(frozen=True)
class PlayerInput:
    community_player_id: str
    display_name: str
    steam_id64: str | None
    identity_status: str
    manual_rating: float
    premier_rating: int | None = None
    premier_source: str | None = None
    premier_season: str | None = None
    faceit_elo: int | None = None
    leetify_rating: float | None = None
    recent_form: float | None = None
    primary_role: str | None = None
    secondary_role: str | None = None
    map_ratings: dict[str, float] = field(default_factory=dict)
    # Available source-qualified combat stats (optional, missing = None)
    adr: float | None = None
    kd_ratio: float | None = None
    kast: float | None = None
    opening_duel_pct: float | None = None
    trade_kills_per_match: float | None = None
    utility_damage_per_round: float | None = None
    flash_assists_per_round: float | None = None
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
    normalized_strength: float
    confidence: float
    strength_band: str
    sources_used: list[str]
    missing_sources: list[str]
    component_scores: dict[str, float]
    recent_form_normalized: float
    has_recent_form: bool
    primary_role: str | None
    secondary_role: str | None
    map_adjustments: dict[str, float]
    adr: float | None = None
    kd_ratio: float | None = None
    kast: float | None = None
    opening_duel_pct: float | None = None
    trade_kills_per_match: float | None = None
    utility_damage_per_round: float | None = None
    flash_assists_per_round: float | None = None
    clutch_win_pct: float | None = None
    consistency_score: float | None = None
    win_rate: float | None = None
    stats_sample_size: int = 0
    stats_stale: bool = False


def _strength_band(score: float) -> str:
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
    Normalizes each available metric independently without adding raw source scales.
    Missing metrics are treated as unknown (omitted and disclosed), never zero.
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

    component_scores["manual"] = normalize_manual(player.manual_rating)

    external_count = sum(1 for s in ("premier", "faceit", "leetify") if s in component_scores)
    if external_count == 0:
        # Only manual baseline is available
        strength = component_scores["manual"]
        sources_used = ["manual"]
        confidence = 0.55
    else:
        weighted_sum = 0.0
        total_weight = 0.0
        sources_used = []
        for src, score in component_scores.items():
            w = SOURCE_WEIGHTS[src]
            weighted_sum += w * score
            total_weight += w
            sources_used.append(src)
        strength = round(weighted_sum / total_weight, 3)
        confidence = {1: 0.72, 2: 0.85, 3: 0.95}.get(external_count, 0.95)

    # Gentle combat performance shrinkage adjustment if sample size >= 5 (never overfits to K/D)
    if player.stats_sample_size >= 5 and player.adr is not None:
        adr_score = _piecewise_linear(player.adr, [(50.0, 28.0), (70.0, 50.0), (85.0, 70.0), (100.0, 88.0), (115.0, 96.0)])
        shrink = min(0.20, 0.08 + (min(player.stats_sample_size, 30) / 30.0) * 0.12)
        if player.stats_stale:
            shrink *= 0.5
        strength = round((1.0 - shrink) * strength + shrink * adr_score, 3)

    if player.stats_stale and confidence > 0.5:
        confidence = round(max(0.45, confidence - 0.12), 2)

    has_form = player.recent_form is not None
    if has_form:
        form_norm = max(-1.0, min(1.0, float(player.recent_form))) * 10.0
    else:
        form_norm = 0.0
        missing_sources.append("recent_form")

    # Apply sample shrinkage (0.65) toward 0.0 for optional per-map deltas
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
        normalized_strength=round(strength, 2),
        confidence=confidence,
        strength_band=_strength_band(strength),
        sources_used=sources_used,
        missing_sources=missing_sources,
        component_scores=component_scores,
        recent_form_normalized=round(form_norm, 3),
        has_recent_form=has_form,
        primary_role=player.primary_role,
        secondary_role=player.secondary_role,
        map_adjustments=map_adj,
        adr=player.adr,
        kd_ratio=player.kd_ratio,
        kast=player.kast,
        opening_duel_pct=player.opening_duel_pct,
        trade_kills_per_match=player.trade_kills_per_match,
        utility_damage_per_round=player.utility_damage_per_round,
        flash_assists_per_round=player.flash_assists_per_round,
        clutch_win_pct=player.clutch_win_pct,
        consistency_score=player.consistency_score,
        win_rate=player.win_rate,
        stats_sample_size=player.stats_sample_size,
        stats_stale=player.stats_stale,
    )
