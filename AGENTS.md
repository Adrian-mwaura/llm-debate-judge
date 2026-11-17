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

## Using the judge (built)

`src/debate_judge/judge.py` and `src/debate_judge/prompts.py`; read their docstrings.

- `judge_pair(pair, thinking=..., run=..., condition=...)` judges one JudgeBench pair in both answer orders.
  `pair` uses JudgeBench's own fields: `pair_id`, `question`, `response_A`, `response_B` (`label` is not read here).
- **`v.decisions` are both in the pair's original labels** ("A>B" means `response_A` won, in either order).
  Do not flip the second one again when scoring; JudgeBench's published outputs keep it in swapped labels, ours don't.
  A decision is `None` when the reply was incomplete or could not be parsed.
- Debate arguments go in as `arguments={"A": ..., "B": ...}` in original labels; one entry means a one-sided argument.
  They are relabeled for the swapped order, so each argument is generated once and reused for both orders.
- For votes, call it with `sample=0..k-1`. Every call logs `prompt_version`; bump `JUDGE_PROMPT_VERSION` if the wording changes.
- The prompts are frozen with a git tag before the pilot. Don't tune them on pilot pairs.

## Using the JudgeBench data (built)

`src/debate_judge/data.py`; read its docstring.

- `load_judgebench()` returns all 620 pairs as dicts, pinned to one dataset revision. It adds `split` (gpt or claude),
  `category` (knowledge, reasoning, math, coding) and `group` (knowledge or rmc). Downloading it is free.
- **Fixed subsets; always use these, never pick pairs by hand:**
  - `dry_run_pairs(pairs)`: 20 pairs for prompt dry runs. Never in reported results.
  - `pilot_pairs(pairs)`: 200 pairs for the go/no-go pilot. They are part of the reported set, so the full run reuses their cached calls.
  - `report_pairs(pairs)`: the 600 pairs all reported results use.
  All keep the category mix of the full set.
- `score_pair(label, verdict.decisions)` applies JudgeBench's rule. The decisions are in original labels, as `judge.py` returns them; do not flip.
  Outcomes: `both_right`, `both_wrong`, `split` (same shown position both times; `first_slot` says which), `partial_right`, `partial_wrong`, `no_verdict`.
- `majority(decisions)` combines votes for one order (ties give `None`); `summarize(...)` gives accuracy by category and group.
- Scoring was checked against JudgeBench's published outputs: GPT-4o 50.9, DeepSeek-R1 73.1 and o3-mini (high) 80.9, matching exactly.

## Using the statistics (built)

`src/debate_judge/stats.py`; read its docstring. Inputs are `{pair_id: correct}` dicts, from `score_pair(...).correct`.

- `accuracy_ci(correct)`: accuracy with a 95% Wilson interval. Use it for every number in the results table.
- `paired_comparison(a, b)`: B minus A on the pairs both conditions scored, with Newcombe's 95% paired interval
  and McNemar's exact p-value. Always compare conditions this way, never by overlapping the two separate intervals.
- **Go/no-go rule:** `paired_comparison(weak_judge, thinking_judge).b_better` (the interval is above zero).
- `by_group(...)` and `paired_by_group(...)` split by `group` (knowledge or rmc) or `category`, for hypothesis H3.
- `paired_bootstrap_interval(a, b)` is a seeded cross-check; it agrees with Newcombe within about 2 points.

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
  prompts.py      judge (and later debater) prompt templates [judge built] (method lead)
  debate.py       debaters: one-round debate, one-sided argument (method lead)
  judge.py        pairwise judge in both answer orders [built] (method lead)
  methods/        our new method                            (method lead)
scripts/          check_model.py [built]; run_baseline.sh, run_method.sh, make_table.py
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
