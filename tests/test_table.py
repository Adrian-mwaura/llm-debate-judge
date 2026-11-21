"""Tests for table.py on synthetic per-pair records with known answers. No API calls, no download."""
import random

import pytest

from debate_judge import table
from debate_judge.full import VOTE_KS

WEAK_COST = 0.0006  # per pair, both orders


def make_records(n=300, seed=1, debate_high_acc=0.9, votes_acc=0.75, debate_cost=8.5 * WEAK_COST):
    rng = random.Random(seed)
    recs = []
    for i in range(n):
        pid = f"p{i:03d}"
        group = "knowledge" if i % 2 else "rmc"
        base = {"pair_id": pid, "category": "knowledge" if group == "knowledge" else "math", "group": group,
                "split": "gpt", "label": "A>B"}

        def rec(cond, ok, cost, outcome=None):
            recs.append({**base, "condition": cond, "correct": ok, "cost_match_usd": cost,
                         "outcome": outcome or ("both_right" if ok else "both_wrong")})

        weak_ok = rng.random() < 0.7
        rec("judge_none", weak_ok, WEAK_COST, None if weak_ok else "split")
        for k in VOTE_KS:
            rec(f"votes_k{k}", weak_ok if k == 1 else rng.random() < votes_acc, k * WEAK_COST)
        rec("debate_high", rng.random() < debate_high_acc, debate_cost)
        rec("debate_low", rng.random() < 0.8, 6.2 * WEAK_COST)
        rec("one_sided", rng.random() < 0.78, 4.9 * WEAK_COST)
        rec("judge_low", rng.random() < 0.88, 4.1 * WEAK_COST)
        rec("judge_high", rng.random() < 0.9, 5.4 * WEAK_COST)
    return recs


def test_condition_rows_cover_every_condition_in_order():
    conds = table.by_condition(make_records())
    ids = set.intersection(*(set(v) for v in conds.values()))
    rows = table.condition_rows(conds, ids)
    names = [r["condition"] for r in rows]
    assert names[0] == "judge_none" and names[-5:] == list(table.METHODS)
    assert "votes_k1" not in names  # k=1 is the judge alone; shown once
    r = next(r for r in rows if r["condition"] == "judge_none")
    assert r["n"] == 300 and r["ci_low"] < r["accuracy"] < r["ci_high"]
    assert r["cost_per_pair"] == pytest.approx(WEAK_COST)
    assert 0 < r["split_rate"] < 1


@pytest.mark.parametrize("method,expected", [
    ("debate_high", "votes_k9"), ("debate_low", "votes_k7"), ("one_sided", "votes_k5"),
    ("judge_low", "votes_k5"), ("judge_high", "votes_k7")])
def test_same_cost_baseline_follows_the_proposal_rule(method, expected):
    conds = table.by_condition(make_records())
    ids = set(conds["judge_none"])
    assert table.same_cost_votes(conds, method, ids) == expected


def test_debate_costing_more_than_nine_votes_uses_eleven():
    conds = table.by_condition(make_records(debate_cost=9.2 * WEAK_COST))
    assert table.same_cost_votes(conds, "debate_high", set(conds["judge_none"])) == "votes_k11"


def test_h1_is_primary_and_detects_a_clear_gain():
    conds = table.by_condition(make_records(debate_high_acc=0.95, votes_acc=0.7))
    comp = table.comparisons(conds, {r["pair_id"]: r for r in make_records()})
    h1 = comp["same_cost"]["debate_high"]
    assert h1["role"] == "H1 (primary)" and h1["baseline"] == "votes_k9"
    assert h1["comparison"].diff > 0.15 and h1["comparison"].b_better
    assert all(c["role"] == "exploratory" for m, c in comp["same_cost"].items() if m != "debate_high")
    assert "H2" in comp and set(comp["H3"]) == {"all", "knowledge", "rmc"}


def test_no_gain_when_debate_equals_votes():
    conds = table.by_condition(make_records(debate_high_acc=0.75, votes_acc=0.75, seed=3))
    h1 = table.comparisons(conds)["same_cost"]["debate_high"]["comparison"]
    assert h1.ci_low < 0 < h1.ci_high or abs(h1.diff) < 0.08


def test_restrict_limits_the_comparison_to_given_pairs():
    conds = table.by_condition(make_records())
    rest = {f"p{i:03d}" for i in range(100, 300)}
    comp = table.comparisons(conds, restrict=rest)
    assert comp["same_cost"]["debate_high"]["comparison"].n == 200


def test_markdown_and_plot(tmp_path):
    recs = make_records()
    conds = table.by_condition(recs)
    ids = set(conds["judge_none"])
    rows = table.condition_rows(conds, ids)
    comp = table.comparisons(conds, {r["pair_id"]: r for r in recs})
    md = table.markdown(rows, comp, comp, 300)
    assert "Table 1" in md and "H1 (primary)" in md and "outside the pilot" in md
    assert md.count("\n| ") >= len(rows) + len(comp["same_cost"])
    pytest.importorskip("matplotlib")
    table.plot(rows, tmp_path / "plot.png")
    assert (tmp_path / "plot.png").stat().st_size > 10_000
