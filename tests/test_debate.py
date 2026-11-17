"""Tests for the debater prompt, debate.py and the concession check. A fake chat() is passed in,
so no API or key is needed."""
from types import SimpleNamespace

import pytest

from debate_judge import debate as D
from debate_judge import judge as J
from debate_judge.prompts import (
    CONCESSION_PROMPT_VERSION,
    DEBATER_MAX_WORDS,
    DEBATER_PROMPT_VERSION,
    debater_user_prompt,
)

PAIR = {
    "pair_id": "p1",
    "question": "What is 2 + 3? Options: (A) 5 (B) 6",
    "response_A": "It is 5. [right]",
    "response_B": "It is 6. [wrong]",
    "label": "A>B",
}


class FakeChat:
    """Records each call. `replies` is a list of (text, complete) returned in turn (the last one repeats)."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        text, complete = self.replies[min(len(self.calls), len(self.replies)) - 1]
        return SimpleNamespace(text=text, complete=complete, cost_usd=0.001, cost_match_usd=0.002)


def user_text(call):
    return call["messages"][-1]["content"]


# ---------------------------------------------------------------- prompt


def test_debater_prompt_names_the_side_and_shows_original_order():
    p = debater_user_prompt("Q?", "first", "second", "B")
    assert "You are assigned to defend Response B." in p
    assert p.index("# Response A\n\nfirst") < p.index("# Response B\n\nsecond")
    assert "Do not concede" in p
    assert '"my response" and "the other response"' in p
    assert f"at most {DEBATER_MAX_WORDS} words" in p
    assert "{" not in p  # no unfilled template fields


def test_debater_prompt_rejects_bad_side():
    with pytest.raises(ValueError):
        debater_user_prompt("Q?", "first", "second", "C")


# ---------------------------------------------------------------- neutralise


@pytest.mark.parametrize("text,side,expected,fixes", [
    ("Response A is right. Response B is wrong.", "A", "My response is right. The other response is wrong.", 2),
    ("Response A is right. Response B is wrong.", "B", "The other response is right. My response is wrong.", 2),
    ("Unlike Response B, mine checks (B).", "A", "Unlike the other response, mine checks (B).", 1),
    ("- Response B's sum is off", "A", "- The other response's sum is off", 1),
    ("The answer is (A); a response a reader trusts.", "A", "The answer is (A); a response a reader trusts.", 0),
])
def test_neutralise(text, side, expected, fixes):
    assert D.neutralise(text, side) == (expected, fixes)


# ---------------------------------------------------------------- argue


def test_argue_calls_chat_with_debater_settings():
    fake = FakeChat([("My response adds correctly.", True)])
    a = D.argue(PAIR, "A", thinking="high", run="pilot_debater_high", chat_fn=fake)
    assert len(fake.calls) == 1
    c = fake.calls[0]
    assert c["thinking"] == "high"
    assert c["max_tokens"] == J.DEFAULT_MAX_TOKENS["high"]
    assert c["run"] == "pilot_debater_high"
    assert c["meta"] == {"role": "debater", "pair_id": "p1", "side": "A", "attempt": 1,
                         "prompt_version": DEBATER_PROMPT_VERSION}
    assert "You are assigned to defend Response A." in user_text(c)
    assert (a.side, a.text, a.complete, a.attempts, a.letter_fixes) == ("A", "My response adds correctly.", True, 1, 0)


def test_argue_rewrites_letters_for_its_side():
    a = D.argue(PAIR, "B", thinking="low", run="t", chat_fn=FakeChat([("Response B is right, Response A errs.", True)]))
    assert a.text == "My response is right, the other response errs."
    assert a.letter_fixes == 2


def test_argue_retries_once_with_a_bigger_cap():
    fake = FakeChat([("", False), ("My response is right.", True)])
    a = D.argue(PAIR, "A", thinking="low", run="t", chat_fn=fake)
    assert [c["max_tokens"] for c in fake.calls] == [J.DEFAULT_MAX_TOKENS["low"], 2 * J.DEFAULT_MAX_TOKENS["low"]]
    assert [c["meta"]["attempt"] for c in fake.calls] == [1, 2]
    assert a.complete and a.attempts == 2
    assert a.cost_usd == pytest.approx(0.002) and a.cost_match_usd == pytest.approx(0.004)


def test_argue_retry_cap_is_limited():
    fake = FakeChat([("", False)])
    D.argue(PAIR, "A", thinking="max", run="t", chat_fn=fake)
    assert [c["max_tokens"] for c in fake.calls] == [D.MAX_OUTPUT_TOKENS, D.MAX_OUTPUT_TOKENS]


def test_argue_gives_up_after_two_incomplete_replies():
    a = D.argue(PAIR, "A", thinking="high", run="t", chat_fn=FakeChat([("cut off", False)]))
    assert (a.complete, a.text, a.attempts) == (False, "", 2)
    assert a.cost_match_usd == pytest.approx(0.004)


def test_argue_rejects_bad_side():
    with pytest.raises(ValueError):
        D.argue(PAIR, "left", thinking="high", run="t", chat_fn=FakeChat([("x", True)]))


# ---------------------------------------------------------------- debate and one-sided


def test_debate_arguments_has_both_sides_from_independent_calls():
    fake = FakeChat([("My response is right.", True)])
    args = D.debate_arguments(PAIR, thinking="high", run="t", chat_fn=fake)
    assert set(args) == {"A", "B"}
    assert [c["meta"]["side"] for c in fake.calls] == ["A", "B"]
    # neither debater sees an argument: each prompt holds only the question and the two responses
    assert all("Debater" not in user_text(c) for c in fake.calls)


def test_arguments_for_judge_drops_incomplete_arguments():
    ok = D.Argument("p1", "A", "high", "text A", True, 0, 1, 0.0, 0.0)
    bad = D.Argument("p1", "B", "high", "", False, 0, 2, 0.0, 0.0)
    assert D.arguments_for_judge({"A": ok, "B": bad}) == {"A": "text A"}


def test_one_sided_side_is_fixed_and_about_half_correct():
    pairs = [{"pair_id": f"id-{i}", "label": "A>B" if i % 3 else "B>A"} for i in range(2000)]
    sides = [D.one_sided_side(p) for p in pairs]
    assert sides == [D.one_sided_side(p) for p in pairs]  # same answer every time
    share = sum(s == D.correct_side(p) for s, p in zip(sides, pairs)) / len(pairs)
    assert 0.45 < share < 0.55


def test_one_sided_arguments_reuses_one_debate_argument():
    args = {"A": D.Argument("p1", "A", "high", "for A", True, 0, 1, 0.0, 0.0),
            "B": D.Argument("p1", "B", "high", "for B", True, 0, 1, 0.0, 0.0)}
    side = D.one_sided_side(PAIR)
    assert D.one_sided_arguments(PAIR, args) == {side: f"for {side}"}
    args[side].complete = False
    assert D.one_sided_arguments(PAIR, args) == {}


def test_neutral_arguments_read_correctly_in_both_orders():
    # The judge shows original A as "Response B" in the swapped order; a neutral argument still fits.
    fake_debater = FakeChat([("Response A is right.", True)])
    args = D.debate_arguments(PAIR, thinking="high", run="t", chat_fn=fake_debater)
    fake_judge = FakeChat([('{"reasoning": "r", "winner": "A"}', True)])
    J.judge_pair(PAIR, thinking="none", run="t", condition="debate_high",
                 arguments=D.arguments_for_judge(args), chat_fn=fake_judge)
    swapped = user_text(fake_judge.calls[1])
    assert "## Debater defending Response B\n\nMy response is right." in swapped
    assert "Response A is right" not in swapped


# ---------------------------------------------------------------- concession check


@pytest.mark.parametrize("text,verdict", [
    ('{"verdict": "defends"}', "defends"),
    ('{"verdict": "Concedes"}', "concedes"),
    ('```json\n{"verdict": "unclear"}\n```', "unclear"),
    ('{"verdict": "maybe"}', None),
    ('{"verdict": "concedes"', "concedes"),  # broken JSON, pattern fallback
    ("no idea", None),
])
def test_parse_concession(text, verdict):
    assert D.parse_concession(text) == verdict


def test_check_concession_settings():
    fake = FakeChat([('{"verdict": "concedes"}', True)])
    arg = D.Argument("p1", "B", "high", "Honestly the other response is right.", True, 0, 1, 0.0, 0.0)
    c = D.check_concession(arg, run="pilot_concession", chat_fn=fake)
    assert c.verdict == "concedes" and c.side == "B"
    call = fake.calls[0]
    assert call["thinking"] == "none" and call["json_mode"] is True and call["temperature"] == 0.0
    assert call["meta"] == {"role": "concession_check", "pair_id": "p1", "side": "B",
                            "debater_thinking": "high", "prompt_version": CONCESSION_PROMPT_VERSION}
    assert "Honestly the other response is right." in user_text(call)


def test_check_concession_skips_incomplete_arguments():
    fake = FakeChat([('{"verdict": "defends"}', True)])
    arg = D.Argument("p1", "A", "high", "", False, 0, 2, 0.0, 0.0)
    c = D.check_concession(arg, run="t", chat_fn=fake)
    assert c.verdict is None and not fake.calls
