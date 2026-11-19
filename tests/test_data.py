"""Tests for data.py. Scoring and subset tests use synthetic pairs and need no download;
the tests marked `download` load the real JudgeBench (free, cached after the first run)."""
import json
import socket
from collections import Counter
from pathlib import Path

import pytest

from debate_judge import data
from debate_judge.data import majority, score_pair, summarize

# ---------------------------------------------------------------- scoring


@pytest.mark.parametrize("label,decisions,correct,outcome,first_slot", [
    ("A>B", ["A>B", "A>B"], True, "both_right", None),
    ("A>B", ["B>A", "B>A"], False, "both_wrong", None),
    ("B>A", ["B>A", "B>A"], True, "both_right", None),
    # split: different original responses, i.e. the same shown position both times
    ("A>B", ["A>B", "B>A"], False, "split", True),   # first slot: A shown first, then B shown first
    ("A>B", ["B>A", "A>B"], False, "split", False),  # second slot both times
    ("B>A", ["A>B", "B>A"], False, "split", True),
    # one verdict missing: JudgeBench counts the other one alone
    ("A>B", ["A>B", None], True, "partial_right", None),
    ("A>B", [None, "B>A"], False, "partial_wrong", None),
    ("A>B", [None, None], False, "no_verdict", None),
])
def test_score_pair(label, decisions, correct, outcome, first_slot):
    s = score_pair(label, decisions)
    assert (s.correct, s.outcome, s.first_slot) == (correct, outcome, first_slot)


def test_score_pair_does_not_flip_the_second_decision():
    # judge.py returns both decisions in original labels; a consistent judge that always
    # prefers response_A gives ["A>B", "A>B"], which must be both_right for label A>B.
    assert score_pair("A>B", ["A>B", "A>B"]).outcome == "both_right"


@pytest.mark.parametrize("label,decisions", [
    ("A=B", ["A>B", "A>B"]),
    ("A>B", ["A>B"]),
    ("A>B", ["A>B", "A"]),
])
def test_score_pair_rejects_bad_input(label, decisions):
    with pytest.raises(ValueError):
        score_pair(label, decisions)


@pytest.mark.parametrize("votes,expected", [
    (["A>B", "A>B", "B>A"], "A>B"),
    (["B>A"], "B>A"),
    (["A>B", "B>A"], None),            # tie
    (["A>B", None, None], "A>B"),      # missing votes skipped
    ([None, None], None),
    ([], None),
])
def test_majority(votes, expected):
    assert majority(votes) == expected


def test_summarize_by_category_and_group():
    pairs = [
        {"category": "knowledge", "group": "knowledge"},
        {"category": "math", "group": "rmc"},
        {"category": "math", "group": "rmc"},
    ]
    scores = [score_pair("A>B", ["A>B", "A>B"]), score_pair("A>B", ["A>B", "B>A"]),
              score_pair("B>A", ["B>A", "B>A"])]
    s = summarize(zip(pairs, scores))
    assert s["all"]["n"] == 3 and s["all"]["correct"] == 2
    assert s["all"]["accuracy"] == pytest.approx(2 / 3)
    assert s["math"]["outcomes"] == {"split": 1, "both_right": 1}
    assert s["group:rmc"]["split_first_slot"] == 1
    assert s["knowledge"]["accuracy"] == 1.0


def test_summarize_counts_knowledge_pairs_once():
    # The knowledge category and the knowledge group share a name; each must count the pair once.
    pairs = [{"category": "knowledge", "group": "knowledge"}, {"category": "math", "group": "rmc"}]
    scores = [score_pair("A>B", ["A>B", "A>B"]), score_pair("A>B", ["B>A", "B>A"])]
    s = summarize(zip(pairs, scores))
    assert (s["knowledge"]["n"], s["knowledge"]["correct"]) == (1, 1)
    assert (s["group:knowledge"]["n"], s["group:knowledge"]["correct"]) == (1, 1)
    assert (s["group:rmc"]["n"], s["group:rmc"]["correct"]) == (1, 0)
    assert s["all"]["n"] == 2


def test_category():
    assert data.category("mmlu-pro-law") == "knowledge"
    assert data.category("livebench-reasoning") == "reasoning"
    assert data.category("livebench-math") == "math"
    assert data.category("livecodebench") == "coding"
    with pytest.raises(ValueError):
        data.category("gsm8k")


# ---------------------------------------------------------------- subsets (synthetic)


SIZES = {"knowledge": 308, "reasoning": 149, "math": 90, "coding": 73}


def synthetic_pairs():
    # Like JudgeBench: 350 gpt and 270 claude pairs, the splits spread unevenly across categories.
    pairs = []
    for c, n in SIZES.items():
        for i in range(n):
            pairs.append({"pair_id": f"{c}-{i:03d}", "category": c, "group": data.group(c)})
    for i, p in enumerate(pairs):
        p["split"] = "gpt" if (i * 7) % 620 < 350 else "claude"
    return pairs


def ids(ps):
    return [p["pair_id"] for p in ps]


def test_subsets_sizes_and_overlap():
    pairs = synthetic_pairs()
    dry, pilot, report = data.dry_run_pairs(pairs), data.pilot_pairs(pairs), data.report_pairs(pairs)
    rest = data.non_pilot_pairs(pairs)
    assert (len(dry), len(pilot), len(report), len(rest)) == (20, 200, 600, 400)
    assert not set(ids(dry)) & set(ids(report))      # dry-run pairs are never reported
    assert set(ids(pilot)) <= set(ids(report))       # pilot calls are reused by the full run
    assert set(ids(dry)) | set(ids(report)) == set(ids(pairs))
    assert not set(ids(pilot)) & set(ids(rest))      # the 400-pair check excludes the pilot
    assert set(ids(pilot)) | set(ids(rest)) == set(ids(report))


def test_subsets_keep_the_category_mix():
    pairs = synthetic_pairs()
    for subset, n in ((data.pilot_pairs(pairs), 200), (data.dry_run_pairs(pairs), 20)):
        got = Counter(p["category"] for p in subset)
        for cat, total in SIZES.items():
            assert abs(got[cat] - total * n / 620) <= 1.5, (cat, got)


def test_pilot_keeps_the_response_author_mix():
    pairs = synthetic_pairs()
    rest = [p for p in pairs if p["pair_id"] not in set(ids(data.dry_run_pairs(pairs)))]
    pilot = data.pilot_pairs(pairs)
    for key in (lambda p: p["split"], lambda p: (p["category"], p["split"])):
        whole, got = Counter(map(key, rest)), Counter(map(key, pilot))
        for cell, total in whole.items():
            assert abs(got[cell] - total * 200 / len(rest)) <= 1.5, (cell, got)


def test_dry_run_pairs_are_the_category_only_selection():
    # The dry run on 2026-11-18 used the first 20 pairs of the category-stratified order.
    # Balancing the pilot by author must not change them, or a dry-run pair could end up reported.
    pairs = synthetic_pairs()
    assert ids(data.dry_run_pairs(pairs)) == ids(data._stratified_order(pairs, data.SUBSET_SEED)[:20])


def test_subsets_do_not_depend_on_load_order():
    pairs = synthetic_pairs()
    for fn in (data.dry_run_pairs, data.pilot_pairs, data.report_pairs):
        assert ids(fn(pairs)) == ids(fn(list(reversed(pairs))))


# ---------------------------------------------------------------- the real dataset


def _hub_reachable() -> bool:
    try:
        socket.create_connection(("huggingface.co", 443), timeout=5).close()
        return True
    except OSError:
        return False


@pytest.fixture(scope="module")
def judgebench():
    # Skip only when the data cannot be had: `datasets` not installed, or offline with nothing cached.
    # Anything else (a wrong revision, a changed schema, a bug) must fail, not skip.
    pytest.importorskip("datasets", reason="the `datasets` package is not installed (pip install -r requirements.txt)")
    try:
        return data.load_judgebench()
    except Exception as e:
        if not _hub_reachable():
            pytest.skip(f"Hugging Face is unreachable and JudgeBench is not cached: {e}")
        raise


@pytest.mark.download
def test_real_dataset_shape(judgebench):
    assert len(judgebench) == 620
    assert Counter(p["split"] for p in judgebench) == {"gpt": 350, "claude": 270}
    assert Counter(p["category"] for p in judgebench) == {"knowledge": 308, "reasoning": 149, "math": 90, "coding": 73}
    assert Counter(p["group"] for p in judgebench) == {"knowledge": 308, "rmc": 312}
    for p in judgebench:
        assert p["label"] in ("A>B", "B>A")
        assert p["question"] and p["response_A"] and p["response_B"]


@pytest.mark.download
def test_real_subsets_are_fixed(judgebench):
    dry, pilot = data.dry_run_pairs(judgebench), data.pilot_pairs(judgebench)
    assert len(dry) == 20 and len(pilot) == 200
    # Pin the first ids so an accidental change to the selection is caught.
    assert [p["pair_id"] for p in dry[:3]] == PINNED_DRY_RUN_FIRST_IDS


PINNED_DRY_RUN_FIRST_IDS = [  # from the real run on 2026-11-17, REVISION 57dd5e0
    "c67cf264-33f9-5730-aeea-a7364756a96b",
    "29da4abd-50bc-5254-bfca-dfbbf7b48daf",
    "6071bc26-275c-5873-aa87-bca1593c1350",
]


@pytest.mark.download
def test_real_dry_run_pairs_match_the_dry_run_logs(judgebench):
    # The committed dry-run logs say which 20 pairs were dry-run; they must stay out of reported results.
    log = Path(__file__).resolve().parents[1] / "logs" / "calls" / "dry_judge_none.jsonl"
    logged = {json.loads(line)["meta"]["pair_id"] for line in log.read_text(encoding="utf-8").splitlines() if line}
    assert set(ids(data.dry_run_pairs(judgebench))) == logged


@pytest.mark.download
def test_real_pilot_keeps_category_and_author_mix(judgebench):
    report, pilot = data.report_pairs(judgebench), data.pilot_pairs(judgebench)
    for key in (lambda p: p["category"], lambda p: p["split"]):
        whole, got = Counter(map(key, report)), Counter(map(key, pilot))
        for cell, total in whole.items():
            assert abs(got[cell] - total * 200 / 600) <= 1.5, (cell, got)
