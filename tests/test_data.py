"""Tests for data.py. Scoring and subset tests use synthetic pairs and need no download;
the tests marked `download` load the real JudgeBench (free, cached after the first run)."""
from collections import Counter

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
    assert s["rmc"]["split_first_slot"] == 1
    assert s["knowledge"]["accuracy"] == 1.0


def test_category():
    assert data.category("mmlu-pro-law") == "knowledge"
    assert data.category("livebench-reasoning") == "reasoning"
    assert data.category("livebench-math") == "math"
    assert data.category("livecodebench") == "coding"
    with pytest.raises(ValueError):
        data.category("gsm8k")


# ---------------------------------------------------------------- subsets (synthetic)


def synthetic_pairs():
    sizes = {"knowledge": 308, "reasoning": 149, "math": 90, "coding": 73}
    return [{"pair_id": f"{c}-{i:03d}", "category": c, "group": data.group(c)}
            for c, n in sizes.items() for i in range(n)]


def test_subsets_sizes_and_overlap():
    pairs = synthetic_pairs()
    dry, pilot, report = data.dry_run_pairs(pairs), data.pilot_pairs(pairs), data.report_pairs(pairs)
    ids = lambda ps: {p["pair_id"] for p in ps}  # noqa: E731
    assert (len(dry), len(pilot), len(report)) == (20, 200, 600)
    assert not ids(dry) & ids(report)            # dry-run pairs are never reported
    assert ids(pilot) <= ids(report)             # pilot calls are reused by the full run
    assert ids(dry) | ids(report) == ids(pairs)


def test_subsets_keep_the_category_mix():
    pairs = synthetic_pairs()
    for subset, n in ((data.pilot_pairs(pairs), 200), (data.dry_run_pairs(pairs), 20)):
        got = Counter(p["category"] for p in subset)
        for cat, total in (("knowledge", 308), ("reasoning", 149), ("math", 90), ("coding", 73)):
            assert abs(got[cat] - total * n / 620) <= 1.5, (cat, got)


def test_subsets_do_not_depend_on_load_order():
    pairs = synthetic_pairs()
    a = [p["pair_id"] for p in data.pilot_pairs(pairs)]
    b = [p["pair_id"] for p in data.pilot_pairs(list(reversed(pairs)))]
    assert a == b


# ---------------------------------------------------------------- the real dataset


@pytest.fixture(scope="module")
def judgebench():
    try:
        return data.load_judgebench()
    except Exception as e:  # offline
        pytest.skip(f"JudgeBench not available: {e}")


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
