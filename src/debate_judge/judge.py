"""The pairwise judge: one JudgeBench pair, judged in both answer orders.

    from debate_judge.judge import judge_pair
    v = judge_pair(pair, thinking="none", run="pilot_judge_none", condition="judge_alone")
    v.decisions        # ["A>B" | "B>A" | None, ...] for the original order and the swapped order
    v.cost_match_usd   # both calls, at list price

`pair` is a JudgeBench record (or any mapping with the same fields): pair_id, question,
response_A, response_B. The label is not needed here; scoring is done separately.

Both decisions are in the pair's ORIGINAL labels: "A>B" always means the judge preferred
pair["response_A"], whichever position it was shown in. (JudgeBench's published outputs keep the
second decision in swapped labels and flip it when scoring; do not flip these again.)

Debate arguments are passed in the original labels too, {"A": ..., "B": ...}, and are relabeled
for the swapped order, so the same argument text is reused for both orders.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from debate_judge.prompts import JUDGE_PROMPT_VERSION, judge_messages

ORDERS = ("AB", "BA")  # AB: original order; BA: response_B shown first, as "Response A"

# Room for the answer, plus the reasoning tokens when thinking is on. These are caps, not costs;
# an answer that hits the cap comes back with complete=False and is not cached.
DEFAULT_MAX_TOKENS = {"none": 1000, "low": 16000, "high": 32000, "max": 64000}

_SWAP = {"A": "B", "B": "A"}


@dataclass
class OrderVerdict:
    order: str                # "AB" or "BA"
    shown_winner: str | None  # "A" or "B" as shown to the judge; None if unparsable or incomplete
    decision: str | None      # "A>B" or "B>A" in the pair's original labels; None as above
    reasoning: str
    complete: bool
    cost_usd: float
    cost_match_usd: float


@dataclass
class PairVerdict:
    pair_id: Any
    verdicts: tuple[OrderVerdict, OrderVerdict]

    @property
    def decisions(self) -> list[str | None]:
        """Decisions for the original and the swapped order, both in original labels."""
        return [v.decision for v in self.verdicts]

    @property
    def consistent(self) -> bool:
        """True if both orders chose the same response."""
        d = self.decisions
        return d[0] is not None and d[0] == d[1]

    @property
    def cost_usd(self) -> float:
        return sum(v.cost_usd for v in self.verdicts)

    @property
    def cost_match_usd(self) -> float:
        return sum(v.cost_match_usd for v in self.verdicts)


# ---------------------------------------------------------------- parsing

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)
_WINNER_RE = re.compile(r'"winner"\s*:\s*"\s*(?:response\s+)?([ab])\s*"', re.IGNORECASE)


def _normalise_winner(value: Any) -> str | None:
    w = str(value or "").strip().upper()
    if w.startswith("RESPONSE "):
        w = w[len("RESPONSE "):].strip()
    return w if w in ("A", "B") else None


def extract_json(text: str) -> dict | None:
    """The JSON object in a model reply, or None.

    Tries the whole reply first (after removing code fences), then the first {...} block,
    for replies wrapped in prose.
    """
    cleaned = _FENCE.sub("", text or "").strip()
    candidates = [cleaned]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if 0 <= start < end:
        candidates.append(cleaned[start:end + 1])
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def parse_verdict(text: str) -> tuple[str | None, str]:
    """Return (winner, reasoning) from the judge's reply; winner is "A", "B" or None.

    Uses extract_json(), then a "winner": "X" pattern as a last resort for broken JSON.
    """
    obj = extract_json(text)
    if obj is not None:
        return _normalise_winner(obj.get("winner")), str(obj.get("reasoning", "")).strip()
    m = _WINNER_RE.search(_FENCE.sub("", text or ""))
    return (m.group(1).upper() if m else None), ""


def _decision(shown_winner: str | None, order: str) -> str | None:
    """Map the winner as shown back to a decision in the pair's original labels."""
    if shown_winner is None:
        return None
    original = shown_winner if order == "AB" else _SWAP[shown_winner]
    return "A>B" if original == "A" else "B>A"


# ---------------------------------------------------------------- judging


def _shown(pair: Mapping[str, Any], order: str, arguments: Mapping[str, str] | None):
    """Responses and arguments as shown in the given order."""
    a, b = pair["response_A"], pair["response_B"]
    args = dict(arguments or {})
    if order == "AB":
        return a, b, args
    return b, a, {_SWAP[label]: text for label, text in args.items()}


def judge_pair(
    pair: Mapping[str, Any],
    *,
    thinking: str,
    run: str,
    condition: str,
    arguments: Mapping[str, str] | None = None,
    sample: int = 0,
    temperature: float | None = None,
    max_tokens: int | None = None,
    json_mode: bool = True,
    chat_fn: Callable[..., Any] | None = None,
) -> PairVerdict:
    """Judge one pair in both answer orders and return both verdicts.

    thinking:    "none" for the weak judge; "low", "high" or "max" for the thinking judge.
    run:         log file name for chat(), one per condition, e.g. "pilot_judge_none".
    condition:   recorded in each call's meta, e.g. "judge_alone", "one_sided", "debate_high".
    arguments:   debater arguments in ORIGINAL labels, {"A": ..., "B": ...}; one entry = one-sided.
    sample:      vote index (0..k-1) for the vote baseline; part of chat()'s cache key.
    temperature: set it explicitly for the vote baseline so it is logged; chat() only sends it
                 with thinking="none" (the API ignores it in thinking mode).
    chat_fn:     defaults to debate_judge.llm.chat; tests pass a fake.
    """
    if chat_fn is None:
        from debate_judge.llm import chat as chat_fn  # imported here so tests need no API setup
    if arguments and set(arguments) - {"A", "B"}:
        raise ValueError(f"arguments keys must be 'A' or 'B', got {sorted(arguments)}")
    if max_tokens is None:
        max_tokens = DEFAULT_MAX_TOKENS[thinking]

    verdicts = []
    for order in ORDERS:
        first, second, shown_args = _shown(pair, order, arguments)
        r = chat_fn(
            judge_messages(pair["question"], first, second, shown_args),
            thinking=thinking,
            max_tokens=max_tokens,
            run=run,
            json_mode=json_mode,
            sample=sample,
            temperature=temperature,
            meta={
                "role": "judge",
                "pair_id": pair.get("pair_id"),
                "order": order,
                "condition": condition,
                "n_arguments": len(shown_args),
                "prompt_version": JUDGE_PROMPT_VERSION,
            },
        )
        shown_winner, reasoning = parse_verdict(r.text) if r.complete else (None, "")
        verdicts.append(OrderVerdict(
            order=order,
            shown_winner=shown_winner,
            decision=_decision(shown_winner, order),
            reasoning=reasoning,
            complete=r.complete,
            cost_usd=r.cost_usd,
            cost_match_usd=r.cost_match_usd,
        ))
    return PairVerdict(pair_id=pair.get("pair_id"), verdicts=(verdicts[0], verdicts[1]))
