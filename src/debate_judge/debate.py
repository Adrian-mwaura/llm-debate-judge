"""Debaters: one-round debate, one-sided argument, and the concession check.

    from debate_judge.debate import debate_arguments, arguments_for_judge, one_sided_arguments
    args = debate_arguments(pair, thinking="high", run="pilot_debater_high")   # {"A": Argument, "B": Argument}
    judge_pair(pair, thinking="none", run=..., condition="debate_high", arguments=arguments_for_judge(args))
    judge_pair(pair, thinking="none", run=..., condition="one_sided", arguments=one_sided_arguments(pair, args))

One round: each debater makes ONE call that defends its assigned response and critiques the other.
The two debaters never see each other's arguments, so their calls are independent.

The one-sided condition reuses one of the two `high` debate arguments instead of a separate call.
The prompt is the same, so the only difference between the conditions is whether the judge also
sees the second argument. The side is fixed per pair by a seeded hash: it is the correct response
about half the time.

Arguments are in the pair's ORIGINAL labels ({"A": ..., "B": ...}), like judge_pair() expects.
Debaters are told to say "my response" and "the other response", never "Response A/B", so the same
text reads correctly in both answer orders; any "Response A/B" that slips through is rewritten here.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from debate_judge.judge import DEFAULT_MAX_TOKENS, extract_json
from debate_judge.prompts import (
    CONCESSION_PROMPT_VERSION,
    DEBATER_PROMPT_VERSION,
    concession_messages,
    debater_messages,
)

SIDES = ("A", "B")
_OTHER = {"A": "B", "B": "A"}

# A cut-off or blank argument is retried once with twice the token cap (up to this limit).
MAX_OUTPUT_TOKENS = max(DEFAULT_MAX_TOKENS.values())

ONE_SIDED_SEED = "one-sided-v1"  # change only before any one-sided results exist

CONCESSION_VERDICTS = ("defends", "concedes", "unclear")
CONCESSION_MAX_TOKENS = 200


def _chat(chat_fn):
    if chat_fn is None:
        from debate_judge.llm import chat  # imported here so tests need no API setup
        return chat
    return chat_fn


# ---------------------------------------------------------------- arguments


@dataclass
class Argument:
    pair_id: Any
    side: str             # "A" or "B": the original label of the response this debater defends
    thinking: str
    text: str             # the argument, with any "Response A/B" rewritten; "" if incomplete
    complete: bool
    letter_fixes: int     # how many "Response A/B" mentions were rewritten
    attempts: int
    cost_usd: float       # summed over attempts
    cost_match_usd: float


_LETTER_RE = re.compile(r"\b([Rr]esponse)\s+([AB])\b")
_SENTENCE_START = ".!?\n-*>#:"


def neutralise(text: str, side: str) -> tuple[str, int]:
    """Rewrite "Response A/B" as "my response" / "the other response" for a debater on `side`.

    Only "Response" followed by a capital A or B is touched, so answer options such as "(B)"
    and words like "a response a reader..." are left alone. Returns (text, number of rewrites).
    """
    def repl(m: re.Match) -> str:
        phrase = "my response" if m.group(2) == side else "the other response"
        before = text[:m.start()].rstrip(" \t\"'(")
        if not before or before[-1] in _SENTENCE_START:
            phrase = phrase[0].upper() + phrase[1:]
        return phrase

    return _LETTER_RE.subn(repl, text)


def argue(
    pair: Mapping[str, Any],
    side: str,
    *,
    thinking: str,
    run: str,
    max_tokens: int | None = None,
    chat_fn: Callable[..., Any] | None = None,
) -> Argument:
    """One debater call: defend `side` ("A" or "B", original label) and critique the other response.

    A cut-off or blank reply is retried once with twice the token cap; if that fails too, the
    argument comes back with complete=False and text "". Both attempts' costs are counted.
    """
    if side not in SIDES:
        raise ValueError(f"side must be 'A' or 'B', got {side!r}")
    chat = _chat(chat_fn)
    first_cap = max_tokens or DEFAULT_MAX_TOKENS[thinking]
    caps = (first_cap, min(2 * first_cap, MAX_OUTPUT_TOKENS))
    messages = debater_messages(pair["question"], pair["response_A"], pair["response_B"], side)

    cost = cost_match = 0.0
    for attempt, cap in enumerate(caps, start=1):
        r = chat(
            messages,
            thinking=thinking,
            max_tokens=cap,
            run=run,
            meta={
                "role": "debater",
                "pair_id": pair.get("pair_id"),
                "side": side,
                "attempt": attempt,
                "prompt_version": DEBATER_PROMPT_VERSION,
            },
        )
        cost += r.cost_usd
        cost_match += r.cost_match_usd
        if r.complete:
            text, fixes = neutralise(r.text.strip(), side)
            return Argument(pair.get("pair_id"), side, thinking, text, True, fixes, attempt, cost, cost_match)
    return Argument(pair.get("pair_id"), side, thinking, "", False, 0, len(caps), cost, cost_match)


def debate_arguments(
    pair: Mapping[str, Any],
    *,
    thinking: str,
    run: str,
    max_tokens: int | None = None,
    chat_fn: Callable[..., Any] | None = None,
) -> dict[str, Argument]:
    """Both debaters' arguments for one pair, {"A": ..., "B": ...} in original labels.

    The two calls are independent (neither debater sees the other's argument). Run pairs in
    parallel at the caller; within a pair the calls run one after the other.
    """
    return {side: argue(pair, side, thinking=thinking, run=run, max_tokens=max_tokens, chat_fn=chat_fn)
            for side in SIDES}


def arguments_for_judge(args: Mapping[str, Argument]) -> dict[str, str]:
    """The argument texts judge_pair() takes. Incomplete arguments are left out, so the judge
    meta's n_arguments shows when a debate was missing a side."""
    return {side: a.text for side, a in args.items() if a.complete}


# ---------------------------------------------------------------- one-sided argument


def correct_side(pair: Mapping[str, Any]) -> str:
    """The original label of the correct response."""
    return "A" if pair["label"] == "A>B" else "B"


def one_sided_side(pair: Mapping[str, Any], seed: str = ONE_SIDED_SEED) -> str:
    """The side whose argument the judge sees in the one-sided condition.

    A seeded hash of the pair id decides whether it is the correct response (about half the
    time), so the choice is fixed per pair and does not depend on which other pairs are run.
    """
    digest = hashlib.sha256(f"{seed}:{pair['pair_id']}".encode("utf-8")).digest()
    right = correct_side(pair)
    return right if digest[0] < 128 else _OTHER[right]


def one_sided_arguments(pair: Mapping[str, Any], debate_args: Mapping[str, Argument]) -> dict[str, str]:
    """The one-sided condition's argument for judge_pair(): one of the `high` debate arguments.

    Returns {} if that argument is incomplete, so the judge would see no argument at all;
    the caller should count those pairs.
    """
    side = one_sided_side(pair)
    a = debate_args[side]
    return {side: a.text} if a.complete else {}


# ---------------------------------------------------------------- concession check


@dataclass
class ConcessionCheck:
    pair_id: Any
    side: str
    verdict: str | None   # "defends", "concedes", "unclear"; None if the reply was unusable
    complete: bool
    cost_usd: float
    cost_match_usd: float


_VERDICT_RE = re.compile(r'"verdict"\s*:\s*"\s*(defends|concedes|unclear)\s*"', re.IGNORECASE)


def parse_concession(text: str) -> str | None:
    """"defends", "concedes" or "unclear" from the checker's reply; None if unreadable."""
    obj = extract_json(text)
    if obj is not None:
        v = str(obj.get("verdict", "")).strip().lower()
        return v if v in CONCESSION_VERDICTS else None
    m = _VERDICT_RE.search(text or "")
    return m.group(1).lower() if m else None


def check_concession(
    argument: Argument,
    *,
    run: str,
    chat_fn: Callable[..., Any] | None = None,
) -> ConcessionCheck:
    """Ask a non-thinking call whether an argument defends its side or concedes.

    This is analysis, not part of any condition: the judge never sees it, so it is not counted
    in cost matching. Check it against hand labels on the pilot before trusting it on the full run.
    """
    chat = _chat(chat_fn)
    if not argument.complete:
        return ConcessionCheck(argument.pair_id, argument.side, None, False, 0.0, 0.0)
    r = chat(
        concession_messages(argument.text),
        thinking="none",
        max_tokens=CONCESSION_MAX_TOKENS,
        run=run,
        temperature=0.0,
        json_mode=True,
        meta={
            "role": "concession_check",
            "pair_id": argument.pair_id,
            "side": argument.side,
            "debater_thinking": argument.thinking,
            "prompt_version": CONCESSION_PROMPT_VERSION,
        },
    )
    verdict = parse_concession(r.text) if r.complete else None
    return ConcessionCheck(argument.pair_id, argument.side, verdict, r.complete, r.cost_usd, r.cost_match_usd)
