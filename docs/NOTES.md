# Shared project notes

This is the running log for both members and their coding agents.
Read it at the start of every work session, and update it at the end.
Put the newest entries first in each section.

## Status

- **2026-11-14:** Repo created. Two roles proposed (see `docs/ROLES.md`), not assigned yet.
  The course provides no framework code, so we build it ourselves.
  The research question is not chosen yet.

## Next steps

- [ ] Both: assign Role A and Role B, then record it in `docs/ROLES.md` in a pull request.
- [ ] Both: choose the research question and write the 1-page proposal (`report/proposal.md`).
- [ ] Evaluation lead: `chat()` helper with cache and call log; confirm the model id.
- [ ] Method lead: debate engine and judge on top of `chat()`.

## Decisions

| Date | Decision | Why | Who |
|---|---|---|---|
| 2026-11-14 | Proposed two roles, Role A (method lead) and Role B (evaluation lead); each of us picks one, and a tie is settled on a call | The split works for any research question, both of us write code, and Varun should choose rather than be assigned | Adrian |
| 2026-11-14 | Match costs on logged tokens and dollars, not on the number of calls | Debate prompts get longer each round | Both |

## Budget ledger (cap: US$30)

| Date | Who | Run | Dataset and number of questions | Cost (US$) | Total so far (US$) |
|---|---|---|---|---|---|
| | | | | | 0.00 |

## Experiment log

<!-- One entry per run: date, who, git commit, settings, accuracy, cost, notes. -->

## Collaboration log

Record entries here for the report's Collaboration section.

| Date | Who | What | AI tools used and how the code was checked |
|---|---|---|---|
| 2026-11-14 | Adrian | Repo setup, roles, shared agent context | Claude Code wrote the scaffold; Adrian reviewed the files |
