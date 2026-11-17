# Schedule

**Goal: everything finished by Friday 20 November 2026.** The course deadline is Monday 23 November;
Saturday to Monday are buffer only, not planned work.

Times are UTC+3. A task is **late** if it is not done by the end of its day.
Tick the boxes as tasks are done, in the same PR as the work or in `docs/NOTES.md`'s evening update.

## Rules

- **Blockers:** if a task that blocks the other person is not in a PR by midday, the other person picks it up.
- **Paid runs:** start them after 13:00 UTC+3 on weekdays (off-peak, half price; peak is 04:00–07:00 and 09:00–13:00 UTC+3).
- **Pilot calls are cached,** so the full run reuses them and does not pay twice. The 10–20 dry-run pairs are left out of reported results.
- **Every evening:** both update `docs/NOTES.md` (status, runs, spend) so the other's agent starts from the latest work.

## Day by day

### Tue 17 Nov

- [ ] Varun: JudgeBench loader and both-order scoring (`data.py`), in a PR. *Carried over from Mon 16; it blocks the pilot.*
- [ ] Varun: review PR #5 (proposal) and PR #6 (judge).
- [ ] Adrian: debater prompt and `debate.py` (one-round debate, one-sided argument, concession check), in a PR.
- [ ] Adrian: review Varun's loader PR.
- [ ] Both, evening: freeze the prompts with a git tag, dry run on 10–20 pairs, start the 200-pair pilot.

### Wed 18 Nov

- [ ] Both, by midday: go/no-go from the pilot (question 6, or switch to question 8); finish the proposal and merge it.
- [ ] Adrian: full debate and one-sided runs on all 620 pairs.
- [ ] Varun: vote baseline, cost matching and thinking-judge runs.
- [ ] Varun: confidence intervals and paired tests (`stats.py`).

### Thu 19 Nov

- [ ] Adrian: error analysis, concession counts and results by category.
- [ ] Adrian: report sections Method and Analysis.
- [ ] Varun: plots, one-command results table, budget ledger.
- [ ] Varun: report sections Setup, Results and Limitations.

### Fri 20 Nov

- [ ] Both: report sections Introduction and Hypothesis, and Collaboration.
- [ ] Both: final edit; check the report is 6–8 pages.
- [ ] Both: rebuild the results table from a fresh clone with one command.
- [ ] **Finished:** proposal, report, code and logs ready to submit.

### Sat 21 – Mon 23 Nov

Buffer only. Submit by Monday 23 November.

## Cut to fit the schedule

- The two-round debate is dropped.
- The max-effort run happens only if Thursday ends with spare time and budget.

If the pilot says switch to question 8, the days stay the same; Wednesday's runs become the question 8 runs.
