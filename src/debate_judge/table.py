"""The main results table, the hypothesis tests and the accuracy-vs-cost plot, from results/full/pairs.jsonl.

No API calls: everything is computed from the committed per-pair records, so `python scripts/make_table.py`
rebuilds every number in the report from a fresh clone.

- Table 1: every condition on the same pairs: accuracy with a 95% Wilson interval, mean cost per pair
  (cost_match_usd, off-peak list price, including the debater arguments the judge read), and the split rate
  (same shown position in both orders).
- Same-cost comparisons (the proposal's rule): each method against votes_k<k> for the smallest odd k whose mean
  cost per pair is at least the method's (full.matched_k), with Newcombe's paired interval and McNemar's test.
  H1, the primary test: debate_high against its same-cost votes. Everything else is exploratory (no multiplicity
  correction), as agreed in Adrian's PR #11 review.
- H2: debate_high against debate_low. H3: the H1 comparison by group (knowledge, rmc).
- The same comparisons on the 400 report pairs outside the pilot, as the check the report promises.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

from debate_judge import stats
from debate_judge.full import VOTE_KS, matched_k

PRIMARY = "debate_high"
METHODS = ("debate_high", "debate_low", "one_sided", "judge_low", "judge_high")
ORDER = ("judge_none",) + tuple(f"votes_k{k}" for k in VOTE_KS if k > 1) + METHODS
LABELS = {
    "judge_none": "Weak judge alone (thinking off)",
    "debate_high": "Weak judge + debate (debaters `high`)",
    "debate_low": "Weak judge + debate (debaters `low`)",
    "one_sided": "Weak judge + one-sided argument (`high`)",
    "judge_low": "Thinking judge alone (`low`)",
    "judge_high": "Thinking judge alone (`high`)",
    **{f"votes_k{k}": f"Weak judge, {k} votes per order" for k in VOTE_KS if k > 1},
}


def by_condition(records: Iterable[Mapping]) -> dict[str, dict[Any, Mapping]]:
    out: dict[str, dict[Any, Mapping]] = defaultdict(dict)
    for r in records:
        out[r["condition"]][r["pair_id"]] = r
    return dict(out)


def _shared_ids(conds: Mapping[str, Mapping], names: Iterable[str], restrict: set | None) -> set:
    ids = None
    for n in names:
        s = set(conds[n])
        ids = s if ids is None else ids & s
    ids = ids or set()
    return ids & restrict if restrict is not None else ids


def _correct(conds, name, ids) -> dict:
    return {pid: bool(conds[name][pid]["correct"]) for pid in ids}


def mean_cost(conds, name, ids) -> float:
    return sum(conds[name][pid]["cost_match_usd"] for pid in ids) / len(ids)


def condition_rows(conds: Mapping[str, Mapping], ids: set) -> list[dict]:
    rows = []
    for name in ORDER:
        if name not in conds:
            continue
        a = stats.accuracy_ci(_correct(conds, name, ids))
        splits = sum(conds[name][pid]["outcome"] == "split" for pid in ids)
        rows.append({"condition": name, "label": LABELS.get(name, name), "n": a.n, "accuracy": a.accuracy,
                     "ci_low": a.ci_low, "ci_high": a.ci_high, "cost_per_pair": mean_cost(conds, name, ids),
                     "split_rate": splits / a.n})
    return rows


def same_cost_votes(conds: Mapping[str, Mapping], method: str, ids: set) -> str | None:
    """The votes condition that matches `method` under the proposal's rule, measured on these pairs."""
    if "votes_k1" not in conds:
        return None
    weak = mean_cost(conds, "votes_k1", ids)
    k = matched_k(mean_cost(conds, method, ids), weak, [k for k in VOTE_KS if f"votes_k{k}" in conds])
    return f"votes_k{k}" if k is not None else None


def comparisons(conds: Mapping[str, Mapping], pairs_by_id: Mapping[Any, Mapping] | None = None,
                restrict: set | None = None) -> dict[str, Any]:
    """Same-cost comparisons, H1 (primary), H2 and H3. `restrict` limits them to a set of pair ids."""
    out: dict[str, Any] = {"same_cost": {}, "notes": []}
    for method in METHODS:
        if method not in conds:
            continue
        ids = _shared_ids(conds, [method, "votes_k1"] + [f"votes_k{k}" for k in VOTE_KS if f"votes_k{k}" in conds],
                          restrict)
        if not ids:
            continue
        votes = same_cost_votes(conds, method, ids)
        if votes is None:
            out["notes"].append(f"{method}: costs more than the largest vote count run; no same-cost baseline.")
            continue
        cmp = stats.paired_comparison(_correct(conds, votes, ids), _correct(conds, method, ids))
        out["same_cost"][method] = {"baseline": votes, "method_cost": mean_cost(conds, method, ids),
                                    "baseline_cost": mean_cost(conds, votes, ids), "comparison": cmp,
                                    "role": "H1 (primary)" if method == PRIMARY else "exploratory"}
    if "debate_high" in conds and "debate_low" in conds:
        ids = _shared_ids(conds, ["debate_high", "debate_low"], restrict)
        out["H2"] = stats.paired_comparison(_correct(conds, "debate_low", ids), _correct(conds, "debate_high", ids))
    h1 = out["same_cost"].get(PRIMARY)
    if h1 and pairs_by_id:
        ids = _shared_ids(conds, [PRIMARY, h1["baseline"]], restrict)
        pairs = [pairs_by_id[pid] for pid in ids]
        out["H3"] = stats.paired_by_group(_correct(conds, h1["baseline"], ids), _correct(conds, PRIMARY, ids), pairs)
    return out


# ---------------------------------------------------------------- formatting


def _pct(x: float) -> str:
    return f"{100 * x:.1f}"


def markdown(rows: Sequence[Mapping], comp: Mapping, check: Mapping | None, n_check: int | None) -> str:
    lines = ["# Main results", "",
             "Generated by `python scripts/make_table.py` from `results/full/pairs.jsonl`. Do not edit by hand.", "",
             "## Table 1: all conditions on the same pairs", "",
             "| Condition | n | Accuracy % [95% CI] | Cost per pair (US$, list) | Split rate % |",
             "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['label']} | {r['n']} | {_pct(r['accuracy'])} [{_pct(r['ci_low'])}, {_pct(r['ci_high'])}] | "
                     f"{r['cost_per_pair']:.5f} | {_pct(r['split_rate'])} |")
    lines += ["", "Split: the judge picked the same shown position in both answer orders, so its verdict followed the order.",
              "", "## Table 2: each method against votes at the same cost", "",
              "Baseline: the smallest odd number of weak-judge votes per order whose cost is at least the method's.", "",
              "| Method | Role | Same-cost baseline | Method minus baseline, points [95% CI] | McNemar p |",
              "|---|---|---|---|---|"]
    for method, c in comp["same_cost"].items():
        cmp = c["comparison"]
        lines.append(f"| {LABELS[method]} | {c['role']} | {LABELS[c['baseline']]} | "
                     f"{100 * cmp.diff:+.1f} [{100 * cmp.ci_low:+.1f}, {100 * cmp.ci_high:+.1f}] | {cmp.p_value:.3g} |")
    for note in comp["notes"]:
        lines.append(f"\n{note}")
    if "H2" in comp:
        lines += ["", f"**H2** (debaters `high` minus `low`): {comp['H2']}"]
    if "H3" in comp:
        lines += ["", "**H3** (H1 comparison by group):", ""]
        for g, cmp in comp["H3"].items():
            lines.append(f"- {g}: {cmp}")
    if check is not None:
        lines += ["", f"## Check: the {n_check} report pairs outside the pilot", "",
                  "The pilot pairs decided go/no-go, so the same-cost comparisons are repeated without them.", "",
                  "| Method | Same-cost baseline | Method minus baseline, points [95% CI] |", "|---|---|---|"]
        for method, c in check["same_cost"].items():
            cmp = c["comparison"]
            lines.append(f"| {LABELS[method]} | {LABELS[c['baseline']]} | "
                         f"{100 * cmp.diff:+.1f} [{100 * cmp.ci_low:+.1f}, {100 * cmp.ci_high:+.1f}] |")
    lines += ["", "H1 is the one primary test; every other comparison is exploratory, with no correction for multiple tests."]
    return "\n".join(lines) + "\n"


def plot(rows: Sequence[Mapping], path) -> None:
    """Accuracy against cost per pair, with 95% intervals; votes as a line, methods as labelled points."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4.5))
    votes = [r for r in rows if r["condition"] == "judge_none" or r["condition"].startswith("votes_k")]
    votes.sort(key=lambda r: r["cost_per_pair"])
    if votes:
        ax.errorbar([r["cost_per_pair"] for r in votes], [100 * r["accuracy"] for r in votes],
                    yerr=[[100 * (r["accuracy"] - r["ci_low"]) for r in votes],
                          [100 * (r["ci_high"] - r["accuracy"]) for r in votes]],
                    fmt="-o", color="0.45", capsize=3, label="Weak judge, 1–11 votes per order")
    markers = {"debate_high": ("s", "C0"), "debate_low": ("s", "C9"), "one_sided": ("^", "C2"),
               "judge_low": ("D", "C3"), "judge_high": ("D", "C1")}
    for r in rows:
        if r["condition"] in markers:
            m, c = markers[r["condition"]]
            ax.errorbar([r["cost_per_pair"]], [100 * r["accuracy"]],
                        yerr=[[100 * (r["accuracy"] - r["ci_low"])], [100 * (r["ci_high"] - r["accuracy"])]],
                        fmt=m, color=c, capsize=3, label=LABELS[r["condition"]].replace("`", ""))
    ax.set_xlabel("Cost per pair, both answer orders (US$, off-peak list price)")
    ax.set_ylabel("JudgeBench accuracy (%)")
    ax.set_title("Accuracy against cost on the report pairs (95% CIs)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def csv_rows(rows: Sequence[Mapping]) -> list[dict]:
    return [{k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()} for r in rows]
