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


# ---- Adrian's PR #12 review -------------------------------------------------------------


def test_incomplete_arguments_leave_the_denominator():
    rows = [{"debater_thinking": "low", "assigned_correct": False, "auto_verdict": v, "complete": c}
            for v, c in (("concedes", True), ("defends", True), (None, False), (None, False))]
    r = pilot.concession_rates(rows)["low"]
    assert (r["wrong_side_arguments"], r["incomplete_excluded"], r["rate"]) == (2, 2, 0.5)


def test_no_complete_wrong_side_argument_is_an_error_not_no_go():
    rows = [{"debater_thinking": "low", "assigned_correct": False, "auto_verdict": None, "complete": False},
            {"debater_thinking": "low", "assigned_correct": True, "auto_verdict": "defends", "complete": True}]
    with pytest.raises(ValueError, match="no complete wrong-side"):
        pilot.concession_rates(rows)


def test_concession_rates_read_csv_text_values():
    rows = [{"debater_thinking": "high", "assigned_correct": "False", "complete": "True", "auto_verdict": "defends"},
            {"debater_thinking": "high", "assigned_correct": "True", "complete": "True", "auto_verdict": "concedes"}]
    assert pilot.concession_rates(rows)["high"]["wrong_side_arguments"] == 1


@pytest.mark.parametrize("cond,needed,capped,flag", [(9.0, 9, 9, False), (15.0, 15, 15, False), (16.4, 17, 15, True),
                                                     (40.0, 39, 15, True)])
def test_vote_cap(cond, needed, capped, flag):
    assert pilot.votes_needed(cond, 1.0) == needed
    assert pilot.suggested_votes(cond, 1.0) == capped
    assert pilot.vote_cap_exceeded(cond, 1.0) is flag


def _labelled_rows(labels, auto="defends"):
    rows = []
    for level in ("low", "high"):
        for i, lab in enumerate(labels):
            rows.append({"pair_id": f"p{i}", "debater_thinking": level, "side": "B", "assigned_correct": "False",
                         "complete": "True", "auto_verdict": auto, "hand_label": lab})
        rows.append({"pair_id": "right", "debater_thinking": level, "side": "A", "assigned_correct": "True",
                     "complete": "True", "auto_verdict": "defends", "hand_label": ""})  # right side needs no label
    return rows


SUMMARY = {"go_no_go": {"rule": "r", "thinking_beats_weak": True, "thinking_minus_weak": "+18.5"}}


def test_decide_go_with_hand_labels():
    final = pilot.decide(SUMMARY, _labelled_rows(["defends"] * 9 + ["concedes"]))
    assert final["decision"].startswith("GO")
    assert final["concession_hand"]["low"]["rate"] == pytest.approx(0.1)
    assert final["hand_vs_auto_agreement"]["agree"] == 18 and final["hand_vs_auto_agreement"]["of"] == 20
    assert len(final["hand_vs_auto_agreement"]["disagreements"]) == 2


def test_decide_no_go_when_hand_labels_show_concessions():
    final = pilot.decide(SUMMARY, _labelled_rows(["concedes"] * 3 + ["defends"] * 7))
    assert final["decision"].startswith("NO-GO") and final["concessions_ok_hand"] is False


def test_decide_no_go_when_thinking_judge_is_not_better():
    final = pilot.decide({"go_no_go": {**SUMMARY["go_no_go"], "thinking_beats_weak": False}},
                         _labelled_rows(["defends"] * 10))
    assert final["decision"].startswith("NO-GO")


@pytest.mark.parametrize("bad", ["", "yes", "conceded"])
def test_decide_refuses_missing_or_unknown_labels(bad):
    with pytest.raises(ValueError, match="hand_label"):
        pilot.decide(SUMMARY, _labelled_rows(["defends"] * 9 + [bad]))


def test_decide_accepts_label_case_and_spaces():
    assert pilot.decide(SUMMARY, _labelled_rows([" Defends "] * 10))["decision"].startswith("GO")


def test_decide_reads_the_csv_written_by_write_outputs(tmp_path):
    pairs = make_pairs(30)
    result = pilot.run_stage("pilot", pairs, chat_fn=FakeChat(), workers=4, progress=lambda s: None)
    pilot.write_outputs(result, tmp_path)
    rows = pilot.read_concession_csv(tmp_path / "concession_review.csv")
    with pytest.raises(ValueError):  # unlabelled
        pilot.decide(result["summary"], rows)
    for r in rows:
        r["hand_label"] = "defends"
    assert pilot.decide(result["summary"], rows)["decision"].startswith("GO")


# ---- freeze check, on a throwaway git repository ----


def _git(repo, *args):
    import subprocess
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True,
                   capture_output=True)


@pytest.fixture
def repo(tmp_path):
    for f in pilot.FROZEN_FILES + ("docs/NOTES.md",):
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("v1\n", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_freeze_requires_the_named_tag(repo):
    _git(repo, "tag", "some-other-tag")
    g = pilot.git_state(repo)
    assert g["tag_exists"] is False and g["frozen"] is False


def test_frozen_when_tagged(repo):
    _git(repo, "tag", "prompts-v1")
    assert pilot.git_state(repo)["frozen"] is True


def test_later_commits_to_other_files_stay_frozen(repo):
    _git(repo, "tag", "prompts-v1")
    (repo / "docs/NOTES.md").write_text("results\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "notes")
    g = pilot.git_state(repo)
    assert g["frozen"] is True and g["commit"] != g["tag_commit"]


@pytest.mark.parametrize("f", pilot.FROZEN_FILES)
def test_committed_change_to_a_frozen_file_unfreezes(repo, f):
    _git(repo, "tag", "prompts-v1")
    (repo / f).write_text("v2\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "change")
    g = pilot.git_state(repo)
    assert g["frozen_files_same_as_tag"] is False and g["frozen"] is False


def test_uncommitted_change_to_a_frozen_file_unfreezes(repo):
    _git(repo, "tag", "prompts-v1")
    (repo / "src/debate_judge/judge.py").write_text("edited\n", encoding="utf-8")
    g = pilot.git_state(repo)
    assert g["frozen_files_uncommitted_changes"] is True and g["frozen"] is False
