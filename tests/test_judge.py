"""Tests for the judge prompt and judge_pair(). A fake chat() is passed in, so no API or key is needed."""
from types import SimpleNamespace

import pytest

from debate_judge import judge as J
from debate_judge.prompts import JUDGE_PROMPT_VERSION, judge_user_prompt

PAIR = {
    "pair_id": "p1",
    "question": "What is 2 + 3?",
    "response_A": "It is 5. [right]",
    "response_B": "It is 6. [wrong]",
    "label": "A>B",
}


class FakeChat:
    """Records each call; `reply` maps the user prompt to the judge's reply text."""

    def __init__(self, reply, complete=True):
        self.reply = reply
        self.complete = complete
        self.calls = []

    def __call__(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        user = messages[-1]["content"]
        return SimpleNamespace(text=self.reply(user), complete=self.complete,
                               cost_usd=0.001, cost_match_usd=0.002)


def shown_a(user_prompt):
    """The text shown as Response A in a judge prompt."""
    return user_prompt.split("# Response A\n\n")[1].split("\n\n# Response B")[0]


def picks_right(user_prompt):
    """A judge that always finds the right response, wherever it is shown."""
    return '{"reasoning": "checked", "winner": "%s"}' % ("A" if "[right]" in shown_a(user_prompt) else "B")


def always_a(_user_prompt):
    return '{"reasoning": "first looks fine", "winner": "A"}'


# ---------------------------------------------------------------- prompt


def test_prompt_contains_question_and_responses_in_order():
    p = judge_user_prompt("Q?", "first", "second")
    assert "Q?" in p
    assert p.index("# Response A\n\nfirst") < p.index("# Response B\n\nsecond")
    assert "debater" not in p.lower()
    assert '"winner"' in p and "JSON" in p


def test_prompt_with_two_arguments():
    p = judge_user_prompt("Q?", "first", "second", {"A": "argA", "B": "argB"})
    assert "# Arguments from two debaters" in p
    assert p.index("## Debater defending Response A\n\nargA") < p.index("## Debater defending Response B\n\nargB")
    assert "claim to check" in p


def test_prompt_with_one_argument():
    p = judge_user_prompt("Q?", "first", "second", {"B": "argB"})
    assert "# Argument from one debater" in p
    assert "## Debater defending Response B\n\nargB" in p
    assert "Debater defending Response A" not in p


def test_prompt_rejects_bad_argument_labels():
    with pytest.raises(ValueError):
        judge_user_prompt("Q?", "first", "second", {"C": "x"})


# ---------------------------------------------------------------- parsing


@pytest.mark.parametrize("text,winner", [
    ('{"reasoning": "r", "winner": "A"}', "A"),
    ('{"reasoning": "r", "winner": "b"}', "B"),
    ('{"reasoning": "r", "winner": "Response B"}', "B"),
    ('```json\n{"reasoning": "r", "winner": "A"}\n```', "A"),
    ('Here is my verdict: {"reasoning": "r", "winner": "B"} Thanks.', "B"),
    ('{"reasoning": "unterminated, "winner": "B"', "B"),  # broken JSON, pattern fallback
    ('{"reasoning": "r", "winner": "A or B"}', None),
    ('{"reasoning": "r", "winner": "tie"}', None),
    ("I cannot decide.", None),
    ("", None),
])
def test_parse_verdict(text, winner):
    assert J.parse_verdict(text)[0] == winner


def test_parse_verdict_returns_reasoning():
    assert J.parse_verdict('{"reasoning": "because 2+3=5", "winner": "A"}') == ("A", "because 2+3=5")


# ---------------------------------------------------------------- judge_pair


def test_both_orders_are_judged_and_swapped():
    fake = FakeChat(picks_right)
    J.judge_pair(PAIR, thinking="none", run="t", condition="judge_alone", chat_fn=fake)
    assert [c["meta"]["order"] for c in fake.calls] == ["AB", "BA"]
    first, second = (c["messages"][-1]["content"] for c in fake.calls)
    assert shown_a(first) == PAIR["response_A"]
    assert shown_a(second) == PAIR["response_B"]


def test_decisions_are_in_original_labels():
    v = J.judge_pair(PAIR, thinking="none", run="t", condition="judge_alone", chat_fn=FakeChat(picks_right))
    assert v.decisions == ["A>B", "A>B"]
    assert v.consistent
    assert [x.shown_winner for x in v.verdicts] == ["A", "B"]


def test_position_bias_shows_as_inconsistent():
    v = J.judge_pair(PAIR, thinking="none", run="t", condition="judge_alone", chat_fn=FakeChat(always_a))
    assert v.decisions == ["A>B", "B>A"]
    assert not v.consistent


def test_arguments_follow_their_response_when_swapped():
    fake = FakeChat(picks_right)
    args = {"A": "ARG FOR ORIGINAL A", "B": "ARG FOR ORIGINAL B"}
    J.judge_pair(PAIR, thinking="none", run="t", condition="debate_high", arguments=args, chat_fn=fake)
    first, second = (c["messages"][-1]["content"] for c in fake.calls)
    assert "## Debater defending Response A\n\nARG FOR ORIGINAL A" in first
    # In the swapped order, original A is shown as Response B, and so is its debater.
    assert "## Debater defending Response B\n\nARG FOR ORIGINAL A" in second
    assert "## Debater defending Response A\n\nARG FOR ORIGINAL B" in second


def test_one_sided_argument_is_relabeled_too():
    fake = FakeChat(picks_right)
    J.judge_pair(PAIR, thinking="none", run="t", condition="one_sided", arguments={"B": "ARG B"}, chat_fn=fake)
    first, second = (c["messages"][-1]["content"] for c in fake.calls)
    assert "## Debater defending Response B\n\nARG B" in first
    assert "## Debater defending Response A\n\nARG B" in second
    assert [c["meta"]["n_arguments"] for c in fake.calls] == [1, 1]


def test_incomplete_reply_gives_no_decision():
    fake = FakeChat(always_a, complete=False)
    v = J.judge_pair(PAIR, thinking="high", run="t", condition="thinking_judge", chat_fn=fake)
    assert v.decisions == [None, None]
    assert not v.consistent
    assert all(not x.complete for x in v.verdicts)


def test_settings_and_meta_are_passed_to_chat():
    fake = FakeChat(picks_right)
    J.judge_pair(PAIR, thinking="high", run="pilot_judge_high", condition="thinking_judge", sample=3, chat_fn=fake)
    c = fake.calls[0]
    assert c["thinking"] == "high"
    assert c["max_tokens"] == J.DEFAULT_MAX_TOKENS["high"]
    assert c["run"] == "pilot_judge_high"
    assert c["sample"] == 3
    assert c["json_mode"] is True
    assert c["temperature"] is None
    assert c["meta"] == {"role": "judge", "pair_id": "p1", "order": "AB", "condition": "thinking_judge",
                         "n_arguments": 0, "prompt_version": JUDGE_PROMPT_VERSION}


def test_temperature_is_passed_to_chat_for_votes():
    fake = FakeChat(picks_right)
    J.judge_pair(PAIR, thinking="none", run="t", condition="votes", sample=1, temperature=1.0, chat_fn=fake)
    assert [c["temperature"] for c in fake.calls] == [1.0, 1.0]


def test_costs_are_summed_over_both_orders():
    v = J.judge_pair(PAIR, thinking="none", run="t", condition="judge_alone", chat_fn=FakeChat(picks_right))
    assert v.cost_usd == pytest.approx(0.002)
    assert v.cost_match_usd == pytest.approx(0.004)


def test_bad_argument_labels_are_rejected():
    with pytest.raises(ValueError):
        J.judge_pair(PAIR, thinking="none", run="t", condition="x", arguments={"left": "?"}, chat_fn=FakeChat(always_a))
