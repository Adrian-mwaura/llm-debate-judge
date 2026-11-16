# Shared project notes

This is the running log for both members and their coding agents.
Read it at the start of every work session, and update it at the end.
Put the newest entries first in each section.

## Status

- **2026-11-16:** Research on which question to pick is in `docs/research/question_selection.md`.
  It recommends question 8 (judge computation), with questions 7 and 6 as second and third choices.
  This is input for our meeting, not a decision. The proposal is due 2026-11-23.
  Facts for whoever builds `chat()`: thinking is on by default and billed as output, `temperature` has no
  effect in thinking mode, and off-peak hours are half price (peak is 01:00–04:00 and 06:00–10:00 UTC on weekdays).
- **2026-11-14:** Repo created. Two roles proposed (see `docs/ROLES.md`), not assigned yet.
  The course provides no framework code, so we build it ourselves.
  The research question is not chosen yet.

## Next steps

- [ ] Both: assign Role A and Role B, then record it in `docs/ROLES.md` in a pull request.
- [ ] Both: read `docs/research/question_selection.md` before the meeting.
- [ ] Both: choose the research question and write the 1-page proposal (`report/proposal.md`), due 2026-11-23.
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
| 2026-11-16 | Adrian | Research report comparing the nine questions | Claude Code searched and read the sources (official DeepSeek docs, dataset pages, paper abstracts) and wrote the report; its limits section lists what was not verified; Adrian to review before the meeting |
| 2026-11-14 | Adrian | Repo setup, roles, shared agent context | Claude Code wrote the scaffold; Adrian reviewed the files |
