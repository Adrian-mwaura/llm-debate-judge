# LLM Debate and LLM Judge: shared agent context

This file is the shared project context for both team members' coding agents.
Claude Code loads it through `CLAUDE.md`; Codex, Cursor and other tools read `AGENTS.md` directly.
Keep it current: if you change the plan, layout, rules or conventions, update this file in the same PR.
The running log of status, decisions, runs and spend is in `docs/NOTES.md`. Read it at the start of every session.
The schedule is in `docs/SCHEDULE.md`: everything finished by Friday 20 November. Check it at the start of every session,
work on today's tasks, and say so if one is late.

## Project

This is a course final project; the full brief is in `docs/project_brief.pdf`.
A team of two studies multi-agent debate and LLM judges using the DeepSeek API.
We add a new method, compare it with baselines at the same API cost, and report accuracy with 95% confidence intervals.

The course provides no framework code, so we build the `debate-judge-baseline` framework ourselves, following the brief:

- **`chat()` helper:** the single function for every API call.
  It uses the OpenAI Python SDK pointed at the DeepSeek base URL with model `deepseek-flash`.
  It keeps a disk cache and writes a JSONL log of each call: settings, tokens in and out, cost, and the response.
- **Debate engine:** N agents and R rounds.
  In each round every agent reads the other agents' answers and gives an updated answer.
  The final answer is a majority vote.
- **Judge:** compares two answers and picks one.
  It runs each comparison twice with the order swapped.
  It outputs JSON: `{"reasoning": "...", "winner": "A" | "B"}`.
- **Baselines:** chain-of-thought gives one sample; self-consistency gives k samples and takes a majority vote.
- **Evaluation harness:** loads GSM8K, MMLU-Pro and JudgeBench and scores answers against the answer key.
  It adds up tokens and cost, computes 95% confidence intervals, and runs paired tests (the same questions go to every method).

**Research question: question 6, "Can a weak judge find the correct answer when two agents debate against each other?"**,
run on JudgeBench as redesigned in `docs/research/question_selection.md` (section "Question 6 (second choice, redesigned on JudgeBench)").

- **Hypothesis:** a non-thinking `deepseek-flash` judge is more accurate on JudgeBench after reading arguments from two thinking `deepseek-flash` debaters
  than when it spends the same budget on extra votes. The benefit grows with the debaters' thinking effort,
  and is larger on reasoning, math and coding pairs than on knowledge pairs.
- **Setup:** each JudgeBench pair has one correct and one wrong response; one debater argues for each.
  The judge sees the question, both responses and the arguments, and gives a verdict in both answer orders, scored with JudgeBench's rule.
- **Same-cost baseline:** the non-thinking judge alone with k votes, k chosen to match each protocol's cost at list price.
  A thinking judge alone is also reported on the same accuracy-vs-cost plot.
- **Go/no-go pilot first:** if non-thinking `deepseek-flash` is not clearly a weaker judge than thinking `deepseek-flash`, switch to question 8.
  Most code (JudgeBench loader, scoring, judge, vote baseline, thinking judge) is shared, so nothing is lost.

## Hard rules

- Use the model `deepseek-flash` only.
- The budget is at most US$30 for the whole team.
  Check the budget ledger in `docs/NOTES.md` before every paid run and add each paid run to it.
- Compare every new method with a baseline at the same API cost.
  Match on logged tokens or dollars, not on the number of calls, because debate prompts get longer each round.
- Every API call goes through `chat()`, so its tokens and cost are logged. Do not call the SDK directly anywhere else.
  The only exception is unbilled, read-only calls (listing models, checking the balance), which may use `get_client()` directly,
  as `scripts/check_model.py` does. Never use it for a completion.
- Never commit API keys. The key goes in `.env`, which git ignores; `.env.example` shows the variable names.
- Pilot every change on a small subset of 20–50 questions before a full run.
  Commit the call cache and logs so neither of us pays twice for the same call.
- One command must rebuild the main results table from the committed logs.

## Roles

Roles are assigned (full detail is in `docs/ROLES.md`):

- **Role A, method lead (Adrian):** debate engine, judge, the new method, prompts, pilot runs and error analysis.
- **Role B, evaluation lead (Varun):** `chat()` helper, dataset loaders and scoring, baselines, cost matching, statistics, plots, the reproduce script and budget tracking.

Every change is reviewed by the other member in a pull request before it is merged.

## Using `chat()` (built)

`src/debate_judge/llm.py` is done; read its docstring. The rules that matter for everyone:

- Call `chat(messages, thinking=..., max_tokens=..., run=...)`. `thinking` is required: `"none"`, `"low"`, `"high"` or `"max"`.
  With thinking on, `max_tokens` must leave room for the reasoning tokens.
- **Check `r.complete` before using `r.text`.** An answer cut off by `max_tokens` or a blank reply is returned and logged
  (it was paid for) but never cached, so a rerun calls the API again.
- `temperature` is only sent with thinking off; the API ignores it in thinking mode. Pass `logprobs=True` to get `r.logprobs`.
- `run` names the log file `logs/calls/<run>.jsonl`. Use one run name per experiment condition, e.g. `pilot_debate_high`.
- For k votes, pass `sample=0..k-1`. The API has no `n` or `seed`, and identical requests with the same `sample` come from the disk cache.
- Pass `meta={...}` (pair id, role, order) so the logs can be joined back to the data.
- `chat_many(jobs)` runs calls in parallel; `summarize_log(run)` gives totals.
- **Match methods on `cost_match_usd`** (off-peak list price, no cache discount; independent of time and caching).
  `cost_usd` is the real spend (peak or off-peak, cache discount, 0 for our own cache hits); the budget ledger uses it.
- Tests use a fake client and cost nothing: `python -m pytest`. `python scripts/check_model.py` checks the real API for under US$0.01.

## Using the debaters (built)

`src/debate_judge/debate.py` and the debater prompt in `src/debate_judge/prompts.py`; read their docstrings.

- **One round:** `debate_arguments(pair, thinking="low"|"high", run=...)` makes one call per side; each debater defends
  its assigned response and critiques the other, without seeing the other debater's argument. Pass
  `arguments_for_judge(args)` to `judge_pair()`; incomplete arguments are left out.
- **One-sided:** `one_sided_arguments(pair, debate_args_high)` reuses one of the two `high` debate arguments (no extra
  debater call). The side is fixed per pair by a seeded hash and is the correct response about half the time.
- Debaters say "my response" and "the other response", never "Response A/B", so one argument fits both answer orders.
  Any slip is rewritten and counted in `Argument.letter_fixes`.
- A cut-off or blank argument is retried once with twice the token cap; both attempts' costs count toward the condition.
- **Concessions:** `check_concession(argument, run=...)` is a thinking-off check ("defends", "concedes" or "unclear").
  It is analysis, not part of any condition, so it is left out of cost matching. In the pilot, compare it with hand labels.
- Every call logs `prompt_version` (`debater-v1`, `concession-v1`). Frozen with the judge prompt before the pilot.

## Using the judge (built)

`src/debate_judge/judge.py` and `src/debate_judge/prompts.py`; read their docstrings.

- `judge_pair(pair, thinking=..., run=..., condition=...)` judges one JudgeBench pair in both answer orders.
  `pair` uses JudgeBench's own fields: `pair_id`, `question`, `response_A`, `response_B` (`label` is not read here).
- **`v.decisions` are both in the pair's original labels** ("A>B" means `response_A` won, in either order).
  Do not flip the second one again when scoring; JudgeBench's published outputs keep it in swapped labels, ours don't.
  A decision is `None` when the reply was incomplete or could not be parsed.
- Debate arguments go in as `arguments={"A": ..., "B": ...}` in original labels; one entry means a one-sided argument.
  They are relabeled for the swapped order, so each argument is generated once and reused for both orders.
- For votes, call it with `sample=0..k-1` and an explicit `temperature`, so it is logged.
  Every call logs `prompt_version`; bump `JUDGE_PROMPT_VERSION` if the wording changes.
- The prompts are frozen with a git tag before the pilot. Don't tune them on pilot pairs.

## Using the JudgeBench data (built)

`src/debate_judge/data.py`; read its docstring.

- `load_judgebench()` returns all 620 pairs as dicts, pinned to one dataset revision. It adds `split` (gpt or claude),
  `category` (knowledge, reasoning, math, coding) and `group` (knowledge or rmc). Downloading it is free.
- **Fixed subsets; always use these, never pick pairs by hand:**
  - `dry_run_pairs(pairs)`: 20 pairs for prompt dry runs. Never in reported results.
  - `pilot_pairs(pairs)`: 200 pairs for the go/no-go pilot. They are part of the reported set, so the full run reuses their cached calls.
  - `report_pairs(pairs)`: the 600 pairs all reported results use (the pilot pairs first).
  - `non_pilot_pairs(pairs)`: the 400 reported pairs outside the pilot, for the report's check that excludes the pilot.
  All keep the category mix of the full set; the pilot also keeps the mix of response authors (gpt or claude).
  The dry-run pairs are fixed: they are the 20 pairs the 2026-11-18 dry run used.
- `score_pair(label, verdict.decisions)` applies JudgeBench's rule. The decisions are in original labels, as `judge.py` returns them; do not flip.
  Outcomes: `both_right`, `both_wrong`, `split` (same shown position both times; `first_slot` says which), `partial_right`, `partial_wrong`, `no_verdict`.
- `majority(decisions)` combines votes for one order (ties give `None`); `summarize(...)` gives accuracy overall (`"all"`),
  by category (`"knowledge"`, `"math"`, ...) and by group (`"group:knowledge"`, `"group:rmc"`).
- Scoring was checked against JudgeBench's published outputs: GPT-4o 50.9, DeepSeek-R1 73.1 and o3-mini (high) 80.9, matching exactly.

## Using the statistics (built)

`src/debate_judge/stats.py`; read its docstring. Inputs are `{pair_id: correct}` dicts, from `score_pair(...).correct`.

- `accuracy_ci(correct)`: accuracy with a 95% Wilson interval. Use it for every number in the results table.
- `paired_comparison(a, b)`: B minus A on the pairs both conditions scored, with Newcombe's 95% paired interval
  and McNemar's exact p-value. Always compare conditions this way, never by overlapping the two separate intervals.
- **Go/no-go rule:** `paired_comparison(weak_judge, thinking_judge).b_better` (the interval is above zero).
- `by_group(...)` and `paired_by_group(...)` split by `group` (knowledge or rmc) or `category`, for hypothesis H3.
- `paired_bootstrap_interval(a, b)` is a seeded cross-check; it agrees with Newcombe within about 2 points.

## Running the dry run and the pilot (built)

`scripts/run_pilot.py` with the logic in `src/debate_judge/pilot.py`; read their docstrings.

- `python scripts/run_pilot.py dry`: the 20 `dry_run_pairs`, every kind of call once (about US$0.20). Never reported.
- `python scripts/run_pilot.py pilot`: the 200 `pilot_pairs`. Weak judge, thinking judge at `low` and `high`;
  debaters at `low` and `high` on the first 30 pilot pairs (both sides), the weak judge reading those debates and the
  one-sided argument, and the automatic concession check. About US$1.50–2.
- **Freeze check:** the tag `prompts-v1` (on `5509a74`) must exist, and the code that decides results,
  `prompts.py`, `judge.py` and `debate.py` (`pilot.FROZEN_FILES`), must be identical to the tag with no uncommitted changes.
  Later commits to other files (data, notes, results, new scripts) are fine. The check is recorded in `summary.json`.
  **Any change to those three files after the tag means a new tag and new runs.** It also refuses peak price.
  Overrides: `--allow-peak`, `--allow-unfrozen` (avoid).
- Outputs: `results/<stage>/summary.json` (accuracy with intervals, paired comparisons, outcomes, incomplete and unparsed
  counts, cost per pair including debater arguments, suggested votes k per order capped at 15 with any condition over the
  cap flagged, go/no-go) and `results/<stage>/concession_review.csv` (every argument, automatic verdict, empty `hand_label`).
- **The weak judge always runs at `pilot.WEAK_JUDGE_TEMPERATURE` (1.0)**, alone, with debates and in the vote baseline,
  so the judge-alone call is vote sample 0 and is paid once.
- Concession rates leave incomplete arguments out of the denominator (reported as `incomplete_excluded`); no complete
  wrong-side argument at an effort is an error, not a NO-GO.
- **The go/no-go is final only after `python scripts/run_pilot.py decide`** (no API calls). It needs `hand_label` set to
  `defends`, `concedes` or `unclear` on every complete wrong-side row of `results/pilot/concession_review.csv`, computes the
  hand-label concession rates and their agreement with the automatic check, and writes `go_no_go_final` into `summary.json`.

## Running the full run (built)

`scripts/run_full.py` with the logic in `src/debate_judge/full.py`; read their docstrings. All on the 600 `report_pairs`.

- `python scripts/run_full.py estimate`: no API calls; cost estimate per condition from the pilot's measured costs, and the balance.
- `python scripts/run_full.py shared`: weak judge alone, the **vote baseline** (weak judge with `sample=0..10` per order;
  majority of the first k for k = 1, 3, 5, 7, 9, 11, saved as `votes_k1` … `votes_k11`), thinking judge `low` and `high`.
  Needed by question 6 and by the question-8 fallback, so it may run before the final go/no-go. About US$5.
- `python scripts/run_full.py debate`: debate `high` and `low`, one-sided, and the automatic concession check.
  **Refuses without `go_no_go_final` = GO** (from `run_pilot.py decide`). About US$5.
- The freeze check runs at start-up. **Before every condition** it repeats the peak check (`full.peak_check`, so a weekday run
  that drifts into 09:00–12:00 or 14:00–18:00 UTC+8 stops cleanly) and a budget check: it reads the DeepSeek balance and stops
  if the balance is below the estimate × 1.25. The debate group's estimate includes the concession checks (pilot cost per call
  × 4 per pair). Finished conditions are saved; every call is cached, so just rerun.
- The printed spend and `run_<group>.json` include the concession checks (`spend_usd_concession_checks`), so the figure for the
  budget ledger matches the account.
- Output: `results/full/pairs.jsonl`, one record per (pair, condition) with both decisions, `correct`, `outcome`, `first_slot`
  and `cost_match_usd` (the debater arguments the judge read are included; one-sided includes the one argument it shows),
  plus `concessions.jsonl` and `run_<group>.json`. Logs: `logs/calls/full_*.jsonl`.
- **Cost matching for H1 (the proposal's rule):** compare each condition with `votes_k<k>` for the **smallest odd k whose mean
  `cost_match_usd` per pair is at least the condition's** (`full.matched_k`). From the pilot: debate `high` → k 9 (ratio 8.95,
  hence votes up to 11 in case the full run costs slightly more), debate `low` → 7, thinking `high` → 7, thinking `low` → 5,
  one-sided → 5. `make_table.py` does this from the full run's own costs in `pairs.jsonl`.

## Building the results table (built)

`python scripts/make_table.py`, logic in `src/debate_judge/table.py`. **The one command that rebuilds every reported number**
from the committed `results/full/pairs.jsonl`; no API calls. Writes `results/full/table.md`, `table.csv` and
`accuracy_vs_cost.png`.

- Table 1: every condition on the same pairs: accuracy with a 95% Wilson interval, mean cost per pair, split rate.
- Table 2: each method against votes at the same cost, using the proposal's rule (`full.matched_k`, measured on the full run's
  own costs), with Newcombe's paired interval and McNemar's p. **H1 (primary) = debate `high` against its same-cost votes**;
  all other rows are exploratory. Then H2 (debate `high` minus `low`) and H3 (the H1 comparison by group).
- The same-cost comparisons are repeated on the 400 report pairs outside the pilot.
- The plot: the votes as a line (cost against accuracy, k = 1 to 11) and each method as a point, all with 95% intervals.

## Planned layout

Update this section whenever the layout changes.

```
pyproject.toml    package metadata and pytest settings
tests/            unit tests; no API calls
src/debate_judge/
  llm.py          chat() helper, cache, call log  [built]   (evaluation lead)
  data.py         JudgeBench loader, fixed subsets, both-order scoring [built] (evaluation lead)
  baselines.py    chain-of-thought, self-consistency        (evaluation lead)
  stats.py        Wilson intervals, Newcombe paired interval, McNemar test [built] (evaluation lead)
  prompts.py      judge, debater and concession-check prompts [built] (method lead)
  debate.py       debaters: one-round debate, one-sided argument, concession check [built] (method lead)
  judge.py        pairwise judge in both answer orders [built] (method lead)
  methods/        our new method                            (method lead)
  pilot.py        dry run and go/no-go pilot logic [built] (evaluation lead)
  full.py         full run on the 600 report pairs, vote baseline, budget guard [built] (evaluation lead)
  table.py        results table, same-cost tests (H1–H3), plot [built] (evaluation lead)
scripts/          check_model.py, run_pilot.py, run_full.py, make_table.py [built]
logs/             calls/<run>.jsonl call logs and cache/<xx>/<hash>.json (committed)
results/          tables and plots (committed)
report/           proposal and report drafts
docs/             brief, roles, shared notes, schedule
```

## Workflow

- Pull `main` before you start.
  Do each task on its own branch named `<name>/<topic>` and open a pull request.
  The other member reviews it before it is merged. Nobody pushes directly to `main`.
- At the end of every work session, update `docs/NOTES.md` with status, decisions, runs and spend.
  This way the other member's agent always starts from your latest work.
- The person who commits AI-written code is responsible for it.
  Run it on a small sample and check the outputs by hand.
  Note which tool you used and how you checked the code in the collaboration log in `docs/NOTES.md`; the report needs it.

## Conventions

- Use Python 3.11 or newer, and install dependencies from `requirements.txt`.
- Record the settings of every run with its logs: dataset, number of questions, N, R, k, temperature, max_tokens and seed.
- The bash scripts in `scripts/` must also work in Git Bash on Windows.
