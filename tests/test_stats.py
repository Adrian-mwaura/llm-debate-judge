"""Tests for stats.py, checked against SciPy and against the numbers in the research report."""
import random

import pytest
from scipy.stats import binomtest

from debate_judge import stats


# ---------------------------------------------------------------- Wilson


@pytest.mark.parametrize("k,n", [(403, 620), (415, 500), (0, 20), (20, 20), (7, 13), (100, 200)])
def test_wilson_matches_scipy(k, n):
    ci = binomtest(k, n).proportion_ci(confidence_level=0.95, method="wilson")
    low, high = stats.wilson_interval(k, n)
    assert low == pytest.approx(ci.low, abs=1e-9) and high == pytest.approx(ci.high, abs=1e-9)


def test_interval_widths_match_research_report():
    # Report: about ±3.8 points at 65% on 620 pairs, ±3.3 at 83% on 500, ±2.3 at 83% on 1,000.
    for k, n, half in ((403, 620, 0.038), (415, 500, 0.033), (830, 1000, 0.023)):
        low, high = stats.wilson_interval(k, n)
        assert (high - low) / 2 == pytest.approx(half, abs=0.0015)


def test_accuracy_ci_from_dict_and_list():
    a = stats.accuracy_ci({"p1": True, "p2": False, "p3": True, "p4": True})
    b = stats.accuracy_ci([True, False, True, True])
    assert (a.n, a.correct, a.accuracy) == (4, 3, 0.75)
    assert (a.ci_low, a.ci_high) == (b.ci_low, b.ci_high)
    assert "75.0" in str(a)


def test_wilson_rejects_bad_input():
    with pytest.raises(ValueError):
        stats.wilson_interval(1, 0)
    with pytest.raises(ValueError):
        stats.wilson_interval(5, 4)


# ---------------------------------------------------------------- McNemar


@pytest.mark.parametrize("only_a,only_b", [(10, 25), (3, 3), (0, 7), (40, 18), (0, 0), (1, 0)])
def test_mcnemar_matches_scipy(only_a, only_b):
    expected = 1.0 if only_a + only_b == 0 else binomtest(only_b, only_a + only_b, 0.5).pvalue
    assert stats.mcnemar_exact(only_a, only_b) == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------- paired comparison


def make(n, acc_a, acc_b, agree, seed=1):
    """Synthetic paired results: A and B agree on a fraction `agree` of pairs."""
    rng = random.Random(seed)
    a, b = {}, {}
    for i in range(n):
        x = rng.random() < acc_a
        y = x if rng.random() < agree else rng.random() < acc_b
        a[f"p{i}"], b[f"p{i}"] = x, y
    return a, b


def test_paired_counts_and_direction():
    a = {"p1": True, "p2": True, "p3": False, "p4": False, "p5": False}
    b = {"p1": True, "p2": False, "p3": True, "p4": True, "p5": False}
    d = stats.paired_comparison(a, b)
    assert (d.n, d.only_a, d.only_b) == (5, 1, 2)
    assert d.acc_a == pytest.approx(0.4) and d.acc_b == pytest.approx(0.6)
    assert d.diff == pytest.approx(0.2)
    assert d.ci_low < d.diff < d.ci_high


def test_paired_uses_only_shared_pairs():
    a = {"p1": True, "p2": False, "extra_a": True}
    b = {"p1": True, "p2": True, "extra_b": False}
    d = stats.paired_comparison(a, b)
    assert d.n == 2 and d.only_b == 1
    with pytest.raises(ValueError):
        stats.paired_comparison({"x": True}, {"y": True})


def test_identical_conditions_give_zero_difference():
    a, _ = make(200, 0.6, 0.6, 1.0)
    d = stats.paired_comparison(a, dict(a))
    assert d.diff == 0 and d.p_value == 1.0
    assert d.ci_low <= 0 <= d.ci_high and not d.b_better


def test_clear_improvement_is_detected():
    a, b = make(600, 0.55, 0.80, 0.6)
    d = stats.paired_comparison(a, b)
    assert d.diff > 0.1 and d.b_better and d.p_value < 0.001


def test_newcombe_agrees_with_bootstrap():
    for seed in range(5):
        a, b = make(200, 0.6, 0.7, 0.7, seed=seed)
        d = stats.paired_comparison(a, b)
        lo, hi = stats.paired_bootstrap_interval(a, b, resamples=20000, seed=seed)
        assert d.ci_low == pytest.approx(lo, abs=0.02) and d.ci_high == pytest.approx(hi, abs=0.02)


def test_newcombe_coverage_is_about_95_percent():
    # Simulate paired outcomes with a known true difference and count how often the interval covers it.
    rng = random.Random(7)
    true_diff = 0.08
    p = {"both": 0.50, "only_a": 0.08, "only_b": 0.16, "neither": 0.26}  # p_b - p_a = 0.08
    cover, trials, n = 0, 1500, 200
    for _ in range(trials):
        cells = {"both": 0, "only_a": 0, "only_b": 0, "neither": 0}
        for _ in range(n):
            r, acc = rng.random(), 0.0
            for cell, pr in p.items():
                acc += pr
                if r < acc:
                    cells[cell] += 1
                    break
            else:
                cells["neither"] += 1
        lo, hi = stats.newcombe_paired_interval(cells["both"], cells["only_a"], cells["only_b"], cells["neither"])
        cover += lo <= true_diff <= hi
    assert 0.93 <= cover / trials <= 0.975


def test_newcombe_edge_cases_stay_in_range():
    for cells in [(10, 0, 0, 0), (0, 0, 0, 10), (0, 10, 0, 0), (0, 0, 10, 0), (5, 0, 5, 0), (3, 1, 1, 3)]:
        lo, hi = stats.newcombe_paired_interval(*cells)
        assert -1 <= lo <= hi <= 1


# ---------------------------------------------------------------- groups


def test_by_group_and_paired_by_group():
    pairs = [{"pair_id": f"p{i}", "group": "knowledge" if i < 4 else "rmc"} for i in range(8)]
    a = {f"p{i}": i % 2 == 0 for i in range(8)}
    b = {f"p{i}": True for i in range(8)}
    g = stats.by_group(a, pairs)
    assert set(g) == {"all", "knowledge", "rmc"} and g["all"].n == 8 and g["rmc"].correct == 2
    pg = stats.paired_by_group(a, b, pairs)
    assert pg["all"].only_b == 4 and pg["knowledge"].n == 4 and pg["rmc"].diff == pytest.approx(0.5)
