# LLM Debate and LLM Judge: shared agent context

This file is the shared project context for both team members' coding agents.
Claude Code loads it through `CLAUDE.md`; Codex, Cursor and other tools read `AGENTS.md` directly.
Keep it current: if you change the plan, layout, rules or conventions, update this file in the same PR.
The running log of status, decisions, runs and spend is in `docs/NOTES.md`. Read it at the start of every session.

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

**Research question:** not chosen yet. Pick one of questions 1–9 in the brief, or write our own with instructor approval.
Record the choice and the hypothesis in `docs/NOTES.md` and in this section.

## Hard rules

- Use the model `deepseek-flash` only.
- The budget is at most US$30 for the whole team.
  Check the budget ledger in `docs/NOTES.md` before every paid run and add each paid run to it.
- Compare every new method with a baseline at the same API cost.
  Match on logged tokens or dollars, not on the number of calls, because debate prompts get longer each round.
- Every API call goes through `chat()`, so its tokens and cost are logged. Do not call the SDK directly anywhere else.
- Never commit API keys. The key goes in `.env`, which git ignores; `.env.example` shows the variable names.
- Pilot every change on a small subset of 20–50 questions before a full run.
  Commit the call cache and logs so neither of us pays twice for the same call.
- One command must rebuild the main results table from the committed logs.

## Roles

The two roles are proposed but not assigned yet; full detail is in `docs/ROLES.md`.
Update this section with names once we decide.

- **Role A, method lead:** debate engine, judge, the new method, prompts, pilot runs and error analysis.
- **Role B, evaluation lead:** `chat()` helper, dataset loaders and scoring, baselines, cost matching, statistics, plots, the reproduce script and budget tracking.

Every change is reviewed by the other member in a pull request before it is merged.

## Planned layout

Update this section whenever the layout changes.

```
src/debate_judge/
  llm.py          chat() helper, cache, call log            (evaluation lead)
  data.py         dataset loaders, answer extraction, scoring (evaluation lead)
  baselines.py    chain-of-thought, self-consistency        (evaluation lead)
  stats.py        confidence intervals, paired tests        (evaluation lead)
  debate.py       debate engine                             (method lead)
  judge.py        pairwise judge with order swap            (method lead)
  methods/        our new method                            (method lead)
scripts/          run_baseline.sh, run_method.sh, make_table.py
logs/             JSONL call logs and cache (committed)
results/          tables and plots (committed)
report/           proposal and report drafts
docs/             brief, roles, shared notes
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
