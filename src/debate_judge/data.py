"""JudgeBench: loading, fixed pair subsets, and both-order scoring.

    from debate_judge.data import load_judgebench, dry_run_pairs, pilot_pairs, report_pairs, score_pair
    pairs = load_judgebench()            # all 620 pairs, as dicts, in a fixed order
    dry = dry_run_pairs(pairs)           # 20 pairs for prompt dry runs; never reported
    pilot = pilot_pairs(pairs)           # 200 pairs for the go/no-go pilot (disjoint from dry)
    full = report_pairs(pairs)           # the 600 pairs that go into reported results (pilot first)
    check = non_pilot_pairs(pairs)       # the 400 reported pairs outside the pilot
    s = score_pair(pair["label"], verdict.decisions)   # judge.PairVerdict.decisions

Data: ScalerLab/JudgeBench on Hugging Face, pinned to one revision so both of us get the same pairs.
Each pair has one correct and one wrong response; `label` is "A>B" (response_A is correct) or "B>A".
We add `split` ("gpt" or "claude", the model that wrote the responses), `category`
(knowledge, reasoning, math, coding) and `group` (knowledge, or rmc = reasoning, math and coding).

Scoring follows JudgeBench's rule: a pair is judged in both answer orders, and it is correct only if
the two decisions together favour the labelled response (net votes > 0; a tie or a missing verdict
counts as 0). Decisions must be in the pair's ORIGINAL labels, as judge.py returns them:
do not flip the second decision, unlike JudgeBench's own published outputs.
"""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Iterable, Mapping, Sequence

DATASET = "ScalerLab/JudgeBench"
REVISION = "57dd5e0b9817d07f05ec8f45a91b2ce1e310e308"  # checked 2026-11-17: 350 gpt + 270 claude pairs
SPLITS = ("gpt", "claude")
LABELS = ("A>B", "B>A")
FLIP = {"A>B": "B>A", "B>A": "A>B"}
CATEGORIES = ("knowledge", "reasoning", "math", "coding")

# Fixed subsets: change the seed or sizes only before any results exist.
SUBSET_SEED = 20261117
DRY_RUN_SIZE = 20
PILOT_SIZE = 200


def category(source: str) -> str:
    """JudgeBench source -> one of CATEGORIES."""
    if source.startswith("mmlu-pro"):
        return "knowledge"
    if source.startswith("livebench-reasoning"):
        return "reasoning"
    if source.startswith("livebench-math"):
        return "math"
    if source.startswith("livecodebench"):
        return "coding"
    raise ValueError(f"unknown JudgeBench source: {source!r}")


def group(cat: str) -> str:
    """The two halves of hypothesis H3: knowledge against reasoning, math and coding."""
    return "knowledge" if cat == "knowledge" else "rmc"


def _with_fields(row: Mapping[str, Any], split: str) -> dict[str, Any]:
    pair = dict(row)
    if pair["label"] not in LABELS:
        raise ValueError(f"pair {pair['pair_id']}: unexpected label {pair['label']!r}")
    pair["split"] = split
    pair["category"] = category(pair["source"])
    pair["group"] = group(pair["category"])
    return pair


def load_judgebench(splits: Sequence[str] = SPLITS, revision: str = REVISION) -> list[dict[str, Any]]:
    """All pairs from the given splits, in the dataset's own order (gpt first, then claude).

    Downloads once into the Hugging Face cache (~/.cache/huggingface); no API cost.
    """
    from datasets import load_dataset

    ds = load_dataset(DATASET, revision=revision)
    pairs = [_with_fields(row, split) for split in splits for row in ds[split]]
    ids = [p["pair_id"] for p in pairs]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate pair_id across splits")
    return pairs


# ---------------------------------------------------------------- fixed subsets


def _by_category(p: Mapping[str, Any]) -> str:
    return p["category"]


def _by_category_and_split(p: Mapping[str, Any]) -> tuple[str, str]:
    return p["category"], p["split"]


def _stratified_order(
    pairs: Sequence[Mapping[str, Any]],
    seed: int,
    stratum: Callable[[Mapping[str, Any]], Any] = _by_category,
) -> list[Mapping[str, Any]]:
    """All pairs in a seeded order where every prefix keeps the mix of strata of the whole set.

    Pairs are shuffled within each stratum (by default the category), then interleaved by largest
    remaining share, so the first n pairs have about the same proportions as the whole set.
    """
    rng = random.Random(seed)
    by_stratum: dict[Any, list] = {}
    for p in sorted(pairs, key=lambda p: p["pair_id"]):  # independent of load order
        by_stratum.setdefault(stratum(p), []).append(p)
    for s in sorted(by_stratum):
        rng.shuffle(by_stratum[s])
    total = len(pairs)
    size = {s: len(items) for s, items in by_stratum.items()}
    taken = Counter()
    order = []
    for i in range(total):
        # the stratum furthest behind its share of the first i+1 pairs (ties: sorted order)
        left = [s for s in sorted(by_stratum) if by_stratum[s]]
        s = max(left, key=lambda s: size[s] * (i + 1) / total - taken[s])
        order.append(by_stratum[s].pop())
        taken[s] += 1
    return order


@lru_cache(maxsize=8)
def _subset_ids(rows: tuple[tuple[Any, str, str], ...], seed: int) -> tuple[tuple, tuple, tuple]:
    """(dry-run ids, pilot ids, report ids) for the pairs given as (pair_id, category, split) rows.

    The dry-run pairs are the first DRY_RUN_SIZE of a category-stratified order. That is the
    selection the 2026-11-18 dry run used, kept so those pairs stay out of reported results.
    The remaining pairs are then ordered by category AND split (the model that wrote the responses),
    and the pilot is the first PILOT_SIZE of that order, so it mirrors the full set on both.
    Cached, so the three subset functions share one computed order.
    """
    records = [{"pair_id": i, "category": c, "split": s} for i, c, s in rows]
    dry_ids = tuple(p["pair_id"] for p in _stratified_order(records, seed, _by_category)[:DRY_RUN_SIZE])
    rest = [p for p in records if p["pair_id"] not in set(dry_ids)]
    report_ids = tuple(p["pair_id"] for p in _stratified_order(rest, seed, _by_category_and_split))
    return dry_ids, report_ids[:PILOT_SIZE], report_ids


def _subsets(pairs: Sequence[Mapping[str, Any]], seed: int = SUBSET_SEED) -> dict[str, list]:
    rows = tuple(sorted((p["pair_id"], p["category"], p["split"]) for p in pairs))
    dry, pilot, report = _subset_ids(rows, seed)
    by_id = {p["pair_id"]: p for p in pairs}
    return {
        "dry_run": [by_id[i] for i in dry],
        "pilot": [by_id[i] for i in pilot],
        "report": [by_id[i] for i in report],
    }


def dry_run_pairs(pairs: Sequence[Mapping[str, Any]]) -> list:
    """20 pairs for prompt dry runs. They are never part of reported results."""
    return _subsets(pairs)["dry_run"]


def pilot_pairs(pairs: Sequence[Mapping[str, Any]]) -> list:
    """200 pairs for the go/no-go pilot, with the category and response-author mix of the full set.
    They are a subset of report_pairs(), so the full runs reuse the pilot's cached calls."""
    return _subsets(pairs)["pilot"]


def report_pairs(pairs: Sequence[Mapping[str, Any]]) -> list:
    """Every pair except the dry-run pairs: the set all reported results use (600 of 620).
    The first 200 are the pilot pairs."""
    return _subsets(pairs)["report"]


def non_pilot_pairs(pairs: Sequence[Mapping[str, Any]]) -> list:
    """The 400 reported pairs outside the pilot. The pilot decided go/no-go, so the report also shows
    results on these alone as a check."""
    return _subsets(pairs)["report"][PILOT_SIZE:]


# ---------------------------------------------------------------- scoring


@dataclass
class PairScore:
    correct: bool        # JudgeBench's rule: net votes for the labelled response > 0
    outcome: str         # both_right, both_wrong, split, partial_right, partial_wrong, no_verdict
    first_slot: bool | None  # for a split: True if the judge chose the first-shown response both times


def score_pair(label: str, decisions: Sequence[str | None]) -> PairScore:
    """Score one pair from its label and its two decisions [original order, swapped order],
    both in the pair's original labels ("A>B" or "B>A"; None if missing or incomplete)."""
    if label not in LABELS:
        raise ValueError(f"label must be one of {LABELS}, got {label!r}")
    if len(decisions) != 2:
        raise ValueError(f"expected 2 decisions (both orders), got {len(decisions)}")
    for d in decisions:
        if d is not None and d not in LABELS:
            raise ValueError(f"decision must be 'A>B', 'B>A' or None, got {d!r}")
    right = sum(d == label for d in decisions)
    wrong = sum(d == FLIP[label] for d in decisions)
    if right == 2:
        outcome = "both_right"
    elif wrong == 2:
        outcome = "both_wrong"
    elif right == 1 and wrong == 1:
        outcome = "split"
    elif right == 1:
        outcome = "partial_right"
    elif wrong == 1:
        outcome = "partial_wrong"
    else:
        outcome = "no_verdict"
    # In a split the judge picked different original responses in the two orders, so it picked the
    # same shown position. In the original order the first-shown response is response_A.
    first_slot = (decisions[0] == "A>B") if outcome == "split" else None
    return PairScore(correct=right - wrong > 0, outcome=outcome, first_slot=first_slot)


def majority(decisions: Iterable[str | None]) -> str | None:
    """Majority of several decisions for ONE order (the vote baseline). Missing votes are skipped;
    a tie, or no valid votes, gives None. Use an odd number of votes to make ties rare."""
    counts = Counter(d for d in decisions if d is not None)
    if not counts:
        return None
    (top, n), *rest = counts.most_common()
    if rest and rest[0][1] == n:
        return None
    return top


def summarize(scored: Iterable[tuple[Mapping[str, Any], PairScore]]) -> dict[str, Any]:
    """Accuracy and outcome counts: "all", one key per category ("knowledge", "math", ...) and
    one per group ("group:knowledge", "group:rmc").

    `scored` is (pair, PairScore) for each pair. Confidence intervals and paired tests are in stats.py.
    """
    def empty():
        return {"n": 0, "correct": 0, "outcomes": Counter(), "split_first_slot": 0}

    out = {"all": empty()}
    for pair, s in scored:
        # Groups get their own prefix: the knowledge category and the knowledge group share a name,
        # and one bucket for both would count every knowledge pair twice.
        for key in ("all", pair["category"], f"group:{pair['group']}"):
            b = out.setdefault(key, empty())
            b["n"] += 1
            b["correct"] += s.correct
            b["outcomes"][s.outcome] += 1
            b["split_first_slot"] += bool(s.first_slot)
    for b in out.values():
        b["accuracy"] = b["correct"] / b["n"] if b["n"] else float("nan")
        b["outcomes"] = dict(b["outcomes"])
    return out
