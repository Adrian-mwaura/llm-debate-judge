"""Recompute JudgeBench scores, consistency and position preference from published judge outputs.

This backs the table in docs/research/question_selection.md. It makes no API calls.

The JudgeBench leaderboard publishes each judge's raw outputs here:
  https://huggingface.co/spaces/ScalerLab/JudgeBench/tree/main/outputs
Download the .jsonl files you want into one folder, then run:
  python docs/research/judgebench_published_scores.py <folder>

Scoring follows the leaderboard's own rule (utils.py in that Space): each pair is judged in both
answer orders, and it counts as correct only if the two verdicts together favour the labelled response.
"""
import glob
import json
import os
import sys

FLIP = {"A>B": "B>A", "B>A": "A>B"}


def category(source: str) -> str:
    if source.startswith("mmlu-pro"):
        return "knowledge"
    if source.startswith("livebench-reasoning"):
        return "reasoning"
    if source.startswith("livebench-math"):
        return "math"
    if source.startswith("livecodebench"):
        return "coding"
    return source


def score_file(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        pairs = [json.loads(line) for line in f if line.strip()]
    n = len(pairs)
    out = {"n": n, "correct": 0, "both_right": 0, "both_wrong": 0, "split": 0, "other": 0,
           "split_first_slot": 0, "by_category": {}}
    for p in pairs:
        label = p["label"]
        j1, j2 = p["judgments"]
        d1 = j1["decision"] if j1 else None
        d2_raw = j2["decision"] if j2 else None
        d2 = FLIP.get(d2_raw, d2_raw)  # map the swapped-order verdict back to the original order
        net = sum((d == label) - (d == FLIP[label]) for d in (d1, d2))
        ok = net > 0
        out["correct"] += ok
        cat = out["by_category"].setdefault(category(p["source"]), [0, 0])
        cat[0] += ok
        cat[1] += 1
        if d1 == label and d2 == label:
            out["both_right"] += 1
        elif d1 == FLIP[label] and d2 == FLIP[label]:
            out["both_wrong"] += 1
        elif {d1, d2} == {label, FLIP[label]}:
            out["split"] += 1  # same position chosen in both orders
            out["split_first_slot"] += d1 == "A>B"
        else:
            out["other"] += 1  # a tie or a missing verdict in at least one order
    return out


def main(folder: str) -> None:
    for path in sorted(glob.glob(os.path.join(folder, "*.jsonl"))):
        r = score_file(path)
        n = r["n"]
        pct = lambda k: 100 * r[k] / n  # noqa: E731
        cats = "  ".join(f"{k}={100 * v[0] / v[1]:.1f} (n={v[1]})" for k, v in sorted(r["by_category"].items()))
        print(os.path.basename(path))
        print(f"  n={n}  score={pct('correct'):.1f}  both_right={pct('both_right'):.1f}  "
              f"both_wrong={pct('both_wrong'):.1f}  split={pct('split'):.1f}  other={pct('other'):.1f}  "
              f"first slot chosen in {r['split_first_slot']} of {r['split']} splits")
        print(f"  {cats}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
