"""Confidence intervals and paired tests for per-pair correctness.

Every condition is scored on the same pairs, so comparisons are paired:

    from debate_judge.stats import accuracy_ci, paired_comparison
    a = accuracy_ci(correct_by_pair)                    # {pair_id: bool} for one condition
    d = paired_comparison(weak_judge, thinking_judge)   # thinking minus weak, on the shared pairs
    d.diff, d.ci_low, d.ci_high, d.p_value

Methods (all 95% by default):
- accuracy: Wilson score interval. It behaves well near 0 and 1 and for small n, unlike the plain normal interval.
- paired difference in accuracy (B minus A): Newcombe's interval for paired proportions (method 10, built from
  Wilson intervals; Newcombe 1998, Statistics in Medicine 17:2635). It needs no random numbers, so it is reproducible.
- paired test: McNemar's exact test (two-sided binomial test on the pairs where the two conditions disagree).
- a paired bootstrap interval is available as a cross-check (seeded).

Go/no-go rule from the proposal: continue with question 6 only if the thinking judge beats the weak judge with a
paired 95% interval above zero, i.e. paired_comparison(weak, thinking).ci_low > 0.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

Z95 = 1.959963984540054


@dataclass
class AccuracyCI:
    n: int
    correct: int
    accuracy: float
    ci_low: float
    ci_high: float

    def __str__(self) -> str:
        return f"{100 * self.accuracy:.1f} [{100 * self.ci_low:.1f}, {100 * self.ci_high:.1f}] (n={self.n})"


@dataclass
class PairedComparison:
    n: int                 # pairs scored in both conditions
    acc_a: float
    acc_b: float
    diff: float            # acc_b - acc_a
    ci_low: float          # Newcombe interval for diff
    ci_high: float
    only_a: int            # pairs A got right and B got wrong
    only_b: int            # pairs B got right and A got wrong
    p_value: float         # McNemar exact, two-sided

    @property
    def b_better(self) -> bool:
        """B is better than A with the interval above zero (the go/no-go rule)."""
        return self.ci_low > 0

    def __str__(self) -> str:
        return (f"{100 * self.diff:+.1f} points [{100 * self.ci_low:+.1f}, {100 * self.ci_high:+.1f}], "
                f"McNemar p={self.p_value:.3g} (n={self.n}, only A right {self.only_a}, only B right {self.only_b})")


# ---------------------------------------------------------------- single proportion


def wilson_interval(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for k successes out of n."""
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= k <= n:
        raise ValueError("k must be between 0 and n")
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def accuracy_ci(correct: Mapping[object, bool] | Sequence[bool], z: float = Z95) -> AccuracyCI:
    """Accuracy and its Wilson interval. `correct` is {pair_id: bool} or a list of bools."""
    values = list(correct.values()) if isinstance(correct, Mapping) else list(correct)
    n, k = len(values), sum(bool(v) for v in values)
    low, high = wilson_interval(k, n, z)
    return AccuracyCI(n=n, correct=k, accuracy=k / n, ci_low=low, ci_high=high)


# ---------------------------------------------------------------- paired comparison


def _align(a: Mapping[object, bool], b: Mapping[object, bool]) -> list[tuple[bool, bool]]:
    shared = sorted(set(a) & set(b), key=str)
    if not shared:
        raise ValueError("the two conditions share no pairs")
    return [(bool(a[k]), bool(b[k])) for k in shared]


def _counts(rows: Sequence[tuple[bool, bool]]) -> tuple[int, int, int, int]:
    """(both right, only A right, only B right, both wrong)."""
    both = sum(x and y for x, y in rows)
    only_a = sum(x and not y for x, y in rows)
    only_b = sum(y and not x for x, y in rows)
    return both, only_a, only_b, len(rows) - both - only_a - only_b


def newcombe_paired_interval(both: int, only_a: int, only_b: int, neither: int,
                             z: float = Z95) -> tuple[float, float]:
    """Newcombe (1998) method 10: interval for p_B - p_A from paired counts."""
    n = both + only_a + only_b + neither
    p_a, p_b = (both + only_a) / n, (both + only_b) / n
    l_a, u_a = wilson_interval(both + only_a, n, z)
    l_b, u_b = wilson_interval(both + only_b, n, z)
    d = p_b - p_a

    # correlation term phi, set to 0 when a margin is zero (Newcombe's convention)
    margins = (both + only_a) * (only_b + neither) * (both + only_b) * (only_a + neither)
    if margins == 0:
        phi = 0.0
    else:
        num = both * neither - only_a * only_b
        # Newcombe's adjustment: subtract n/2 if above n/2, set to 0 if between 0 and n/2, keep if negative
        if num > n / 2:
            num -= n / 2
        elif num >= 0:
            num = 0.0
        phi = num / math.sqrt(margins)

    dl2 = (p_b - l_b) ** 2 - 2 * phi * (p_b - l_b) * (u_a - p_a) + (u_a - p_a) ** 2
    du2 = (u_b - p_b) ** 2 - 2 * phi * (u_b - p_b) * (p_a - l_a) + (p_a - l_a) ** 2
    return max(-1.0, d - math.sqrt(max(dl2, 0.0))), min(1.0, d + math.sqrt(max(du2, 0.0)))


def mcnemar_exact(only_a: int, only_b: int) -> float:
    """Two-sided exact McNemar p-value: binomial test of only_b against only_a + only_b at p = 1/2."""
    m = only_a + only_b
    if m == 0:
        return 1.0
    k = min(only_a, only_b)
    tail = sum(math.comb(m, i) for i in range(k + 1)) / 2 ** m
    return min(1.0, 2 * tail)


def paired_comparison(a: Mapping[object, bool], b: Mapping[object, bool], z: float = Z95) -> PairedComparison:
    """Compare condition B with condition A on the pairs both were scored on (B minus A)."""
    rows = _align(a, b)
    both, only_a, only_b, neither = _counts(rows)
    n = len(rows)
    low, high = newcombe_paired_interval(both, only_a, only_b, neither, z)
    return PairedComparison(
        n=n,
        acc_a=(both + only_a) / n,
        acc_b=(both + only_b) / n,
        diff=(only_b - only_a) / n,
        ci_low=low,
        ci_high=high,
        only_a=only_a,
        only_b=only_b,
        p_value=mcnemar_exact(only_a, only_b),
    )


def paired_bootstrap_interval(a: Mapping[object, bool], b: Mapping[object, bool], *, resamples: int = 10000,
                              seed: int = 0, level: float = 0.95) -> tuple[float, float]:
    """Percentile bootstrap interval for acc_b - acc_a, resampling pairs. A cross-check for Newcombe."""
    import numpy as np

    rows = np.array(_align(a, b), dtype=float)
    diffs = rows[:, 1] - rows[:, 0]
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diffs), size=(resamples, len(diffs)))
    means = diffs[idx].mean(axis=1)
    alpha = (1 - level) / 2
    return float(np.quantile(means, alpha)), float(np.quantile(means, 1 - alpha))


# ---------------------------------------------------------------- by subgroup


def by_group(correct: Mapping[object, bool], pairs: Sequence[Mapping[str, object]], key: str = "group",
             z: float = Z95) -> dict[str, AccuracyCI]:
    """Accuracy with intervals per value of `key` ("group" or "category"), plus "all"."""
    label = {p["pair_id"]: p[key] for p in pairs}
    buckets: dict[str, dict] = {"all": {}}
    for pid, ok in correct.items():
        buckets["all"][pid] = ok
        buckets.setdefault(str(label[pid]), {})[pid] = ok
    return {name: accuracy_ci(vals, z) for name, vals in buckets.items()}


def paired_by_group(a: Mapping[object, bool], b: Mapping[object, bool], pairs: Sequence[Mapping[str, object]],
                    key: str = "group", z: float = Z95) -> dict[str, PairedComparison]:
    """paired_comparison per value of `key`, plus "all". Used for hypothesis H3."""
    label = {p["pair_id"]: str(p[key]) for p in pairs}
    out = {"all": paired_comparison(a, b, z)}
    for g in sorted(set(label[k] for k in set(a) & set(b))):
        ids = [k for k in set(a) & set(b) if label[k] == g]
        out[g] = paired_comparison({k: a[k] for k in ids}, {k: b[k] for k in ids}, z)
    return out
