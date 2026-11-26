from __future__ import annotations

import hashlib
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from app.optimizer.normalizer import NORMALIZER_VERSION, NormalizedPlayer, PlayerInput, normalize_player

ALGORITHM_VERSION = "stackforge_126_v2"
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
    counts: dict[str, int] = {"AWPer": 0, "IGL": 0, "Entry": 0, "Support": 0, "Rifler": 0, "Lurker": 0}
    for p in players:
        if p.primary_role and p.primary_role in counts:
            counts[p.primary_role] += 1
    return counts


def _role_imbalance_penalty(roles_a: dict[str, int], roles_b: dict[str, int]) -> float:
    """Rewards having complementary core roles (AWPer, IGL, Entry, Support) across teams."""
    penalty = 0.0
    for role, weight in (("AWPer", 1.5), ("IGL", 1.2), ("Entry", 1.0), ("Support", 0.9)):
        total = roles_a.get(role, 0) + roles_b.get(role, 0)
        if total == 0:
            continue
        penalty += abs(roles_a.get(role, 0) - roles_b.get(role, 0)) * weight
        if roles_a.get(role, 0) == 0 or roles_b.get(role, 0) == 0:
            if total >= 2:
                penalty += weight * 0.8
    return round(penalty, 3)


def _coverage_weighted_gap(
    team_a: list[NormalizedPlayer],
    team_b: list[NormalizedPlayer],
    attr: str,
) -> tuple[float, float]:
    """Returns (absolute gap between side means, coverage fraction in [0, 1])."""
    vals_a = [getattr(p, attr) for p in team_a if getattr(p, attr) is not None]
    vals_b = [getattr(p, attr) for p in team_b if getattr(p, attr) is not None]
    total_tracked = len(vals_a) + len(vals_b)
    if not vals_a or not vals_b:
        return 0.0, 0.0
    coverage = total_tracked / 10.0
    gap = abs((sum(vals_a) / len(vals_a)) - (sum(vals_b) / len(vals_b)))
    return round(gap, 3), round(coverage, 2)


def evaluate_split(
    team_a_ids: tuple[str, ...],
    team_b_ids: tuple[str, ...],
    normalized: dict[str, NormalizedPlayer],
    seed: int,
    neutral_prior: float | None = None,
) -> EvaluatedSplit:
    team_a_players = [normalized[pid] for pid in team_a_ids]
    team_b_players = [normalized[pid] for pid in team_b_ids]

    if neutral_prior is None:
        all_rated = [p.normalized_strength for p in normalized.values() if p.normalized_strength is not None]
        neutral_prior = round(sum(all_rated) / len(all_rated), 2) if all_rated else 50.0

    def _effective_strength(p: NormalizedPlayer) -> float:
        return p.normalized_strength if p.normalized_strength is not None else neutral_prior

    eff_a = [_effective_strength(p) for p in team_a_players]
    eff_b = [_effective_strength(p) for p in team_b_players]
    avg_a = round(sum(eff_a) / 5.0, 2)
    avg_b = round(sum(eff_b) / 5.0, 2)
    strength_diff = round(abs(avg_a - avg_b), 2)

    # Split insufficient-data players evenly so one side never receives all unrated accounts
    unrated_a = sum(1 for p in team_a_players if p.normalized_strength is None)
    unrated_b = sum(1 for p in team_b_players if p.normalized_strength is None)
    unknown_count_gap = abs(unrated_a - unrated_b)

    # Top-end skill parity among rated players
    top2_a = sum(sorted(eff_a, reverse=True)[:2]) / 2.0
    top2_b = sum(sorted(eff_b, reverse=True)[:2]) / 2.0
    top_carry_gap = round(abs(top2_a - top2_b), 3)

    # Coverage-weighted multi-dimensional CS2 balance
    aim_gap, aim_cov = _coverage_weighted_gap(team_a_players, team_b_players, "aim_score")
    util_gap, util_cov = _coverage_weighted_gap(team_a_players, team_b_players, "utility_score")
    entry_gap, entry_cov = _coverage_weighted_gap(team_a_players, team_b_players, "entry_score")
    trade_gap, trade_cov = _coverage_weighted_gap(team_a_players, team_b_players, "trade_score")
    clutch_gap, clutch_cov = _coverage_weighted_gap(team_a_players, team_b_players, "clutch_score")
    cons_gap, cons_cov = _coverage_weighted_gap(team_a_players, team_b_players, "consistency_score")

    # Role balance
    roles_a = _role_counts(team_a_players)
    roles_b = _role_counts(team_b_players)
    role_penalty = _role_imbalance_penalty(roles_a, roles_b)

    # Recent form balance
    form_a_vals = [p.recent_form_normalized for p in team_a_players if p.has_recent_form]
    form_b_vals = [p.recent_form_normalized for p in team_b_players if p.has_recent_form]
    if form_a_vals and form_b_vals:
        form_cov = (len(form_a_vals) + len(form_b_vals)) / 10.0
        form_gap = round(abs((sum(form_a_vals) / len(form_a_vals)) - (sum(form_b_vals) / len(form_b_vals))) * form_cov, 3)
    else:
        form_gap = 0.0

    # Internal active map-pool robustness (equal weights 1/7; never exposes a map picker)
    has_map_data = any(bool(p.map_adjustments) for p in team_a_players + team_b_players)
    if has_map_data:
        map_gaps = []
        for m in INTERNAL_MAP_POOL:
            ma = avg_a + sum(p.map_adjustments.get(m, 0.0) for p in team_a_players) / 5.0
            mb = avg_b + sum(p.map_adjustments.get(m, 0.0) for p in team_b_players) / 5.0
            map_gaps.append(abs(ma - mb))
        expected_map_gap = round(sum(map_gaps) / len(map_gaps), 3)
        worst_map_gap = round(max(map_gaps), 3)
        map_robustness_penalty = round(0.22 * expected_map_gap + 0.14 * worst_map_gap, 3)
    else:
        expected_map_gap = strength_diff
        worst_map_gap = strength_diff
        map_robustness_penalty = 0.0

    # Calibrated composite objective (missing dimensions automatically shrink via coverage weights)
    objective_score = round(
        strength_diff * 2.4
        + unknown_count_gap * 3.5
        + top_carry_gap * 0.45
        + aim_gap * (0.28 * aim_cov)
        + util_gap * (0.24 * util_cov)
        + entry_gap * (0.14 * entry_cov)
        + trade_gap * (0.12 * trade_cov)
        + clutch_gap * (0.10 * clutch_cov)
        + cons_gap * (0.10 * cons_cov)
        + role_penalty * 0.55
        + form_gap * 0.35
        + map_robustness_penalty,
        4,
    )

    pkey = make_partition_key(team_a_ids, team_b_ids)
    tie_breaker = hashlib.sha256(f"{seed}:{pkey}".encode("utf-8")).hexdigest()[:16]

    def _sort_key(pid: str) -> tuple[float, float, str]:
        p = normalized[pid]
        return (-(p.normalized_strength if p.normalized_strength is not None else -1.0), -p.confidence, p.display_name)

    return EvaluatedSplit(
        partition_key=pkey,
        team_a_ids=tuple(sorted(team_a_ids, key=_sort_key)),
        team_b_ids=tuple(sorted(team_b_ids, key=_sort_key)),
        team_a_strength=avg_a,
        team_b_strength=avg_b,
        strength_diff=strength_diff,
        objective_score=objective_score,
        objective_components={
            "strength_gap": strength_diff,
            "unknown_count_gap": float(unknown_count_gap),
            "top_carry_gap": top_carry_gap,
            "aim_gap": round(aim_gap * aim_cov, 3),
            "utility_gap": round(util_gap * util_cov, 3),
            "entry_gap": round(entry_gap * entry_cov, 3),
            "trade_gap": round(trade_gap * trade_cov, 3),
            "clutch_gap": round(clutch_gap * clutch_cov, 3),
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
        return "Very close matchup"
    if strength_diff <= 3.8:
        return "Competitive matchup"
    return "Some imbalance — consider an alternative"


def _avg_metric(players: list[NormalizedPlayer], attr: str) -> tuple[float | None, int]:
    vals = [getattr(p, attr) for p in players if getattr(p, attr) is not None]
    if not vals:
        return None, 0
    return round(sum(vals) / len(vals), 2), len(vals)


def _team_cs2_notes(
    side_players: list[NormalizedPlayer],
    other_players: list[NormalizedPlayer],
) -> list[str]:
    notes: list[str] = []

    aim_s, aim_n = _avg_metric(side_players, "aim_rating")
    aim_o, aim_no = _avg_metric(other_players, "aim_rating")
    pre_s, _ = _avg_metric(side_players, "preaim")
    if aim_n >= 2 and aim_s is not None:
        pre_txt = f", {pre_s:.1f}° pre-aim" if pre_s is not None else ""
        if aim_no >= 2 and aim_o is not None and aim_s >= aim_o + 2.5:
            notes.append(f"Better aim-related statistics ({aim_s:.1f} avg Aim Rating{pre_txt} across {aim_n} players).")
        elif aim_s >= 60.0:
            notes.append(f"Sharp mechanical core ({aim_s:.1f} avg Aim Rating{pre_txt}).")

    open_s, open_n = _avg_metric(side_players, "opening_duel_pct")
    open_o, open_no = _avg_metric(other_players, "opening_duel_pct")
    if open_n >= 2 and open_s is not None:
        if open_no >= 2 and open_o is not None and open_s >= open_o + 2.5:
            notes.append(f"Stronger available opening-duel potential ({open_s:.1f}% first-contact wins).")
        elif open_no >= 2 and open_o is not None and open_s + 2.5 <= open_o:
            notes.append("Needs to coordinate opening fights and early utility carefully.")

    adr_s, adr_n = _avg_metric(side_players, "adr")
    adr_o, adr_no = _avg_metric(other_players, "adr")
    kd_s, _ = _avg_metric(side_players, "kd_ratio")
    if adr_n >= 2 and adr_s is not None:
        if adr_no >= 2 and adr_o is not None and adr_s >= adr_o + 3.0:
            notes.append(f"Higher damage output ({adr_s:.1f} avg ADR{f', {kd_s:.2f} K/D' if kd_s else ''} across {adr_n} tracked players).")
        elif adr_s >= 76.0:
            notes.append(f"Good damage output across recent rounds ({adr_s:.1f} avg ADR).")

    util_s, util_n = _avg_metric(side_players, "utility_rating")
    util_o, util_no = _avg_metric(other_players, "utility_rating")
    flash_s, _ = _avg_metric(side_players, "flash_assists_per_round")
    if util_n >= 2 and util_s is not None:
        flash_txt = f" and {flash_s:.2f} flash assists/rd" if flash_s is not None else ""
        if util_no >= 2 and util_o is not None and util_s >= util_o + 3.0:
            notes.append(f"More balanced utility contribution ({util_s:.1f} avg Utility Rating{flash_txt}).")
        elif util_no >= 2 and util_o is not None and util_s + 3.5 <= util_o:
            notes.append("Slightly less utility contribution — lean on coordinated execute flashes.")

    trade_s, trade_n = _avg_metric(side_players, "trade_kills_per_match")
    trade_o, trade_no = _avg_metric(other_players, "trade_kills_per_match")
    if trade_n >= 2 and trade_s is not None and trade_no >= 2 and trade_o is not None and trade_s >= trade_o + 2.5:
        notes.append(f"More consistent trading performance ({trade_s:.1f}% trade-kill conversion).")

    cons_s, cons_n = _avg_metric(side_players, "consistency_score")
    cons_o, cons_no = _avg_metric(other_players, "consistency_score")
    if cons_n >= 2 and cons_s is not None and cons_no >= 2 and cons_o is not None and cons_s >= cons_o + 2.5:
        notes.append(f"Better recent mechanical consistency ({cons_s:.1f}% clean counter-strafed shots).")

    clutch_s, clutch_n = _avg_metric(side_players, "clutch_win_pct")
    clutch_o, clutch_no = _avg_metric(other_players, "clutch_win_pct")
    if clutch_n >= 2 and clutch_s is not None and clutch_no >= 2 and clutch_o is not None and clutch_s >= clutch_o + 2.5:
        notes.append(f"Stronger available clutch numbers ({clutch_s:.1f}% 1vX conversion).")

    form_vals = [p.recent_form_normalized for p in side_players if p.has_recent_form]
    other_form = [p.recent_form_normalized for p in other_players if p.has_recent_form]
    if form_vals and other_form:
        avg_f = sum(form_vals) / len(form_vals)
        avg_of = sum(other_form) / len(other_form)
        if avg_f >= avg_of + 0.8:
            notes.append("Entering with stronger recent form across their latest tracked matches.")

    explicit_roles = [p.primary_role for p in side_players if p.primary_role]
    if explicit_roles:
        counts = {r: explicit_roles.count(r) for r in dict.fromkeys(explicit_roles)}
        role_str = ", ".join(f"{cnt} {r}" if cnt > 1 else r for r, cnt in counts.items())
        notes.append(f"Tagged roles: {role_str}.")

    if not notes:
        notes.append("Limited external match statistics available for this lineup; consider refreshing profiles if linked.")

    return notes[:4]


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
    alternatives: list[EvaluatedSplit] | None = None,
) -> dict:
    players_list = list(normalized.values())
    avg_conf = round(sum(p.confidence for p in players_list) / len(players_list), 2)
    insufficient_players = [p.display_name for p in players_list if p.data_status == "INSUFFICIENT_DATA"]
    low_conf_players = [p.display_name for p in players_list if p.data_status == "LOW_CONFIDENCE"]
    unverified_players = [p.display_name for p in players_list if not p.steam_id64]
    data_coverage_pct = round(((10 - len(insufficient_players)) / 10.0) * 100.0)

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

    def _display_rank_key(p: NormalizedPlayer) -> tuple[float, float, str]:
        return (-(p.normalized_strength if p.normalized_strength is not None else -1.0), -p.confidence, p.display_name)

    team_a_sorted = sorted([normalized[pid] for pid in split.team_a_ids], key=_display_rank_key)
    team_b_sorted = sorted([normalized[pid] for pid in split.team_b_ids], key=_display_rank_key)
    top_a, low_a = team_a_sorted[0], team_a_sorted[-1]
    top_b, low_b = team_b_sorted[0], team_b_sorted[-1]

    def _fmt_p(p: NormalizedPlayer) -> str:
        s = f"{p.normalized_strength:.1f}" if p.normalized_strength is not None else "Insufficient Data"
        return f"{p.display_name} ({s}" + (f", {p.primary_role})" if p.primary_role else ")")

    player_contributions = [
        f"Team A anchor: {_fmt_p(top_a)} paired with {_fmt_p(low_a)}.",
        f"Team B anchor: {_fmt_p(top_b)} paired with {_fmt_p(low_b)}.",
    ]

    form_a = sum(p.recent_form_normalized for p in team_a_sorted) / 5.0
    form_b = sum(p.recent_form_normalized for p in team_b_sorted) / 5.0
    form_tracked = sum(1 for p in players_list if p.has_recent_form)
    if form_tracked > 0:
        recent_form_summary = (
            f"Recent form tracked for {form_tracked}/10 player(s): "
            f"Team A {form_a:+.2f} vs Team B {form_b:+.2f}."
        )
    else:
        recent_form_summary = "No recent-form deltas available from providers yet."

    trade_offs = []
    if split.objective_components.get("top_carry_gap", 0.0) > 2.5:
        higher_top = "Team A" if (top_a.normalized_strength or 0.0) >= (top_b.normalized_strength or 0.0) else "Team B"
        trade_offs.append(f"{higher_top} holds the stronger top-end carry, offset by deeper mid-roster balance on the opposing side.")
    if split.objective_components.get("role_imbalance", 0.0) > 1.5:
        trade_offs.append("Accepted minor role asymmetry to keep overall competitive skill close.")
    if not trade_offs:
        trade_offs.append("Balanced overall skill, role coverage, and available CS2 indicators cleanly.")

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

    alternative_comparisons = []
    for alt in (alternatives or []):
        rec_a = set(split.team_a_ids)
        alt_a = set(alt.team_a_ids)
        alt_b = set(alt.team_b_ids)
        if len(rec_a ^ alt_a) <= len(rec_a ^ alt_b):
            moved_to_b = [normalized[pid].display_name for pid in sorted(rec_a - alt_a)]
            moved_to_a = [normalized[pid].display_name for pid in sorted(alt_a - rec_a)]
        else:
            moved_to_b = [normalized[pid].display_name for pid in sorted(rec_a - alt_b)]
            moved_to_a = [normalized[pid].display_name for pid in sorted(alt_b - rec_a)]
        diff_delta = round(alt.strength_diff - split.strength_diff, 2)
        alternative_comparisons.append(
            {
                "partition_key": alt.partition_key,
                "strength_diff": alt.strength_diff,
                "strength_diff_delta": diff_delta,
                "moved_players": f"To A: {', '.join(moved_to_a)} | To B: {', '.join(moved_to_b)}",
                "trade_off": f"Team strength gap {diff_delta:+.2f} compared to active split.",
            }
        )

    team_a_notes = _team_cs2_notes(team_a_sorted, team_b_sorted)
    team_b_notes = _team_cs2_notes(team_b_sorted, team_a_sorted)

    stale_count = sum(1 for p in players_list if p.stats_stale)
    tracked_combat = sum(1 for p in players_list if p.stats_sample_size >= 5)

    good_match_parts = []
    if split.strength_diff <= 1.5:
        good_match_parts.append("Both teams have comparable overall competitive strength and should trade rounds closely.")
    elif split.strength_diff <= 3.8:
        good_match_parts.append("Overall team strength is closely matched, leaving plenty of room for mid-round calling and momentum swings.")
    else:
        good_match_parts.append(
            f"There is a noticeable rating gap ({split.strength_diff:.1f} pts) under current locks — consider checking an alternative split or swapping a pair."
        )

    # Contrast real mechanical/utility/combat styles cleanly without inventing numbers
    aim_a, an_a = _avg_metric(team_a_sorted, "aim_rating")
    aim_b, an_b = _avg_metric(team_b_sorted, "aim_rating")
    util_a, un_a = _avg_metric(team_a_sorted, "utility_rating")
    util_b, un_b = _avg_metric(team_b_sorted, "utility_rating")
    if an_a >= 2 and an_b >= 2 and aim_a is not None and aim_b is not None:
        if aim_a >= aim_b + 2.5 and un_a >= 2 and un_b >= 2 and util_b is not None and util_a is not None and util_b >= util_a + 2.0:
            good_match_parts.append("Team A holds a mechanical aim edge, while Team B brings stronger utility fundamentals.")
        elif aim_b >= aim_a + 2.5 and un_a >= 2 and un_b >= 2 and util_a is not None and util_b is not None and util_a >= util_b + 2.0:
            good_match_parts.append("Team B holds a mechanical aim edge, while Team A brings stronger utility fundamentals.")

    if split.map_pool_summary["has_map_data"]:
        good_match_parts.append(
            "Both lineups hold up evenly across the active map pool, so a random map draw should stay competitive."
        )

    uncertainty_bits = []
    if insufficient_players:
        uncertainty_bits.append(f"{len(insufficient_players)} player(s) have insufficient external data and remain unranked")
    if low_conf_players:
        uncertainty_bits.append(f"{len(low_conf_players)} player(s) have low-confidence external coverage")
    if stale_count:
        uncertainty_bits.append(f"{stale_count} player(s) have older cached stats")
    if tracked_combat < 6 and len(insufficient_players) < 10:
        uncertainty_bits.append("match history coverage is partial across the lobby")
    if uncertainty_bits:
        good_match_parts.append("Uncertainty note: " + "; ".join(uncertainty_bits) + ".")

    good_match_summary = " ".join(good_match_parts)
    indicator = _balance_indicator(split.strength_diff)

    share_summary = (
        f"{indicator} (Team A {split.team_a_strength:.1f} vs Team B {split.team_b_strength:.1f}). "
        + (good_match_parts[0] if good_match_parts else "")
    )

    return {
        "balance_indicator": indicator,
        "matchup_label": indicator,
        "summary": good_match_summary,
        "good_match_summary": good_match_summary,
        "team_a_notes": team_a_notes,
        "team_b_notes": team_b_notes,
        "share_summary": share_summary,
        "avg_confidence": avg_conf,
        "data_coverage_pct": data_coverage_pct,
        "confidence_label": "High" if avg_conf >= 0.78 else ("Medium" if avg_conf >= 0.55 else "Insufficient Data"),
        "manual_only_count": len(insufficient_players),
        "manual_only_players": insufficient_players,
        "insufficient_data_players": insufficient_players,
        "low_confidence_players": low_conf_players,
        "stale_count": stale_count,
        "unverified_identity_players": unverified_players,
        "role_notes": role_notes,
        "player_contributions": player_contributions,
        "recent_form_summary": recent_form_summary,
        "trade_offs": trade_offs,
        "alternative_comparisons": alternative_comparisons,
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

    rated_vals = [n.normalized_strength for n in normalized.values() if n.normalized_strength is not None]
    neutral_prior = round(sum(rated_vals) / len(rated_vals), 2) if rated_vals else 50.0

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
                valid_splits.append(evaluate_split(g1, g2, normalized, seed, neutral_prior=neutral_prior))
            elif _orientation_satisfies(g2_set, g1_set, constraints):
                valid_splits.append(evaluate_split(g2, g1, normalized, seed, neutral_prior=neutral_prior))
        else:
            if _orientation_satisfies(g1_set, g2_set, constraints):
                key = make_partition_key(g1, g2)
                flip_bit = int(hashlib.sha256(f"{seed}:orient:{key}".encode("utf-8")).hexdigest()[0], 16) % 2
                if flip_bit == 1:
                    valid_splits.append(evaluate_split(g2, g1, normalized, seed, neutral_prior=neutral_prior))
                else:
                    valid_splits.append(evaluate_split(g1, g2, normalized, seed, neutral_prior=neutral_prior))

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
        recommended,
        normalized,
        constraints,
        valid_count=len(valid_splits),
        alternatives_count=len(alternatives),
        alternatives=alternatives,
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
