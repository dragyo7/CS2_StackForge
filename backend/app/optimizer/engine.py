from __future__ import annotations

import hashlib
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from app.optimizer.normalizer import NORMALIZER_VERSION, NormalizedPlayer, PlayerInput, normalize_player

ALGORITHM_VERSION = "stackforge_126_v1"
MAP_POOL_VERSION = "active_duty_v1"
# Internal active map pool prior (never exposed as a map picker or recommendation)
INTERNAL_MAP_POOL: tuple[str, ...] = (
    "mirage",
    "inferno",
    "nuke",
    "overpass",
    "ancient",
    "anubis",
    "dust2",
)


class UnsatisfiableConstraintsError(ValueError):
    def __init__(self, message: str, reasons: list[str] | None = None):
        super().__init__(message)
        self.message = message
        self.reasons = reasons or [message]


class AllSplitsExhaustedError(ValueError):
    def __init__(self, message: str, valid_count: int):
        super().__init__(message)
        self.message = message
        self.valid_count = valid_count


@dataclass(frozen=True)
class TeamConstraints:
    locked_a: frozenset[str] = frozenset()
    locked_b: frozenset[str] = frozenset()
    together_pairs: tuple[tuple[str, str], ...] = ()
    opponent_pairs: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class EvaluatedSplit:
    partition_key: str
    team_a_ids: tuple[str, ...]
    team_b_ids: tuple[str, ...]
    team_a_strength: float
    team_b_strength: float
    strength_diff: float
    objective_score: float
    objective_components: dict[str, float]
    role_summary: dict[str, dict[str, int]]
    map_pool_summary: dict[str, float | bool]
    tie_breaker: str


@dataclass(frozen=True)
class OptimizationResult:
    algorithm_version: str
    normalizer_version: str
    map_pool_version: str
    seed: int
    recommended: EvaluatedSplit
    alternatives: list[EvaluatedSplit]
    normalized_players: dict[str, NormalizedPlayer]
    total_partitions_evaluated: int
    valid_partitions_count: int
    explanation: dict


def make_partition_key(ids_1: Iterable[str], ids_2: Iterable[str]) -> str:
    """Canonical key invariant to swapping Team A and Team B."""
    s1 = tuple(sorted(ids_1))
    s2 = tuple(sorted(ids_2))
    pair = (s1, s2) if s1 <= s2 else (s2, s1)
    return "|".join([",".join(pair[0]), ",".join(pair[1])])


def enumerate_126_partitions(player_ids: list[str]) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    """
    Enumerates all C(10, 5) / 2 = 126 unique unordered 5v5 partitions.
    Fixes player_ids[0] in group 1 and chooses 4 from the remaining 9 -> 126 unique splits.
    """
    if len(player_ids) != 10:
        raise ValueError(f"Expected exactly 10 players, got {len(player_ids)}.")
    if len(set(player_ids)) != 10:
        raise ValueError("All 10 player IDs must be unique.")

    anchor = player_ids[0]
    rest = player_ids[1:]
    partitions: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    for combo in combinations(rest, 4):
        group1 = (anchor,) + combo
        g1_set = set(group1)
        group2 = tuple(pid for pid in player_ids if pid not in g1_set)
        partitions.append((group1, group2))
    return partitions


def _validate_constraints_precheck(player_ids: set[str], constraints: TeamConstraints) -> None:
    reasons: list[str] = []

    overlap_lock = constraints.locked_a & constraints.locked_b
    if overlap_lock:
        reasons.append("One or more players are locked to both Team A and Team B.")

    if len(constraints.locked_a) > 5:
        reasons.append(f"{len(constraints.locked_a)} players are locked to Team A (maximum is 5).")
    if len(constraints.locked_b) > 5:
        reasons.append(f"{len(constraints.locked_b)} players are locked to Team B (maximum is 5).")

    for pid in constraints.locked_a | constraints.locked_b:
        if pid not in player_ids:
            reasons.append(f"Locked player {pid} is not in the 10-player roster.")

    for a, b in constraints.together_pairs:
        if a == b:
            continue
        if (a in constraints.locked_a and b in constraints.locked_b) or (
            a in constraints.locked_b and b in constraints.locked_a
        ):
            reasons.append("A 'Together' pair has players locked to opposite teams.")

    for a, b in constraints.opponent_pairs:
        if a == b:
            reasons.append("A player cannot be marked as an opponent of themselves.")
        elif (a in constraints.locked_a and b in constraints.locked_a) or (
            a in constraints.locked_b and b in constraints.locked_b
        ):
            reasons.append("An 'Opponent' pair has both players locked to the same team.")

    together_set = {frozenset((a, b)) for a, b in constraints.together_pairs if a != b}
    opponent_set = {frozenset((a, b)) for a, b in constraints.opponent_pairs if a != b}
    if together_set & opponent_set:
        reasons.append("Same pair is marked as both 'Together' and 'Opponent'.")

    if reasons:
        raise UnsatisfiableConstraintsError(" ".join(reasons), reasons=reasons)


def _orientation_satisfies(
    team_a: frozenset[str],
    team_b: frozenset[str],
    constraints: TeamConstraints,
) -> bool:
    if not constraints.locked_a.issubset(team_a):
        return False
    if not constraints.locked_b.issubset(team_b):
        return False
    for a, b in constraints.together_pairs:
        if (a in team_a) != (b in team_a):
            return False
    for a, b in constraints.opponent_pairs:
        if (a in team_a) == (b in team_a):
            return False
    return True


def _role_counts(players: list[NormalizedPlayer]) -> dict[str, int]:
    counts: dict[str, int] = {
        "Entry": 0,
        "Rifler": 0,
        "AWPer": 0,
        "Support": 0,
        "Lurker": 0,
        "IGL": 0,
        "Unassigned": 0,
    }
    for p in players:
        if p.primary_role and p.primary_role in counts:
            counts[p.primary_role] += 1
        else:
            counts["Unassigned"] += 1
    return counts


def _role_imbalance_penalty(roles_a: dict[str, int], roles_b: dict[str, int]) -> float:
    # Penalize asymmetric key tactical roles (especially AWPer, IGL, Entry, Support)
    weights = {
        "AWPer": 2.4,
        "IGL": 1.8,
        "Entry": 1.3,
        "Support": 1.3,
        "Rifler": 0.6,
        "Lurker": 0.7,
    }
    penalty = 0.0
    for role, w in weights.items():
        diff = abs(roles_a.get(role, 0) - roles_b.get(role, 0))
        # Extra penalty if one side has 2+ AWPers and the other has 0
        if role == "AWPer" and ((roles_a["AWPer"] >= 2 and roles_b["AWPer"] == 0) or (roles_b["AWPer"] >= 2 and roles_a["AWPer"] == 0)):
            penalty += 4.0
        else:
            penalty += w * max(0, diff - 0) * 0.45
    return round(penalty, 3)


def evaluate_split(
    team_a_ids: tuple[str, ...],
    team_b_ids: tuple[str, ...],
    normalized: dict[str, NormalizedPlayer],
    seed: int,
) -> EvaluatedSplit:
    team_a_players = [normalized[pid] for pid in team_a_ids]
    team_b_players = [normalized[pid] for pid in team_b_ids]

    sum_a = sum(p.normalized_strength for p in team_a_players)
    sum_b = sum(p.normalized_strength for p in team_b_players)
    avg_a = round(sum_a / 5.0, 2)
    avg_b = round(sum_b / 5.0, 2)
    strength_diff = round(abs(avg_a - avg_b), 2)

    # Top-end skill parity (prevent 1 carry + 4 weak vs 5 solid from hiding behind equal average)
    top2_a = sum(sorted((p.normalized_strength for p in team_a_players), reverse=True)[:2]) / 2.0
    top2_b = sum(sorted((p.normalized_strength for p in team_b_players), reverse=True)[:2]) / 2.0
    top_carry_gap = round(abs(top2_a - top2_b), 3)

    # Role balance
    roles_a = _role_counts(team_a_players)
    roles_b = _role_counts(team_b_players)
    role_penalty = _role_imbalance_penalty(roles_a, roles_b)

    # Recent form balance
    form_a = sum(p.recent_form_normalized for p in team_a_players) / 5.0
    form_b = sum(p.recent_form_normalized for p in team_b_players) / 5.0
    form_gap = round(abs(form_a - form_b), 3)

    # Hidden map-pool robustness across active duty maps (equal weights 1/7)
    has_map_data = any(bool(p.map_adjustments) for p in team_a_players + team_b_players)
    if has_map_data:
        map_gaps = []
        for m in INTERNAL_MAP_POOL:
            ma = avg_a + sum(p.map_adjustments.get(m, 0.0) for p in team_a_players) / 5.0
            mb = avg_b + sum(p.map_adjustments.get(m, 0.0) for p in team_b_players) / 5.0
            map_gaps.append(abs(ma - mb))
        expected_map_gap = round(sum(map_gaps) / len(map_gaps), 3)
        worst_map_gap = round(max(map_gaps), 3)
        map_robustness_penalty = round(0.25 * expected_map_gap + 0.15 * worst_map_gap, 3)
    else:
        expected_map_gap = strength_diff
        worst_map_gap = strength_diff
        map_robustness_penalty = 0.0

    # Composite deterministic objective (lower is better)
    objective_score = round(
        strength_diff * 2.2
        + top_carry_gap * 0.45
        + role_penalty * 0.65
        + form_gap * 0.35
        + map_robustness_penalty,
        4,
    )

    pkey = make_partition_key(team_a_ids, team_b_ids)
    tie_breaker = hashlib.sha256(f"{seed}:{pkey}".encode("utf-8")).hexdigest()[:16]

    return EvaluatedSplit(
        partition_key=pkey,
        team_a_ids=tuple(sorted(team_a_ids, key=lambda pid: -normalized[pid].normalized_strength)),
        team_b_ids=tuple(sorted(team_b_ids, key=lambda pid: -normalized[pid].normalized_strength)),
        team_a_strength=avg_a,
        team_b_strength=avg_b,
        strength_diff=strength_diff,
        objective_score=objective_score,
        objective_components={
            "strength_gap": strength_diff,
            "top_carry_gap": top_carry_gap,
            "role_imbalance": role_penalty,
            "form_imbalance": form_gap,
            "map_pool_penalty": map_robustness_penalty,
        },
        role_summary={"team_a": roles_a, "team_b": roles_b},
        map_pool_summary={
            "has_map_data": has_map_data,
            "expected_map_gap": expected_map_gap,
            "worst_map_gap": worst_map_gap,
        },
        tie_breaker=tie_breaker,
    )


def _balance_indicator(strength_diff: float) -> str:
    if strength_diff <= 1.5:
        return "Very Tight"
    if strength_diff <= 3.5:
        return "Balanced"
    if strength_diff <= 6.5:
        return "Slight Edge"
    return "Skewed"


def _split_distance(a: EvaluatedSplit, b: EvaluatedSplit) -> int:
    """Minimum number of players displaced between two partitions (symmetric over A/B)."""
    a_set = set(a.team_a_ids)
    b_a_set = set(b.team_a_ids)
    b_b_set = set(b.team_b_ids)
    return min(len(a_set ^ b_a_set), len(a_set ^ b_b_set)) // 2


def build_explanation(
    split: EvaluatedSplit,
    normalized: dict[str, NormalizedPlayer],
    constraints: TeamConstraints,
    valid_count: int,
    alternatives_count: int,
) -> dict:
    players_list = list(normalized.values())
    avg_conf = round(sum(p.confidence for p in players_list) / len(players_list), 2)
    manual_only_players = [p.display_name for p in players_list if p.sources_used == ["manual"]]
    unverified_players = [p.display_name for p in players_list if not p.steam_id64]

    roles_a = split.role_summary["team_a"]
    roles_b = split.role_summary["team_b"]
    role_notes = []
    if roles_a.get("AWPer", 0) or roles_b.get("AWPer", 0):
        role_notes.append(f"AWPers: Team A {roles_a['AWPer']} vs Team B {roles_b['AWPer']}")
    if roles_a.get("IGL", 0) or roles_b.get("IGL", 0):
        role_notes.append(f"IGLs: Team A {roles_a['IGL']} vs Team B {roles_b['IGL']}")
    if roles_a.get("Entry", 0) or roles_b.get("Entry", 0):
        role_notes.append(f"Entries: Team A {roles_a['Entry']} vs Team B {roles_b['Entry']}")
    if roles_a.get("Support", 0) or roles_b.get("Support", 0):
        role_notes.append(f"Supports: Team A {roles_a['Support']} vs Team B {roles_b['Support']}")

    constraints_honored = []
    if constraints.locked_a:
        names = [normalized[pid].display_name for pid in sorted(constraints.locked_a) if pid in normalized]
        constraints_honored.append(f"Locked to Team A: {', '.join(names)}")
    if constraints.locked_b:
        names = [normalized[pid].display_name for pid in sorted(constraints.locked_b) if pid in normalized]
        constraints_honored.append(f"Locked to Team B: {', '.join(names)}")
    if constraints.together_pairs:
        constraints_honored.append(f"{len(constraints.together_pairs)} together-pair constraint(s) enforced")
    if constraints.opponent_pairs:
        constraints_honored.append(f"{len(constraints.opponent_pairs)} opponent-pair constraint(s) enforced")

    indicator = _balance_indicator(split.strength_diff)
    summary_parts = [
        f"{indicator} split across 126 evaluated partitions ({valid_count} matched constraints): "
        f"Team A {split.team_a_strength:.1f} vs Team B {split.team_b_strength:.1f} (gap {split.strength_diff:.2f})."
    ]
    if split.objective_components["role_imbalance"] <= 1.2 and role_notes:
        summary_parts.append("Role coverage is well-distributed (" + "; ".join(role_notes[:3]) + ").")
    elif role_notes:
        summary_parts.append("Role distribution: " + "; ".join(role_notes[:3]) + ".")

    if split.map_pool_summary["has_map_data"]:
        summary_parts.append(
            f"Map-pool robustness evaluated across active pool ({MAP_POOL_VERSION}): "
            f"expected gap {split.map_pool_summary['expected_map_gap']:.2f}, "
            f"worst-map gap {split.map_pool_summary['worst_map_gap']:.2f} (maps remain random)."
        )
    else:
        summary_parts.append(
            f"Equal map-pool prior ({MAP_POOL_VERSION}) applied; maps remain random."
        )

    if manual_only_players:
        summary_parts.append(
            f"Low-confidence notice: {len(manual_only_players)}/10 player(s) rely on manual rating only "
            "(missing external Premier/FACEIT/Leetify stats; missing stats are unknown, not zero)."
        )

    return {
        "balance_indicator": indicator,
        "summary": " ".join(summary_parts),
        "avg_confidence": avg_conf,
        "confidence_label": "High" if avg_conf >= 0.8 else ("Medium" if avg_conf >= 0.65 else "Low (Manual Baseline)"),
        "manual_only_count": len(manual_only_players),
        "manual_only_players": manual_only_players,
        "unverified_identity_players": unverified_players,
        "role_notes": role_notes,
        "constraints_honored": constraints_honored,
        "alternatives_found": alternatives_count,
        "map_policy_note": "Maps are random in actual play; no map is selected or predicted.",
    }


def optimize_teams(
    players: list[PlayerInput],
    constraints: TeamConstraints | None = None,
    seed: int = 42,
    exclude_partition_keys: set[str] | None = None,
    max_alternatives: int = 4,
) -> OptimizationResult:
    """
    Deterministic exhaustive 126-partition 5v5 team optimizer.
    """
    constraints = constraints or TeamConstraints()
    exclude_keys = exclude_partition_keys or set()

    if len(players) != 10:
        raise ValueError(f"Exactly 10 players are required, got {len(players)}.")

    normalized = {p.community_player_id: normalize_player(p) for p in players}
    if len(normalized) != 10:
        raise ValueError("Duplicate players detected in roster.")

    player_ids = [p.community_player_id for p in players]
    _validate_constraints_precheck(set(player_ids), constraints)

    raw_partitions = enumerate_126_partitions(player_ids)
    assert len(raw_partitions) == 126

    has_directional_lock = bool(constraints.locked_a or constraints.locked_b)
    valid_splits: list[EvaluatedSplit] = []

    for g1, g2 in raw_partitions:
        g1_set, g2_set = frozenset(g1), frozenset(g2)
        if has_directional_lock:
            if _orientation_satisfies(g1_set, g2_set, constraints):
                valid_splits.append(evaluate_split(g1, g2, normalized, seed))
            elif _orientation_satisfies(g2_set, g1_set, constraints):
                valid_splits.append(evaluate_split(g2, g1, normalized, seed))
        else:
            if _orientation_satisfies(g1_set, g2_set, constraints):
                # Deterministic canonical orientation using seed hash
                key = make_partition_key(g1, g2)
                flip_bit = int(hashlib.sha256(f"{seed}:orient:{key}".encode("utf-8")).hexdigest()[0], 16) % 2
                if flip_bit == 1:
                    valid_splits.append(evaluate_split(g2, g1, normalized, seed))
                else:
                    valid_splits.append(evaluate_split(g1, g2, normalized, seed))

    if not valid_splits:
        raise UnsatisfiableConstraintsError(
            "No valid 5v5 split exists among the 126 partitions that satisfies all current locks and pair constraints. "
            "Remove or relax a lock/pair constraint and try again."
        )

    valid_splits.sort(key=lambda s: (s.objective_score, s.strength_diff, s.tie_breaker))

    candidate_pool = [s for s in valid_splits if s.partition_key not in exclude_keys]
    if not candidate_pool:
        raise AllSplitsExhaustedError(
            f"All {len(valid_splits)} valid split(s) under the current locks and constraints have already been generated. "
            "Restore an earlier proposal, swap players manually, or relax a lock to explore new splits.",
            valid_count=len(valid_splits),
        )

    recommended = candidate_pool[0]

    # Pick materially distinct alternatives (prefer >=2 swaps away first, then fill with next best distinct)
    alternatives: list[EvaluatedSplit] = []
    for s in valid_splits:
        if s.partition_key == recommended.partition_key:
            continue
        if len(alternatives) >= max_alternatives:
            break
        if all(_split_distance(s, chosen) >= 2 for chosen in [recommended] + alternatives):
            alternatives.append(s)

    if len(alternatives) < max_alternatives:
        chosen_keys = {recommended.partition_key} | {a.partition_key for a in alternatives}
        for s in valid_splits:
            if s.partition_key not in chosen_keys:
                alternatives.append(s)
                chosen_keys.add(s.partition_key)
            if len(alternatives) >= max_alternatives:
                break

    explanation = build_explanation(
        recommended, normalized, constraints, valid_count=len(valid_splits), alternatives_count=len(alternatives)
    )

    return OptimizationResult(
        algorithm_version=ALGORITHM_VERSION,
        normalizer_version=NORMALIZER_VERSION,
        map_pool_version=MAP_POOL_VERSION,
        seed=seed,
        recommended=recommended,
        alternatives=alternatives,
        normalized_players=normalized,
        total_partitions_evaluated=126,
        valid_partitions_count=len(valid_splits),
        explanation=explanation,
    )
