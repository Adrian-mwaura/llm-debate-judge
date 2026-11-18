"""Run the prompt dry run and/or the go/no-go pilot. See src/debate_judge/pilot.py.

    python scripts/run_pilot.py dry      # 20 dry-run pairs, about US$0.20; never reported
    python scripts/run_pilot.py pilot    # 200 pilot pairs (+ debaters on 30), about US$1.50-2

Before the pilot: freeze the prompts with a git tag (e.g. `git tag prompts-v1 && git push origin prompts-v1`).
The script refuses to run at peak price, or with uncommitted prompt changes, unless you pass the override flag.
Outputs: results/<stage>/summary.json and results/<stage>/concession_review.csv; call logs in logs/calls/<stage>_*.jsonl.
Add the printed spend to the budget ledger in docs/NOTES.md, and commit logs/ and results/.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from debate_judge import data, llm, pilot  # noqa: E402

LIMITS_USD = {"dry": 1.0, "pilot": 4.0}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["dry", "pilot"])
    ap.add_argument("--allow-peak", action="store_true", help="run even at peak (double) price")
    ap.add_argument("--allow-unfrozen", action="store_true", help="run with uncommitted or untagged prompts")
    ap.add_argument("--workers", type=int, default=32)
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    if llm.price_period(now) == "peak" and not args.allow_peak:
        sys.exit(f"It is peak price now ({now:%H:%M} UTC). Run off-peak (before 09:00, 12:00-14:00 or after 18:00 UTC+8), "
                 "or pass --allow-peak.")
    git = pilot.git_state(REPO)
    if git["prompts_modified"] and not args.allow_unfrozen:
        sys.exit("src/debate_judge/prompts.py has uncommitted changes. Commit and tag the prompts first.")
    if args.stage == "pilot" and not git["tags_at_head"] and not args.allow_unfrozen:
        sys.exit("No git tag on this commit. Freeze the prompts first: git tag prompts-v1 && git push origin prompts-v1")

    pairs = data.load_judgebench()
    subset = data.dry_run_pairs(pairs) if args.stage == "dry" else data.pilot_pairs(pairs)
    print(f"{args.stage}: {len(subset)} pairs, commit {git['commit']}, tags {git['tags_at_head'] or 'none'}")

    result = pilot.run_stage(args.stage, subset, workers=args.workers)
    summary = result["summary"]
    summary["git"] = git
    summary["started_utc"] = now.isoformat()
    out = REPO / "results" / args.stage
    pilot.write_outputs(result, out)

    print(json.dumps(summary["go_no_go"], indent=2))
    for name, c in summary["conditions"].items():
        print(f"  {name:12s} {c['accuracy']}  incomplete={c['incomplete_calls']} unparsed={c['unparsed_verdicts']} "
              f"cost/pair={c['cost_match_per_pair_incl_debaters']:.5f} k={c['suggested_votes_per_order']}")
    print(f"Spend this run: US${summary['spend_usd']:.4f} (add it to the budget ledger)")
    print(f"Wrote {out / 'summary.json'} and {out / 'concession_review.csv'}")
    if summary["spend_usd"] > LIMITS_USD[args.stage]:
        print(f"WARNING: spend is above the expected US${LIMITS_USD[args.stage]:.2f} for this stage.")


if __name__ == "__main__":
    main()
