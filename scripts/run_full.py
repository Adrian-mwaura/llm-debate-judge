"""The full run on the 600 report pairs. See src/debate_judge/full.py.

    python scripts/run_full.py estimate          # no API calls: cost estimate per condition vs. the balance
    python scripts/run_full.py shared            # weak judge, votes (k up to 11), thinking judge low/high
    python scripts/run_full.py debate            # debate high/low, one-sided, concession check (needs final GO)
    python scripts/run_full.py all

Checks before any paid call: off-peak price, prompts frozen (tag prompts-v1; prompts.py, judge.py, debate.py unchanged),
and for each condition enough balance (estimate x 1.25). The debate group also needs `go_no_go_final` = GO in
results/pilot/summary.json (run `python scripts/run_pilot.py decide` first). Overrides: --allow-peak, --allow-unfrozen,
--skip-budget-check, --without-final-go. Every call is cached, so an interrupted run can simply be started again.
Outputs: results/full/pairs.jsonl (+ concessions.jsonl) and logs/calls/full_*.jsonl. Add the spend to the budget ledger.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from debate_judge import data, full, llm, pilot  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("group", choices=["estimate", "shared", "debate", "all"])
    ap.add_argument("--allow-peak", action="store_true")
    ap.add_argument("--allow-unfrozen", action="store_true")
    ap.add_argument("--skip-budget-check", action="store_true")
    ap.add_argument("--without-final-go", action="store_true", help="run the debate group before decide (avoid)")
    ap.add_argument("--workers", type=int, default=32)
    args = ap.parse_args()

    pilot_summary = json.loads((REPO / "results" / "pilot" / "summary.json").read_text(encoding="utf-8"))
    pairs = data.load_judgebench()
    report = data.report_pairs(pairs)
    pilot_ids = {p["pair_id"] for p in data.pilot_pairs(pairs)}
    n_new = len([p for p in report if p["pair_id"] not in pilot_ids])
    # The pilot ran the debate conditions on only 30 pairs, so almost every debate pair is new.
    n_new_debate = len(report) - pilot_summary.get("debate_pairs", 0)

    def estimate(cond: str) -> float:
        # Votes 2..k were never run in the pilot, so they are new on every report pair.
        n = n_new_debate if cond in full.DEBATE else len(report) if cond == "votes" else n_new
        return full.estimate_cost(pilot_summary, cond, n)

    conds = full.GROUPS["all" if args.group == "estimate" else args.group]
    if args.group == "estimate":
        bal = full.balance_usd()
        total = 0.0
        for c in conds:
            e = estimate(c)
            total += e
            print(f"  {c:12s} about US${e:.2f}")
        print(f"Total about US${total:.2f} at list price. Balance: {'unknown' if bal is None else f'US${bal:.2f}'}.")
        print(f"Shared group about US${sum(estimate(c) for c in full.SHARED):.2f}; "
              f"debate group about US${sum(estimate(c) for c in full.DEBATE):.2f}.")
        return

    now = datetime.now(timezone.utc)
    if llm.price_period(now) == "peak" and not args.allow_peak:
        sys.exit(f"It is peak price now ({now:%H:%M} UTC). Run off-peak (before 09:00, 12:00-14:00 or after 18:00 UTC+8).")
    git = pilot.git_state(REPO)
    if not git["frozen"] and not args.allow_unfrozen:
        sys.exit(f"Not frozen against {git['freeze_tag']}: {git}")
    if any(c in full.DEBATE for c in conds) and not args.without_final_go:
        decision = full.go_decision(pilot_summary)
        if decision is None:
            sys.exit("No final go/no-go yet. Adrian fills hand_label, then: python scripts/run_pilot.py decide")
        if not decision.startswith("GO"):
            sys.exit(f"The final decision is {decision!r}; the debate group belongs to question 6 only.")

    def budget_check(cond: str) -> None:
        if args.skip_budget_check:
            return
        bal = full.balance_usd()
        need = estimate(cond) * full.BUDGET_MARGIN
        if cond == "debate_high":  # debate_high also runs debate_low and one_sided
            need = sum(estimate(c) for c in full.DEBATE) * full.BUDGET_MARGIN
        if bal is None:
            sys.exit("Could not read the DeepSeek balance; rerun with --skip-budget-check if you are sure.")
        if bal < need:
            sys.exit(f"Balance US${bal:.2f} is below the US${need:.2f} needed for {cond} (estimate x {full.BUDGET_MARGIN}). "
                     "Top up first. Finished conditions are saved and cached.")
        print(f"  budget ok for {cond}: balance US${bal:.2f}, need about US${need:.2f}")

    out = REPO / "results" / "full"
    print(f"full run ({args.group}): {len(report)} report pairs, commit {git['commit']}, frozen {git['frozen']}")
    done = full.run_conditions(report, conds, out_dir=out, workers=args.workers, budget_check=budget_check)

    spend = sum(r["cost_usd"] for recs in done.values() for r in recs if not r["condition"].startswith("votes_k")
                or r.get("k") == full.MAX_VOTE_K)
    run_info = {"group": args.group, "started_utc": now.isoformat(), "git": git, "pairs": len(report),
                "conditions": sorted(done), "spend_usd_this_run": round(spend, 4)}
    (out / f"run_{args.group}.json").write_text(json.dumps(run_info, indent=2) + "\n", encoding="utf-8")
    for cond in sorted(done):
        recs = done[cond]
        acc = sum(r["correct"] for r in recs) / len(recs)
        cpp = sum(r["cost_match_usd"] for r in recs) / len(recs)
        print(f"  {cond:12s} accuracy {100 * acc:5.1f}  cost/pair {cpp:.5f}  (n={len(recs)})")
    print(f"Spend this run about US${spend:.4f} (cache hits are free). Add it to the budget ledger; commit logs/ and results/.")


if __name__ == "__main__":
    main()
