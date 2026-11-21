"""Rebuild the main results table, the hypothesis tests and the plot from the committed results. No API calls.

    python scripts/make_table.py

Reads results/full/pairs.jsonl. Writes results/full/table.md, results/full/table.csv and
results/full/accuracy_vs_cost.png. See src/debate_judge/table.py for what each number is.
"""
import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from debate_judge import data, full, table  # noqa: E402


def main() -> None:
    out = REPO / "results" / "full"
    records = full.load_records(out / "pairs.jsonl")
    if not records:
        sys.exit(f"No records in {out / 'pairs.jsonl'}. Run scripts/run_full.py first.")
    conds = table.by_condition(records)
    ids = set.intersection(*(set(v) for v in conds.values()))
    pairs_by_id = {r["pair_id"]: r for r in records}  # records carry category, group and split

    rows = table.condition_rows(conds, ids)
    comp = table.comparisons(conds, pairs_by_id)

    try:
        pilot_ids = {p["pair_id"] for p in data.pilot_pairs(data.load_judgebench())}
        rest = {pid for pid in ids if pid not in pilot_ids}
        check = table.comparisons(conds, pairs_by_id, restrict=rest)
    except Exception as e:  # no dataset available: the main table still builds
        print(f"Skipping the non-pilot check: {e}")
        check, rest = None, set()

    (out / "table.md").write_text(table.markdown(rows, comp, check, len(rest)), encoding="utf-8")
    with open(out / "table.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(table.csv_rows(rows))
    table.plot(rows, out / "accuracy_vs_cost.png")
    print((out / "table.md").read_text(encoding="utf-8"))
    print(f"Wrote {out / 'table.md'}, {out / 'table.csv'} and {out / 'accuracy_vs_cost.png'}")


if __name__ == "__main__":
    main()
