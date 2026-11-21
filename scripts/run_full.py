"""The full run on the 600 report pairs. See src/debate_judge/full.py.

    python scripts/run_full.py estimate          # no API calls: cost estimate per condition vs. the balance
    python scripts/run_full.py shared            # weak judge, votes (k up to 11), thinking judge low/high
    python scripts/run_full.py debate            # debate high/low, one-sided, concession check (needs final GO)
    python scripts/run_full.py all

Checks: prompts frozen (tag prompts-v1; prompts.py, judge.py, debate.py unchanged) at start, and before EACH condition
off-peak price and enough balance (estimate x 1.25; the debate group's estimate includes the concession checks). The debate group also needs `go_no_go_final` = GO in
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

from debate_judge import data, full, pilot  # noqa: E402


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

    concession_per_call = full.concession_cost_per_call(REPO / "logs" / "calls" / "pilot_concession.jsonl")

    def estimate(cond: str) -> float:
        # Votes 2..k were never run in the pilot, so they are new on every report pair.
        n = n_new_debate if cond in full.DEBATE + (full.CONCESSION,) else len(report) if cond == "votes" else n_new
        return full.estimate_cost(pilot_summary, cond, n, concession_per_call=concession_per_call)

    # The debate group also runs the concession checks, so its spend and budget include them.
    debate_items = full.DEBATE + (full.CONCESSION,)

    conds = full.GROUPS["all" if args.group == "estimate" else args.group]
    if args.group == "estimate":
        bal = full.balance_usd()
        total = 0.0
        for c in tuple(conds) + (full.CONCESSION,):
            e = estimate(c)
            total += e
            print(f"  {c:16s} about US${e:.2f}")
        print(f"Total about US${total:.2f} at list price. Balance: {'unknown' if bal is None else f'US${bal:.2f}'}.")
        print(f"Shared group about US${sum(estimate(c) for c in full.SHARED):.2f}; "
              f"debate group about US${sum(estimate(c) for c in debate_items):.2f} (incl. concession checks).")
        return

    def peak_check() -> None:
        full.peak_check(datetime.now(timezone.utc), args.allow_peak)

    now = datetime.now(timezone.utc)
    peak_check()
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
        """Runs before every condition: the peak check (Adrian's PR #15 review), then the balance check."""
        peak_check()
        if args.skip_budget_check:
            return
        bal = full.balance_usd()
        need = estimate(cond) * full.BUDGET_MARGIN
        if cond == "debate_high":  # debate_high also runs debate_low, one_sided and the concession checks
            need = sum(estimate(c) for c in debate_items) * full.BUDGET_MARGIN
        if bal is None:
            sys.exit("Could not read the DeepSeek balance; rerun with --skip-budget-check if you are sure.")
        if bal < need:
            sys.exit(f"Balance US${bal:.2f} is below the US${need:.2f} needed for {cond} (estimate x {full.BUDGET_MARGIN}). "
                     "Top up first. Finished conditions are saved and cached.")
        print(f"  budget ok for {cond}: balance US${bal:.2f}, need about US${need:.2f}")

    out = REPO / "results" / "full"
    print(f"full run ({args.group}): {len(report)} report pairs, commit {git['commit']}, frozen {git['frozen']}")
    done = full.run_conditions(report, conds, out_dir=out, workers=args.workers, budget_check=budget_check)

    spend_conditions = full.run_spend(done)
    # The concession checks are not in any condition's records; concessions.jsonl is rewritten by each debate run.
    spend_concessions = (sum(r["cost_usd"] for r in full.load_records(out / "concessions.jsonl"))
                         if any(c in done for c in full.DEBATE) else 0.0)
    spend = spend_conditions + spend_concessions
    run_info = {"group": args.group, "started_utc": now.isoformat(), "git": git, "pairs": len(report),
                "conditions": sorted(done), "spend_usd_conditions": round(spend_conditions, 4),
                "spend_usd_concession_checks": round(spend_concessions, 4), "spend_usd_this_run": round(spend, 4)}
    (out / f"run_{args.group}.json").write_text(json.dumps(run_info, indent=2) + "\n", encoding="utf-8")
    for cond in sorted(done):
        recs = done[cond]
        acc = sum(r["correct"] for r in recs) / len(recs)
        cpp = sum(r["cost_match_usd"] for r in recs) / len(recs)
        print(f"  {cond:12s} accuracy {100 * acc:5.1f}  cost/pair {cpp:.5f}  (n={len(recs)})")
    print(f"Spend this run about US${spend:.4f} (conditions {spend_conditions:.4f}, concession checks {spend_concessions:.4f}; "
          "cache hits are free). Add it to the budget ledger; commit logs/ and results/.")


if __name__ == "__main__":
    main()
