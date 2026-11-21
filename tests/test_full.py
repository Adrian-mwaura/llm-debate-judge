"""The full run with a fake chat(): no API calls, no download."""
import json
from types import SimpleNamespace

import pytest

from debate_judge import data, full

LABELS = {}
COST = 1e-4  # cost_match per call


class FakeChat:
    """Weak judge right on most pairs but varies by sample; thinking judge always right; debaters defend."""

    def __init__(self):
        self.calls = []

    def __call__(self, messages, *, thinking, max_tokens, run, **kw):
        self.calls.append({"thinking": thinking, "run": run, **kw})
        meta = kw.get("meta", {})
        role = meta.get("role")
        if role == "debater":
            text = "My response is correct; the other response is wrong."
        elif role == "concession_check":
            text = '{"verdict": "defends"}'
        else:
            pid, sample = meta["pair_id"], kw.get("sample", 0)
            truth = LABELS[pid]
            if thinking != "none" or meta.get("n_arguments", 0) == 2:
                good = True
            else:
                good = (hash((pid, sample)) % 10) < 7
            winner = truth if good else ("B" if truth == "A" else "A")
            shown = winner if meta["order"] == "AB" else ("B" if winner == "A" else "A")
            text = json.dumps({"reasoning": "x", "winner": shown})
        return SimpleNamespace(text=text, complete=True, cost_usd=COST / 2, cost_match_usd=COST)


def make_pairs(n):
    pairs = []
    for i in range(n):
        cat = data.CATEGORIES[i % 4]
        label = "A>B" if i % 3 else "B>A"
        pid = f"full-{i:03d}"
        LABELS[pid] = label[0]
        pairs.append({"pair_id": pid, "question": f"Q{i}", "response_A": "ra", "response_B": "rb", "label": label,
                      "category": cat, "group": data.group(cat), "split": "gpt" if i % 2 else "claude"})
    return pairs


def by_cond(records):
    out = {}
    for cond, recs in records.items():
        out[cond] = {r["pair_id"]: r for r in recs}
    return out


def test_all_conditions_end_to_end(tmp_path):
    pairs = make_pairs(24)
    fake = FakeChat()
    done = full.run_conditions(pairs, full.GROUPS["all"], out_dir=tmp_path, chat_fn=fake, workers=4,
                               progress=lambda s: None)
    expected = {"judge_none", "judge_low", "judge_high", "debate_high", "debate_low", "one_sided"} | \
               {f"votes_k{k}" for k in full.VOTE_KS}
    assert set(done) == expected
    assert all(len(recs) == 24 for recs in done.values())

    c = by_cond(done)
    # vote k=1 is the judge alone: same decisions
    for pid in c["judge_none"]:
        assert c["votes_k1"][pid]["decisions"] == c["judge_none"][pid]["decisions"]
    # cost matching: k votes cost k judge-alone verdict pairs
    for k in full.VOTE_KS:
        assert c[f"votes_k{k}"][pairs[0]["pair_id"]]["cost_match_usd"] == pytest.approx(k * 2 * COST)
    # debate cost includes both arguments; one-sided includes the one it shows
    pid = pairs[0]["pair_id"]
    assert c["debate_high"][pid]["cost_match_usd"] == pytest.approx(2 * COST + 2 * COST)
    assert c["one_sided"][pid]["cost_match_usd"] == pytest.approx(2 * COST + COST)
    assert c["one_sided"][pid]["shown_side"] in ("A", "B")
    # the fake debate makes the weak judge always right
    assert all(r["correct"] for r in done["debate_high"])

    saved = full.load_records(tmp_path / "pairs.jsonl")
    assert len(saved) == 24 * len(expected)
    conc = full.load_records(tmp_path / "concessions.jsonl")
    assert len(conc) == 24 * 2 * 2 and all(r["auto_verdict"] == "defends" for r in conc)


def test_weak_judge_uses_fixed_temperature_and_votes_share_sample_zero():
    pairs = make_pairs(6)
    fake = FakeChat()
    full.run_judge_alone(pairs, "none", chat_fn=fake, workers=2)
    full.run_votes(pairs, chat_fn=fake, workers=2)
    weak = [c for c in fake.calls if c["thinking"] == "none"]
    assert all(c["temperature"] == full.WEAK_JUDGE_TEMPERATURE for c in weak)
    samples = sorted({c["sample"] for c in fake.calls if c["run"] == "full_votes"})
    assert samples == list(range(full.MAX_VOTE_K))
    # judge-alone and vote sample 0 send the same request (same messages, sample, temperature), so chat() caches it once
    alone = [c for c in fake.calls if c["run"] == "full_judge_none"]
    assert all(c["sample"] == 0 for c in alone)


def test_majority_of_votes_is_used():
    pairs = make_pairs(30)
    recs = full.run_votes(pairs, chat_fn=FakeChat(), workers=4)
    k9 = [r for r in recs if r["condition"] == f"votes_k{full.MAX_VOTE_K}"]
    k1 = [r for r in recs if r["condition"] == "votes_k1"]
    # with independent 70%-right votes, the majority of 9 should be right at least as often as one vote
    assert sum(r["correct"] for r in k9) >= sum(r["correct"] for r in k1)


def test_save_records_merges_and_replaces(tmp_path):
    p = tmp_path / "pairs.jsonl"
    full.save_records(p, [{"pair_id": "a", "condition": "x", "v": 1}, {"pair_id": "b", "condition": "x", "v": 1}])
    full.save_records(p, [{"pair_id": "a", "condition": "x", "v": 2}, {"pair_id": "a", "condition": "y", "v": 1}])
    rows = {(r["pair_id"], r["condition"]): r["v"] for r in full.load_records(p)}
    assert rows == {("a", "x"): 2, ("b", "x"): 1, ("a", "y"): 1}


def test_budget_check_runs_before_each_condition(tmp_path):
    seen = []
    full.run_conditions(make_pairs(4), ("judge_none", "debate_high", "debate_low", "one_sided"), out_dir=tmp_path,
                        chat_fn=FakeChat(), workers=2, budget_check=seen.append, progress=lambda s: None)
    assert seen == ["judge_none", "debate_high"]  # debate_low and one_sided come with debate_high


def test_budget_check_can_stop_the_run(tmp_path):
    def refuse(cond):
        if cond == "votes":
            raise SystemExit("not enough balance")

    with pytest.raises(SystemExit):
        full.run_conditions(make_pairs(4), ("judge_none", "votes"), out_dir=tmp_path, chat_fn=FakeChat(), workers=2,
                            budget_check=refuse, progress=lambda s: None)
    # the finished condition was saved before stopping
    assert {r["condition"] for r in full.load_records(tmp_path / "pairs.jsonl")} == {"judge_none"}


PILOT_SUMMARY = {
    "debate_pairs": 30,
    "conditions": {k: {"cost_match_per_pair_incl_debaters": v} for k, v in {
        "judge_none": 0.000558, "judge_low": 0.002273, "judge_high": 0.003004,
        "debate_low": 0.003444, "debate_high": 0.004996, "one_sided": 0.002774}.items()},
    "debater_cost_match_per_pair": {"low": 0.002712, "high": 0.004255},
}


def test_estimate_cost_matches_the_notes():
    # NOTES.md: debates 4.81, thinking 2.11, one-sided 0.37, weak 0.22; votes up to 11 per order: 10 new samples
    n = {c: 570 if c in full.DEBATE else 600 if c == "votes" else 400 for c in full.GROUPS["all"]}
    e = {c: full.estimate_cost(PILOT_SUMMARY, c, n[c]) for c in full.GROUPS["all"]}
    assert e["debate_high"] + e["debate_low"] == pytest.approx(4.81, abs=0.01)
    assert e["judge_low"] + e["judge_high"] == pytest.approx(2.11, abs=0.01)
    assert e["one_sided"] == pytest.approx(0.37, abs=0.01)
    assert e["judge_none"] == pytest.approx(0.22, abs=0.01)
    assert e["votes"] == pytest.approx(10 * 0.000558 * 600, abs=0.01)  # 3.35: 10 new samples per order on all 600 pairs


@pytest.mark.parametrize("cond,expected", [
    ("judge_low", 5), ("judge_high", 7), ("debate_low", 7), ("debate_high", 9), ("one_sided", 5)])
def test_matched_k_follows_the_proposal_rule_on_pilot_costs(cond, expected):
    weak = PILOT_SUMMARY["conditions"]["judge_none"]["cost_match_per_pair_incl_debaters"]
    cost = PILOT_SUMMARY["conditions"][cond]["cost_match_per_pair_incl_debaters"]
    assert full.matched_k(cost, weak) == expected


def test_matched_k_uses_eleven_when_debate_costs_slightly_more_and_none_beyond():
    assert full.matched_k(9.05, 1.0) == 11
    assert full.matched_k(9.0, 1.0) == 9
    assert full.matched_k(11.5, 1.0) is None


def test_go_decision():
    assert full.go_decision({}) is None
    assert full.go_decision({"go_no_go_final": {"decision": "GO (question 6)"}}).startswith("GO")
