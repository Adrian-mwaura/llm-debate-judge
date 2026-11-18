"""The whole pilot pipeline with a fake chat(): no API calls, no download."""
import json
from types import SimpleNamespace

import pytest

from debate_judge import data, pilot


class FakeChat:
    """Weak judge right 60% of the time, thinking judge 90%; debaters always defend; checker says 'defends'."""

    def __init__(self):
        self.calls = []

    def __call__(self, messages, *, thinking, max_tokens, run, **kw):
        self.calls.append({"thinking": thinking, "run": run, **kw})
        meta = kw.get("meta", {})
        role = meta.get("role")
        if role == "debater":
            text = "My response is correct; the other response makes an error. Response A says so."
        elif role == "concession_check":
            text = '{"verdict": "defends"}'
        else:
            pid = meta["pair_id"]
            truth = LABELS[pid]
            good = (hash(pid) % 10) < (9 if thinking != "none" else 6)
            orig_winner = truth if good else ("B" if truth == "A" else "A")
            shown = orig_winner if meta["order"] == "AB" else ("B" if orig_winner == "A" else "A")
            text = json.dumps({"reasoning": "x", "winner": shown})
        out = 400 if thinking == "none" else 2000
        return SimpleNamespace(text=text, complete=True, cost_usd=1e-4, cost_match_usd=(300 * 0.15 + out * 0.6) / 1e6)


LABELS = {}


def make_pairs(n):
    pairs = []
    for i in range(n):
        cat = data.CATEGORIES[i % 4]
        label = "A>B" if i % 3 else "B>A"
        pid = f"pair-{i:03d}"
        LABELS[pid] = label[0]
        pairs.append({"pair_id": pid, "question": f"Q{i}", "response_A": "ra", "response_B": "rb", "label": label,
                      "category": cat, "group": data.group(cat)})
    return pairs


def test_pilot_stage_end_to_end(tmp_path):
    pairs = make_pairs(60)
    fake = FakeChat()
    result = pilot.run_stage("pilot", pairs, chat_fn=fake, workers=4, progress=lambda s: None)
    s = result["summary"]

    assert set(s["conditions"]) == {"judge_none", "judge_low", "judge_high", "debate_low", "debate_high", "one_sided"}
    assert s["conditions"]["judge_none"]["n"] == 60 and s["conditions"]["debate_high"]["n"] == 30
    # weak judge always at the fixed temperature; thinking judge sends none
    weak_calls = [c for c in fake.calls if c["run"] == "pilot_judge_none"]
    assert weak_calls and all(c["temperature"] == pilot.WEAK_JUDGE_TEMPERATURE for c in weak_calls)
    assert all(c["temperature"] is None for c in fake.calls if c["run"] == "pilot_judge_high")
    # call counts: 60 pairs x 2 orders per judge condition; 30 pairs x 2 sides per debater level
    runs = [c["run"] for c in fake.calls]
    assert runs.count("pilot_judge_none") == 120 and runs.count("pilot_debater_high") == 60
    assert runs.count("pilot_concession") == 120
    # debate conditions cost more per pair than the weak judge because they include the arguments
    cpp = {k: v["cost_match_per_pair_incl_debaters"] for k, v in s["conditions"].items()}
    assert cpp["debate_high"] > cpp["one_sided"] > cpp["judge_none"]
    assert all(v % 2 == 1 for v in (c["suggested_votes_per_order"] for k, c in s["conditions"].items()
                                     if k != "judge_none"))
    # go/no-go: the fake thinking judge is clearly better and nobody concedes
    assert s["go_no_go"]["thinking_beats_weak"] is True
    assert s["go_no_go"]["concessions_ok_auto"] is True
    assert s["go_no_go"]["decision_auto"].startswith("GO")
    assert s["debater_letter_fixes"]["high"] == 60  # every fake argument had one "Response A"

    pilot.write_outputs(result, tmp_path)
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))["stage"] == "pilot"
    lines = (tmp_path / "concession_review.csv").read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 1 + 120 and "hand_label" in lines[0]


def test_dry_stage_uses_five_debate_pairs():
    pairs = make_pairs(20)
    fake = FakeChat()
    s = pilot.run_stage("dry", pairs, chat_fn=fake, workers=4, progress=lambda s: None)["summary"]
    assert s["debate_pairs"] == 5 and s["conditions"]["one_sided"]["n"] == 5
    assert all(c["run"].startswith("dry_") for c in fake.calls)


@pytest.mark.parametrize("cond,weak,expected", [
    (1.0, 1.0, 1), (2.0, 1.0, 1), (2.6, 1.0, 3), (3.0, 1.0, 3), (4.2, 1.0, 5), (6.9, 1.0, 7), (0.2, 1.0, 1),
])
def test_suggested_votes_is_odd_and_closest(cond, weak, expected):
    assert pilot.suggested_votes(cond, weak) == expected


def test_concession_rates():
    rows = [{"debater_thinking": "high", "assigned_correct": False, "auto_verdict": v, "complete": True}
            for v in ("concedes", "defends", "defends", "unclear")]
    rows.append({"debater_thinking": "high", "assigned_correct": True, "auto_verdict": "concedes", "complete": True})
    r = pilot.concession_rates(rows)["high"]
    assert (r["wrong_side_arguments"], r["concedes"], r["unclear"]) == (4, 1, 1) and r["rate"] == 0.25
