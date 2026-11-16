# Roles and division of work

**Team:** Adrian Mwaura (GitHub `Adrian-mwaura`) and Varun Chopra (GitHub `varunchopra-088878`).

**Status: Varun chose Role B (evaluation lead), so Adrian takes Role A (method lead).**
Adrian agrees to this split by approving and merging the pull request that records it.
If Adrian would rather swap, we settle it on a call before merging.

| Member | Role |
|---|---|
| Adrian Mwaura | Role A: method lead |
| Varun Chopra | Role B: evaluation lead |

The work is split by pipeline stage, so the split holds whatever research question we pick.
Each member owns their area and reviews the other's pull requests.

| | Role A: method lead | Role B: evaluation lead |
|---|---|---|
| **Framework** | Debate engine (N agents × R rounds, majority vote); judge (pairwise, order swap, JSON verdict) | `chat()` helper (DeepSeek, cache, per-call token and cost log); loaders and scoring for GSM8K, MMLU-Pro and JudgeBench |
| **Experiments** | Our new method; writing and tuning its prompts; pilot runs on small subsets | Baselines (chain-of-thought, self-consistency); baselines matched on cost; full runs; budget ledger |
| **Analysis** | Error analysis and the example errors for the report | 95% confidence intervals, paired tests, results table, accuracy-vs-cost plot |
| **Reproducibility** | Settings for the method's runs recorded with its logs | The one command that rebuilds the main results table |
| **Report** | Method; Analysis | Experiment setup; Results; Limitations |

## Shared work

- Choosing the research question and writing the 1-page proposal.
- Report sections: Question and hypothesis, Collaboration, and the final edit.
- Reviewing every pull request from the other member.
- Keeping `AGENTS.md` and `docs/NOTES.md` up to date.

## Order of work

1. Both: choose the research question and write the proposal.
2. Evaluation lead: build `chat()` and confirm the exact model id with the API's models list.
   Method lead: start the debate engine and judge against a stub of `chat()`.
3. Evaluation lead: dataset loaders and scoring, then the baselines.
   Method lead: the debate engine and judge running end to end on 20 questions.
4. Method lead: implement our new method and pilot it.
   Evaluation lead: the cost-matched baselines, statistics and plots.
5. Full runs with the budget checked first, then the results table and plot.
6. Report: each member drafts their own sections, then we edit the whole report together.
