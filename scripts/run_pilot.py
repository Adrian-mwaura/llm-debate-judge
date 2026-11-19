"""Run the prompt dry run, the go/no-go pilot, and the final decision. See src/debate_judge/pilot.py.

    python scripts/run_pilot.py dry      # 20 dry-run pairs, about US$0.20; never reported
    python scripts/run_pilot.py pilot    # 200 pilot pairs (+ debaters on 30), about US$1.50-2
    python scripts/run_pilot.py decide   # no API calls: reads the hand labels, writes the final go/no-go

Freeze before the pilot: `git tag prompts-v1 && git push origin prompts-v1`. The pilot only runs if the tag exists and
prompts.py, judge.py and debate.py are identical to the tag with no uncommitted changes; the check is recorded in
summary.json. It also refuses peak price. Overrides: --allow-peak, --allow-unfrozen.
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


def run_decide(stage: str) -> None:
    out = REPO / "results" / stage
    summary_path = out / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    rows = pilot.read_concession_csv(out / "concession_review.csv")
    try:
        final = pilot.decide(summary, rows)
    except ValueError as e:
        sys.exit(f"Cannot decide yet: {e}")
    final["decided_utc"] = datetime.now(timezone.utc).isoformat()
    summary["go_no_go_final"] = final
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in final.items() if k != "hand_vs_auto_agreement"}, indent=2))
    a = final["hand_vs_auto_agreement"]
    print(f"Hand labels agree with the automatic check on {a['agree']} of {a['of']} wrong-side arguments.")
    print(f"Wrote go_no_go_final into {summary_path}. Record the decision in docs/NOTES.md.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["dry", "pilot", "decide"])
    ap.add_argument("--allow-peak", action="store_true", help="run even at peak (double) price")
    ap.add_argument("--allow-unfrozen", action="store_true", help="run although the frozen files differ from the tag")
    ap.add_argument("--workers", type=int, default=32)
    args = ap.parse_args()

    if args.stage == "decide":
        run_decide("pilot")
        return

    now = datetime.now(timezone.utc)
    if llm.price_period(now) == "peak" and not args.allow_peak:
        sys.exit(f"It is peak price now ({now:%H:%M} UTC). Run off-peak (before 09:00, 12:00-14:00 or after 18:00 UTC+8), "
                 "or pass --allow-peak.")
    git = pilot.git_state(REPO)
    if args.stage == "pilot" and not git["frozen"] and not args.allow_unfrozen:
        if not git["tag_exists"]:
            sys.exit(f"Tag {git['freeze_tag']} does not exist. Freeze first: "
                     f"git tag {git['freeze_tag']} && git push origin {git['freeze_tag']}")
        sys.exit(f"{', '.join(git['frozen_files'])} differ from tag {git['freeze_tag']} "
                 f"(same as tag: {git['frozen_files_same_as_tag']}, uncommitted changes: "
                 f"{git['frozen_files_uncommitted_changes']}). Results would not come from the frozen code.")

    pairs = data.load_judgebench()
    subset = data.dry_run_pairs(pairs) if args.stage == "dry" else data.pilot_pairs(pairs)
    print(f"{args.stage}: {len(subset)} pairs, commit {git['commit']}, frozen against {git['freeze_tag']}: {git['frozen']}")

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
    if summary["conditions_over_vote_cap"]:
        print(f"WARNING: these conditions need more than {pilot.MAX_VOTES} votes per order to match cost: "
              f"{summary['conditions_over_vote_cap']}")
    print(f"Spend this run: US${summary['spend_usd']:.4f} (add it to the budget ledger)")
    print(f"Wrote {out / 'summary.json'} and {out / 'concession_review.csv'}")
    if summary["spend_usd"] > LIMITS_USD[args.stage]:
        print(f"WARNING: spend is above the expected US${LIMITS_USD[args.stage]:.2f} for this stage.")


if __name__ == "__main__":
    main()
