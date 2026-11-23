# LLM Debate and LLM Judge

This is our course final project (research question 6).
**Can a weak judge find the correct answer when two agents debate?**
We test it inside one model, `deepseek-flash` through the DeepSeek API: the judge has thinking off, the debaters think.
The questions are the 600 report questions of JudgeBench, and we compare the debate with the judge's own majority vote at the same API cost.

**Main result:** the weak judge scores 85.3% after a debate and 77.3% with the same cost spent on votes,
a difference of +8.0 points [+4.6, +11.4] (paired 95% interval). See [results/full/table.md](results/full/table.md)
and [results/full/accuracy_vs_cost.png](results/full/accuracy_vs_cost.png).

- Brief: [docs/project_brief.pdf](docs/project_brief.pdf)
- Proposal: [report/proposal.md](report/proposal.md)
- Roles: [docs/ROLES.md](docs/ROLES.md)
- Status, decisions, every paid run and the budget: [docs/NOTES.md](docs/NOTES.md)
- Schedule: [docs/SCHEDULE.md](docs/SCHEDULE.md)
- Context shared by both team members' coding assistants: [AGENTS.md](AGENTS.md)

## Setup

macOS, Linux or Git Bash:

```bash
python -m venv .venv
source .venv/bin/activate        # Git Bash on Windows: source .venv/Scripts/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

A DeepSeek key is only needed to run new experiments: copy `.env.example` to `.env` and put the key in it.

## Rebuild the main results table (no API key, no cost)

```bash
python scripts/make_table.py
```

This rebuilds `results/full/table.md`, `results/full/table.csv` and `results/full/accuracy_vs_cost.png` from the
committed per-question results `results/full/pairs.jsonl`: accuracy with 95% intervals, cost per question, each method
against votes at the same cost, and the same comparisons on the 400 questions outside the pilot.
The last check downloads JudgeBench from Hugging Face; if that is not possible it is skipped and the rest is built.

```bash
python -m pytest                 # unit tests, no API calls
```

## How the experiments were run

Every reply is cached in `logs/cache` and every call is logged in `logs/calls`, both committed, so running the same
settings again reuses the recorded replies instead of paying for them. Costs below are what we paid.

| Step | Command | Cost (US$) |
|---|---|---|
| Check the API and the thinking switch | `python scripts/check_model.py` | under 0.01 |
| Prompt dry run on 20 questions | `python scripts/run_pilot.py dry` | 0.15 |
| Go/no-go pilot on 200 questions (needs the git tag `prompts-v1`) | `python scripts/run_pilot.py pilot` | 1.40 |
| Final go/no-go from the hand labels | `python scripts/run_pilot.py decide` | 0 |
| Cost estimate for the full run | `python scripts/run_full.py estimate` | 0 |
| Full run: weak judge, 1 to 11 votes, thinking judge | `python scripts/run_full.py shared` | 3.83 |
| Full run: debates, one-sided argument, concession checks | `python scripts/run_full.py debate` | 4.85 |
| Results table and plot | `python scripts/make_table.py` | 0 |

The whole project cost US$10.22 of the US$30 limit. The scripts refuse to run at peak prices, with changed prompts
or with too little balance; see [AGENTS.md](AGENTS.md) for how each one works.

## Layout

```
src/debate_judge/   llm.py (API helper, cache, cost log), data.py (JudgeBench, fixed question sets, scoring),
                    prompts.py, judge.py, debate.py (judge and debaters), stats.py (intervals and paired tests),
                    pilot.py, full.py (the runs), table.py (table and plot)
scripts/            check_model.py, run_pilot.py, run_full.py, make_table.py
tests/              unit tests that use a fake API
logs/               call logs and the reply cache
results/            pilot/ and full/ results, table and plot
report/             proposal
docs/               brief, roles, notes, schedule, research on the nine questions
```
