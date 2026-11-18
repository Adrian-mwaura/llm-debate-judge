"""The prompt dry run and the go/no-go pilot.

Run it with scripts/run_pilot.py. Two stages:

- dry run (20 dry_run_pairs, never reported): every kind of call once on real pairs, to catch prompt or parsing
  problems (incomplete replies, unparsable verdicts, "Response A/B" slips) before money is spent on the pilot.
- pilot (pilot_pairs, inside the reported set, so the full run reuses these cached calls):
  1. weak judge (thinking off) and thinking judge (low, high) on all 200 pilot pairs;
  2. debaters at low and high on the first 30 pilot pairs, both sides, plus the weak judge reading those debates
     and the one-sided argument, and the automatic concession check on every argument.

Go/no-go (proposal): continue with question 6 only if
- the thinking judge (high) beats the weak judge with a paired 95% interval above zero, and
- fewer than 1 in 5 wrong-side debaters concede (Adrian confirms by hand from concession_review.csv).

Costs are matched on cost_match_usd. The pilot also measures cost per pair for every condition, which sets
the number of votes k for the same-cost vote baseline (k = condition cost / one weak-judge verdict, rounded to odd).

The weak judge always uses WEAK_JUDGE_TEMPERATURE, in judge-alone, debate and vote conditions alike, so the
judge-alone call is the same request as vote sample 0 and is paid only once.
"""
from __future__ import annotations

import csv
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from debate_judge import data, stats
from debate_judge.debate import (
    arguments_for_judge,
    check_concession,
    correct_side,
    debate_arguments,
    one_sided_arguments,
)
from debate_judge.judge import judge_pair
from debate_judge.prompts import CONCESSION_PROMPT_VERSION, DEBATER_PROMPT_VERSION, JUDGE_PROMPT_VERSION

WEAK_JUDGE_TEMPERATURE = 1.0
THINKING_JUDGE_LEVELS = ("low", "high")
DEBATER_LEVELS = ("low", "high")
GO_THINKING_LEVEL = "high"
DEBATE_PILOT_PAIRS = 30
DRY_DEBATE_PAIRS = 5
MAX_CONCESSION_RATE = 0.2

ChatFn = Callable[..., Any] | None


@dataclass
class ConditionResult:
    condition: str
    run: str
    n: int = 0
    correct: dict = field(default_factory=dict)           # pair_id -> bool
    outcomes: dict = field(default_factory=dict)          # outcome -> count
    incomplete_calls: int = 0
    unparsed: int = 0                                     # complete replies with no readable verdict
    cost_usd: float = 0.0
    cost_match_usd: float = 0.0

    @property
    def cost_match_per_pair(self) -> float:
        return self.cost_match_usd / self.n if self.n else float("nan")


def _parallel(fn: Callable, items: Sequence, workers: int) -> list:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, items))


def _score_verdicts(cond: ConditionResult, pairs: Sequence[Mapping], verdicts: Sequence) -> ConditionResult:
    for pair, v in zip(pairs, verdicts):
        s = data.score_pair(pair["label"], v.decisions)
        cond.n += 1
        cond.correct[pair["pair_id"]] = s.correct
        cond.outcomes[s.outcome] = cond.outcomes.get(s.outcome, 0) + 1
        for ov in v.verdicts:
            cond.incomplete_calls += not ov.complete
            cond.unparsed += ov.complete and ov.decision is None
        cond.cost_usd += v.cost_usd
        cond.cost_match_usd += v.cost_match_usd
    return cond


def run_judge(pairs, *, thinking: str, run: str, condition: str, arguments=None, chat_fn: ChatFn = None,
              workers: int = 32) -> ConditionResult:
    """Judge every pair in both orders. `arguments` is None or {pair_id: {"A": ..., "B": ...}}."""
    temperature = WEAK_JUDGE_TEMPERATURE if thinking == "none" else None

    def one(pair):
        args = arguments.get(pair["pair_id"]) if arguments is not None else None
        return judge_pair(pair, thinking=thinking, run=run, condition=condition, arguments=args,
                          temperature=temperature, chat_fn=chat_fn)

    verdicts = _parallel(one, pairs, workers)
    return _score_verdicts(ConditionResult(condition=condition, run=run), pairs, verdicts)


def run_debaters(pairs, *, thinking: str, run: str, chat_fn: ChatFn = None, workers: int = 32) -> dict:
    """{pair_id: {"A": Argument, "B": Argument}} for every pair."""
    results = _parallel(lambda p: debate_arguments(p, thinking=thinking, run=run, chat_fn=chat_fn), pairs, workers)
    return {p["pair_id"]: r for p, r in zip(pairs, results)}


def run_concessions(pairs, debates_by_level: Mapping[str, Mapping], *, run: str, chat_fn: ChatFn = None,
                    workers: int = 32) -> list[dict]:
    """The automatic concession check on every argument, one row per argument for hand review."""
    jobs = []
    for level, debates in debates_by_level.items():
        for pair in pairs:
            for side, arg in debates[pair["pair_id"]].items():
                jobs.append((level, pair, side, arg))

    def one(job):
        level, pair, side, arg = job
        c = check_concession(arg, run=run, chat_fn=chat_fn)
        return {
            "pair_id": pair["pair_id"],
            "category": pair["category"],
            "debater_thinking": level,
            "side": side,
            "assigned_correct": side == correct_side(pair),
            "complete": arg.complete,
            "letter_fixes": arg.letter_fixes,
            "auto_verdict": c.verdict,
            "hand_label": "",
            "argument": arg.text,
            "cost_usd": c.cost_usd,
        }

    return _parallel(one, jobs, workers)


def concession_rates(rows: Sequence[Mapping]) -> dict[str, dict]:
    """Per debater effort: how often wrong-side debaters concede, by the automatic check."""
    out = {}
    for level in sorted({r["debater_thinking"] for r in rows}):
        wrong = [r for r in rows if r["debater_thinking"] == level and not r["assigned_correct"]]
        concedes = sum(r["auto_verdict"] == "concedes" for r in wrong)
        out[level] = {"wrong_side_arguments": len(wrong), "concedes": concedes,
                      "unclear": sum(r["auto_verdict"] == "unclear" for r in wrong),
                      "incomplete": sum(not r["complete"] for r in wrong),
                      "rate": concedes / len(wrong) if wrong else float("nan")}
    return out


def debater_cost_per_pair(debates: Mapping[str, Mapping]) -> tuple[float, float]:
    """(debate cost_match per pair for both arguments, one-sided cost_match per pair for its one argument)."""
    n = len(debates)
    both = sum(a.cost_match_usd for args in debates.values() for a in args.values()) / n
    return both, both / 2


def suggested_votes(condition_cost_per_pair: float, weak_cost_per_pair: float) -> int:
    """Odd number of weak-judge verdicts per order that costs closest to the condition (at least 1)."""
    ratio = condition_cost_per_pair / weak_cost_per_pair
    odd_below = max(1, int(ratio) if int(ratio) % 2 == 1 else int(ratio) - 1)
    return min((odd_below, odd_below + 2), key=lambda k: (abs(k - ratio), k))


def git_state(repo: Path) -> dict:
    def git(*args):
        try:
            return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
        except Exception:
            return None
    return {"commit": git("rev-parse", "--short", "HEAD"),
            "prompts_modified": bool(git("status", "--porcelain", "--", "src/debate_judge/prompts.py")),
            "tags_at_head": (git("tag", "--points-at", "HEAD") or "").split()}


# ---------------------------------------------------------------- stages


def run_stage(stage: str, pairs: Sequence[Mapping], *, chat_fn: ChatFn = None, workers: int = 32,
              progress: Callable[[str], None] = print) -> dict:
    """Run the dry run ("dry") or the pilot ("pilot") on the given pairs and return a summary dict."""
    if stage not in ("dry", "pilot"):
        raise ValueError("stage must be 'dry' or 'pilot'")
    prefix = stage
    n_debate = DRY_DEBATE_PAIRS if stage == "dry" else DEBATE_PILOT_PAIRS
    debate_pairs = list(pairs[:n_debate])
    conditions: dict[str, ConditionResult] = {}

    progress(f"[{stage}] weak judge (thinking off) on {len(pairs)} pairs")
    conditions["judge_none"] = run_judge(pairs, thinking="none", run=f"{prefix}_judge_none",
                                         condition="judge_alone", chat_fn=chat_fn, workers=workers)
    for level in THINKING_JUDGE_LEVELS:
        progress(f"[{stage}] thinking judge ({level}) on {len(pairs)} pairs")
        conditions[f"judge_{level}"] = run_judge(pairs, thinking=level, run=f"{prefix}_judge_{level}",
                                                 condition="thinking_judge", chat_fn=chat_fn, workers=workers)

    debates = {}
    for level in DEBATER_LEVELS:
        progress(f"[{stage}] debaters ({level}) on {len(debate_pairs)} pairs, both sides")
        debates[level] = run_debaters(debate_pairs, thinking=level, run=f"{prefix}_debater_{level}",
                                      chat_fn=chat_fn, workers=workers)
        args = {pid: arguments_for_judge(a) for pid, a in debates[level].items()}
        conditions[f"debate_{level}"] = run_judge(debate_pairs, thinking="none", run=f"{prefix}_judge_debate_{level}",
                                                  condition=f"debate_{level}", arguments=args,
                                                  chat_fn=chat_fn, workers=workers)
    one_sided = {p["pair_id"]: one_sided_arguments(p, debates["high"][p["pair_id"]]) for p in debate_pairs}
    progress(f"[{stage}] weak judge with one-sided argument on {len(debate_pairs)} pairs")
    conditions["one_sided"] = run_judge(debate_pairs, thinking="none", run=f"{prefix}_judge_one_sided",
                                        condition="one_sided", arguments=one_sided, chat_fn=chat_fn, workers=workers)

    progress(f"[{stage}] concession check on {2 * len(debate_pairs) * len(DEBATER_LEVELS)} arguments")
    concession_rows = run_concessions(debate_pairs, debates, run=f"{prefix}_concession", chat_fn=chat_fn,
                                      workers=workers)

    # ---- costs per pair, including the debater arguments each condition reads
    weak = conditions["judge_none"]
    debater_costs = {level: debater_cost_per_pair(debates[level]) for level in DEBATER_LEVELS}
    cost_per_pair = {name: c.cost_match_per_pair for name, c in conditions.items()}
    for level in DEBATER_LEVELS:
        cost_per_pair[f"debate_{level}"] += debater_costs[level][0]
    cost_per_pair["one_sided"] += debater_costs["high"][1]
    weak_verdict_cost = weak.cost_match_per_pair / 2  # one order
    k = {name: suggested_votes(cost / 2, weak_verdict_cost) for name, cost in cost_per_pair.items()
         if name != "judge_none"}

    # ---- go/no-go
    go_cmp = stats.paired_comparison(weak.correct, conditions[f"judge_{GO_THINKING_LEVEL}"].correct)
    rates = concession_rates(concession_rows)
    concession_ok = all(r["rate"] < MAX_CONCESSION_RATE for r in rates.values())

    debate_subset = {pid: weak.correct[pid] for pid in (p["pair_id"] for p in debate_pairs)}
    summary = {
        "stage": stage,
        "pairs": len(pairs),
        "debate_pairs": len(debate_pairs),
        "prompt_versions": {"judge": JUDGE_PROMPT_VERSION, "debater": DEBATER_PROMPT_VERSION,
                            "concession": CONCESSION_PROMPT_VERSION},
        "conditions": {
            name: {
                "n": c.n,
                "accuracy": str(stats.accuracy_ci(c.correct)) if c.n else None,
                "outcomes": c.outcomes,
                "incomplete_calls": c.incomplete_calls,
                "unparsed_verdicts": c.unparsed,
                "cost_usd": round(c.cost_usd, 6),
                "cost_match_per_pair_incl_debaters": round(cost_per_pair[name], 6),
                "suggested_votes_per_order": k.get(name),
            } for name, c in conditions.items()
        },
        "debater_cost_match_per_pair": {lvl: round(v[0], 6) for lvl, v in debater_costs.items()},
        "debater_incomplete": {lvl: sum(not a.complete for args in d.values() for a in args.values())
                               for lvl, d in debates.items()},
        "debater_letter_fixes": {lvl: sum(a.letter_fixes for args in d.values() for a in args.values())
                                 for lvl, d in debates.items()},
        "paired_vs_weak_judge": {
            name: str(stats.paired_comparison(
                debate_subset if name in ("debate_low", "debate_high", "one_sided") else weak.correct, c.correct))
            for name, c in conditions.items() if name != "judge_none"
        },
        "by_group_thinking_vs_weak": {
            g: str(cmp) for g, cmp in stats.paired_by_group(
                weak.correct, conditions[f"judge_{GO_THINKING_LEVEL}"].correct, pairs).items()
        },
        "concession_auto": rates,
        "go_no_go": {
            "rule": f"thinking judge ({GO_THINKING_LEVEL}) beats weak judge with paired 95% interval above zero, "
                    f"and wrong-side concession rate < {MAX_CONCESSION_RATE:.0%} at every debater effort",
            "thinking_beats_weak": go_cmp.b_better,
            "thinking_minus_weak": str(go_cmp),
            "concessions_ok_auto": concession_ok,
            "decision_auto": "GO (question 6)" if go_cmp.b_better and concession_ok else "NO-GO (switch to question 8)",
            "note": "Confirm the concession rate with Adrian's hand labels in concession_review.csv before deciding.",
        },
        "spend_usd": round(sum(c.cost_usd for c in conditions.values())
                           + sum(a.cost_usd for d in debates.values() for args in d.values() for a in args.values())
                           + sum(r["cost_usd"] for r in concession_rows), 6),
    }
    return {"summary": summary, "concession_rows": concession_rows}


def write_outputs(result: Mapping, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(result["summary"], indent=2, ensure_ascii=False) + "\n",
                                          encoding="utf-8")
    rows = result["concession_rows"]
    if rows:
        # utf-8-sig so Excel on Windows shows quotes and maths symbols correctly when Adrian labels by hand
        with open(out_dir / "concession_review.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=[k for k in rows[0] if k != "cost_usd"], extrasaction="ignore")
            w.writeheader()
            w.writerows(sorted(rows, key=lambda r: (r["debater_thinking"], r["assigned_correct"], r["pair_id"])))


__all__ = ["run_stage", "write_outputs", "suggested_votes", "concession_rates", "git_state",
           "WEAK_JUDGE_TEMPERATURE"]
