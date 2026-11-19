"""The full run: every condition on the 600 report pairs. Run it with scripts/run_full.py.

Two groups, so the shared part can run before the go/no-go is final:

- "shared" (needed by question 6 and by the question-8 fallback):
  judge_none (weak judge alone), votes (weak judge, up to MAX_VOTE_K verdicts per order; majority of the first k
  for every odd k), judge_low and judge_high (thinking judge alone).
- "debate" (question 6 only; needs go_no_go_final = GO in results/pilot/summary.json):
  debate_low and debate_high (weak judge reading both debaters), one_sided (weak judge reading one of the `high`
  arguments), and the automatic concession check on every argument (analysis only, not in any condition's cost).

Everything goes through judge_pair()/debate_arguments(), so every call is cached: the pilot pairs' calls are reused,
vote sample 0 is the judge-alone call, and a rerun after an interruption only pays for what is missing.

Output: results/full/pairs.jsonl, one record per (pair, condition): decisions, correct, outcome and cost_match_usd
(including the debater arguments the judge read). make_table.py builds the results table from it.
"""
from __future__ import annotations

import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from debate_judge import data
from debate_judge.debate import arguments_for_judge, check_concession, correct_side, debate_arguments, one_sided_arguments
from debate_judge.judge import judge_pair
from debate_judge.pilot import WEAK_JUDGE_TEMPERATURE

MAX_VOTE_K = 9                   # largest k the pilot's cost matching needs (debate_high); proposal cap is 15
VOTE_KS = (1, 3, 5, 7, 9)        # majority of the first k samples per order; k=1 is the weak judge alone
SHARED = ("judge_none", "votes", "judge_low", "judge_high")
DEBATE = ("debate_high", "debate_low", "one_sided")   # debate_high first: one_sided reuses its arguments
GROUPS = {"shared": SHARED, "debate": DEBATE, "all": SHARED + DEBATE}
RUN_PREFIX = "full"
BUDGET_MARGIN = 1.25             # need 25% more balance than the estimate before starting a condition

ChatFn = Callable[..., Any] | None


def _parallel(fn: Callable, items: Sequence, workers: int) -> list:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, items))


def _record(pair: Mapping, condition: str, decisions: Sequence, cost_match: float, cost_usd: float,
            extra: Mapping | None = None) -> dict:
    s = data.score_pair(pair["label"], decisions)
    return {"pair_id": pair["pair_id"], "category": pair["category"], "group": pair["group"], "split": pair["split"],
            "label": pair["label"], "condition": condition, "decisions": list(decisions), "correct": s.correct,
            "outcome": s.outcome, "first_slot": s.first_slot, "cost_match_usd": cost_match, "cost_usd": cost_usd,
            **(extra or {})}


# ---------------------------------------------------------------- conditions


def run_judge_alone(pairs, thinking: str, *, chat_fn: ChatFn, workers: int) -> list[dict]:
    temperature = WEAK_JUDGE_TEMPERATURE if thinking == "none" else None
    cond = "judge_none" if thinking == "none" else f"judge_{thinking}"

    def one(pair):
        v = judge_pair(pair, thinking=thinking, run=f"{RUN_PREFIX}_{cond}", condition=cond,
                       temperature=temperature, chat_fn=chat_fn)
        return _record(pair, cond, v.decisions, v.cost_match_usd, v.cost_usd)

    return _parallel(one, pairs, workers)


def run_votes(pairs, *, chat_fn: ChatFn, workers: int, max_k: int = MAX_VOTE_K, ks: Sequence[int] = VOTE_KS) -> list[dict]:
    """Weak judge with sample=0..max_k-1 per pair (both orders each), then majority of the first k for each k in ks."""
    jobs = [(pair, s) for pair in pairs for s in range(max_k)]

    def one(job):
        pair, s = job
        return pair["pair_id"], s, judge_pair(pair, thinking="none", run=f"{RUN_PREFIX}_votes", condition="votes",
                                              sample=s, temperature=WEAK_JUDGE_TEMPERATURE, chat_fn=chat_fn)

    by_pair: dict[Any, dict[int, Any]] = {}
    for pid, s, v in _parallel(one, jobs, workers):
        by_pair.setdefault(pid, {})[s] = v
    out = []
    for pair in pairs:
        votes = by_pair[pair["pair_id"]]
        for k in ks:
            first = [votes[s] for s in range(k)]
            decisions = [data.majority(v.decisions[order] for v in first) for order in (0, 1)]
            out.append(_record(pair, f"votes_k{k}", decisions,
                               sum(v.cost_match_usd for v in first), sum(v.cost_usd for v in first), {"k": k}))
    return out


def run_debates(pairs, *, chat_fn: ChatFn, workers: int) -> tuple[list[dict], list[dict]]:
    """debate_high, debate_low and one_sided records, plus one concession-check row per argument."""
    records, concessions = [], []
    debates = {}
    for level in ("high", "low"):
        debates[level] = dict(zip((p["pair_id"] for p in pairs), _parallel(
            lambda p: debate_arguments(p, thinking=level, run=f"{RUN_PREFIX}_debater_{level}", chat_fn=chat_fn),
            pairs, workers)))

        def judge_debate(pair, level=level):
            args = debates[level][pair["pair_id"]]
            v = judge_pair(pair, thinking="none", run=f"{RUN_PREFIX}_judge_debate_{level}", condition=f"debate_{level}",
                           arguments=arguments_for_judge(args), temperature=WEAK_JUDGE_TEMPERATURE, chat_fn=chat_fn)
            arg_match = sum(a.cost_match_usd for a in args.values())
            arg_usd = sum(a.cost_usd for a in args.values())
            return _record(pair, f"debate_{level}", v.decisions, v.cost_match_usd + arg_match, v.cost_usd + arg_usd,
                           {"arguments_complete": sum(a.complete for a in args.values()),
                            "letter_fixes": sum(a.letter_fixes for a in args.values())})

        records += _parallel(judge_debate, pairs, workers)

    def judge_one_sided(pair):
        args = debates["high"][pair["pair_id"]]
        shown = one_sided_arguments(pair, args)
        v = judge_pair(pair, thinking="none", run=f"{RUN_PREFIX}_judge_one_sided", condition="one_sided",
                       arguments=shown, temperature=WEAK_JUDGE_TEMPERATURE, chat_fn=chat_fn)
        side = next(iter(shown), None)
        # the reused argument's cost counts toward one_sided, as agreed in the PR #10 review
        arg = args[side] if side else None
        return _record(pair, "one_sided", v.decisions,
                       v.cost_match_usd + (arg.cost_match_usd if arg else 0.0),
                       v.cost_usd, {"shown_side": side, "shown_correct": side == correct_side(pair) if side else None})

    records += _parallel(judge_one_sided, pairs, workers)

    jobs = [(level, pair, side, arg) for level, d in debates.items() for pair in pairs
            for side, arg in d[pair["pair_id"]].items()]

    def concede(job):
        level, pair, side, arg = job
        c = check_concession(arg, run=f"{RUN_PREFIX}_concession", chat_fn=chat_fn)
        return {"pair_id": pair["pair_id"], "debater_thinking": level, "side": side,
                "assigned_correct": side == correct_side(pair), "complete": arg.complete,
                "auto_verdict": c.verdict, "cost_usd": c.cost_usd}

    concessions = _parallel(concede, jobs, workers)
    return records, concessions


# ---------------------------------------------------------------- budget


def estimate_cost(pilot_summary: Mapping, condition: str, n_new_pairs: int, max_k: int = MAX_VOTE_K) -> float:
    """List-price estimate for running `condition` on pairs the pilot did not already pay for.

    Uses the pilot's measured cost_match per pair. Real spend off-peak is at most this (cache hits are cheaper).
    """
    c = pilot_summary["conditions"]
    per_pair = {
        "judge_none": c["judge_none"]["cost_match_per_pair_incl_debaters"],
        "judge_low": c["judge_low"]["cost_match_per_pair_incl_debaters"],
        "judge_high": c["judge_high"]["cost_match_per_pair_incl_debaters"],
        "debate_high": c["debate_high"]["cost_match_per_pair_incl_debaters"],
        "debate_low": c["debate_low"]["cost_match_per_pair_incl_debaters"],
        # one_sided reuses the high argument, so only its judge calls are new
        "one_sided": c["one_sided"]["cost_match_per_pair_incl_debaters"] - pilot_summary["debater_cost_match_per_pair"]["high"] / 2,
        # votes: samples 1..max_k-1 are new (sample 0 is judge_none)
        "votes": (max_k - 1) * c["judge_none"]["cost_match_per_pair_incl_debaters"],
    }[condition]
    return per_pair * n_new_pairs


def balance_usd() -> float | None:
    """The DeepSeek account balance in USD (an unbilled, read-only call, allowed by AGENTS.md). None if unavailable."""
    from dotenv import load_dotenv

    from debate_judge import llm
    load_dotenv(llm.REPO_ROOT / ".env")
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        return None
    base = os.environ.get("DEEPSEEK_BASE_URL", llm.DEFAULT_BASE_URL).rstrip("/")
    req = urllib.request.Request(base + "/user/balance", headers={"Authorization": f"Bearer {key}",
                                                                  "Accept": "application/json"})
    try:
        infos = json.load(urllib.request.urlopen(req, timeout=30))["balance_infos"]
    except Exception:
        return None
    usd = [float(i["total_balance"]) for i in infos if i.get("currency") == "USD"]
    return usd[0] if usd else None


# ---------------------------------------------------------------- driver


def run_conditions(pairs: Sequence[Mapping], conditions: Sequence[str], *, out_dir: Path, chat_fn: ChatFn = None,
                   workers: int = 32, budget_check: Callable[[str], None] | None = None,
                   progress: Callable[[str], None] = print) -> dict[str, list[dict]]:
    """Run the conditions in order, saving after each, and return {condition: records}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    done: dict[str, list[dict]] = {}
    remaining = list(conditions)
    debate_done = False
    for cond in remaining:
        if cond in ("debate_low", "one_sided") and debate_done:
            continue  # produced together with debate_high
        if budget_check:
            budget_check(cond)
        progress(f"[full] {cond} on {len(pairs)} pairs")
        if cond == "judge_none":
            recs = run_judge_alone(pairs, "none", chat_fn=chat_fn, workers=workers)
        elif cond in ("judge_low", "judge_high"):
            recs = run_judge_alone(pairs, cond.split("_")[1], chat_fn=chat_fn, workers=workers)
        elif cond == "votes":
            recs = run_votes(pairs, chat_fn=chat_fn, workers=workers)
        elif cond in DEBATE:
            recs, concessions = run_debates(pairs, chat_fn=chat_fn, workers=workers)
            write_jsonl(out_dir / "concessions.jsonl", concessions)
            debate_done = True
        else:
            raise ValueError(f"unknown condition {cond!r}")
        for r in recs:
            done.setdefault(r["condition"], []).append(r)
        save_records(out_dir / "pairs.jsonl", recs)
    return done


def write_jsonl(path: Path, rows: Sequence[Mapping]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def save_records(path: Path, new: Sequence[Mapping]) -> None:
    """Merge new records into pairs.jsonl, replacing any earlier record for the same (pair, condition)."""
    keep = {(r["pair_id"], r["condition"]): r for r in load_records(path)}
    for r in new:
        keep[(r["pair_id"], r["condition"])] = r
    write_jsonl(path, sorted(keep.values(), key=lambda r: (r["condition"], r["pair_id"])))


def go_decision(pilot_summary: Mapping) -> str | None:
    final = pilot_summary.get("go_no_go_final")
    return final["decision"] if final else None
