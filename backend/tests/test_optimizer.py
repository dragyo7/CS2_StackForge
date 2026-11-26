from __future__ import annotations

import pytest

from app.optimizer.engine import (
    AllSplitsExhaustedError,
    TeamConstraints,
    UnsatisfiableConstraintsError,
    enumerate_126_partitions,
    make_partition_key,
    optimize_teams,
)
from app.optimizer.normalizer import (
    PlayerInput,
    normalize_faceit,
    normalize_leetify,
    normalize_player,
    normalize_premier,
)


def _make_ten_players() -> list[PlayerInput]:
    specs = [
        ("p1", "Kairo", 84.0, 20500, 2000, None, "AWPer"),
        ("p2", "Vexen", 78.0, 18500, None, None, "IGL"),
        ("p3", "Mako", 73.0, None, 1720, 0.04, "Entry"),
        ("p4", "Nori", 69.0, 15200, None, None, "Rifler"),
        ("p5", "Sora", 65.0, None, None, None, "Support"),
        ("p6", "Dax", 62.0, 13400, None, -0.01, "Lurker"),
        ("p7", "Riven", 58.0, None, None, None, "Entry"),
        ("p8", "Taro", 54.0, None, None, None, "AWPer"),
        ("p9", "Juno", 48.0, None, None, None, "Support"),
        ("p10", "Kip", 42.0, None, None, None, "Rifler"),
    ]
    return [
        PlayerInput(
            community_player_id=pid,
            display_name=name,
            steam_id64=f"7656119800000000{idx}",
            identity_status="STEAM_PARSED",
            manual_rating=manual,
            premier_rating=prem,
            faceit_elo=faceit,
            leetify_rating=leet,
            primary_role=role,
        )
        for idx, (pid, name, manual, prem, faceit, leet, role) in enumerate(specs)
    ]


def test_126_unique_partitions_no_mirrored_duplicates():
    ids = [f"p{i}" for i in range(1, 11)]
    parts = enumerate_126_partitions(ids)
    assert len(parts) == 126

    keys = set()
    for g1, g2 in parts:
        assert len(g1) == 5
        assert len(g2) == 5
        assert set(g1).isdisjoint(set(g2))
        assert set(g1) | set(g2) == set(ids)
        keys.add(make_partition_key(g1, g2))
    assert len(keys) == 126


def test_missing_stats_are_unknown_not_zero():
    manual_only = PlayerInput(
        community_player_id="m1",
        display_name="ManualOnly",
        steam_id64=None,
        identity_status="MANUAL_ONLY",
        manual_rating=95.0,
    )
    norm = normalize_player(manual_only)
    assert norm.normalized_strength is None
    assert norm.data_status == "INSUFFICIENT_DATA"
    assert norm.strength_band == "Insufficient Data"
    assert norm.confidence == 0.0
    assert set(norm.missing_sources) == {"premier", "faceit", "leetify", "recent_form"}

    # Legacy manual_rating is completely ignored even when Premier CSR exists
    with_prem_high_manual = PlayerInput(
        community_player_id="m2",
        display_name="WithPrem",
        steam_id64=None,
        identity_status="MANUAL_ONLY",
        manual_rating=99.0,
        premier_rating=20000,
    )
    with_prem_low_manual = PlayerInput(
        community_player_id="m2",
        display_name="WithPrem",
        steam_id64=None,
        identity_status="MANUAL_ONLY",
        manual_rating=10.0,
        premier_rating=20000,
    )
    norm_p = normalize_player(with_prem_high_manual)
    norm_p_low = normalize_player(with_prem_low_manual)
    assert norm_p.normalized_strength == norm_p_low.normalized_strength
    assert 70.0 <= (norm_p.normalized_strength or 0.0) <= 80.0
    assert norm_p.confidence > norm.confidence
    assert normalize_premier(20000) == 74.0
    assert normalize_faceit(2000) == 79.0
    assert normalize_leetify(0.0) == 50.0


def test_deterministic_optimization_and_balance():
    players = _make_ten_players()
    r1 = optimize_teams(players, seed=42)
    r2 = optimize_teams(players, seed=42)

    assert r1.recommended.partition_key == r2.recommended.partition_key
    assert r1.recommended.team_a_ids == r2.recommended.team_a_ids
    assert r1.recommended.team_b_ids == r2.recommended.team_b_ids
    assert r1.recommended.strength_diff < 3.0
    assert len(set(r1.recommended.team_a_ids) | set(r1.recommended.team_b_ids)) == 10
    assert len(r1.alternatives) >= 2
    assert r1.explanation["map_policy_note"] == "Maps are random in actual play; no map is selected or predicted."


def test_locks_and_pair_constraints_respected():
    players = _make_ten_players()
    constraints = TeamConstraints(
        locked_a=frozenset({"p1", "p2"}),
        locked_b=frozenset({"p10"}),
        together_pairs=(("p3", "p4"),),
        opponent_pairs=(("p1", "p8"),),
    )
    res = optimize_teams(players, constraints=constraints, seed=99)
    team_a = set(res.recommended.team_a_ids)
    team_b = set(res.recommended.team_b_ids)
    assert {"p1", "p2"}.issubset(team_a)
    assert "p10" in team_b
    assert ("p3" in team_a) == ("p4" in team_a)
    assert "p8" in team_b


def test_unsatisfiable_constraints_raise_clear_error():
    players = _make_ten_players()
    bad = TeamConstraints(
        locked_a=frozenset({"p1", "p2"}),
        opponent_pairs=(("p1", "p2"),),
    )
    with pytest.raises(UnsatisfiableConstraintsError) as exc:
        optimize_teams(players, constraints=bad)
    assert "same team" in exc.value.message.lower()


def test_regeneration_avoids_repeated_splits_and_reports_exhaustion():
    players = _make_ten_players()
    # Lock 4 on A and 4 on B -> only 2 players free -> only 2 valid splits!
    tight = TeamConstraints(
        locked_a=frozenset({"p1", "p2", "p3", "p4"}),
        locked_b=frozenset({"p6", "p7", "p8", "p9"}),
    )
    first = optimize_teams(players, constraints=tight, seed=42)
    second = optimize_teams(
        players,
        constraints=tight,
        seed=42,
        exclude_partition_keys={first.recommended.partition_key},
    )
    assert first.recommended.partition_key != second.recommended.partition_key

    with pytest.raises(AllSplitsExhaustedError) as exc:
        optimize_teams(
            players,
            constraints=tight,
            seed=42,
            exclude_partition_keys={first.recommended.partition_key, second.recommended.partition_key},
        )
    assert exc.value.valid_count == 2
