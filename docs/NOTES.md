# Shared project notes

This is the running log for both members and their coding agents.
Read it at the start of every work session, and update it at the end.
Put the newest entries first in each section.

## Status

- **2026-11-16:** Adrian built the judge (`src/debate_judge/judge.py`, prompt in `src/debate_judge/prompts.py`, version `judge-v1`):
  one JudgeBench pair judged in both answer orders, JSON verdict, decisions returned in the pair's original labels,
  debate arguments relabeled for the swapped order. Offline tests only so far (53 pass in total); no real-API dry run yet.
  The proposal draft is in PR #5 for Varun's review. Adrian reviewed and merged PR #4 (`chat()`).
- **2026-11-16:** Real-API check passed after Varun topped up US$10 (USD account). All four thinking levels are accepted:
  thinking off gives 0 reasoning tokens; `low`, `high` and `max` give reasoning tokens, counted inside `completion_tokens`
  and billed as output. Thinking mode adds about 26 prompt tokens per call (44 against 18 on the same question).
  On a trivial question `low` and `high` used the same 18 reasoning tokens, so the pilot must measure how effort levels differ on real pairs.
  Log: `logs/calls/check_model.jsonl`.
- **2026-11-16:** Fixed all seven points from Adrian's review of PR #4: incomplete answers (`finish_reason != "stop"` or blank)
  are no longer cached and are flagged by `r.complete`; `.env` is loaded before `MODEL` and `LOG_DIR` are read; `logprobs` reach
  `ChatResult` and the log; identical concurrent calls are paid once (per-key lock); `temperature` is not sent in thinking mode;
  a comment on Chinese holidays; and `AGENTS.md` allows unbilled read-only calls outside `chat()`. 29 unit tests pass.
  Real-API check: the key works and `deepseek-flash` is listed, but completions return `402 Insufficient Balance` (balance 0);
  the thinking switch is still unverified until the account has credit.
- **2026-11-16:** Varun built the `chat()` helper (`src/debate_judge/llm.py`) with disk cache, per-run call log, peak/off-peak cost
  and a time-independent `cost_match_usd` for cost matching; unit tests in `tests/` use a fake client.
  Not yet run against the real API: Varun still needs a DeepSeek key in `.env`, then `python scripts/check_model.py`.
- **2026-11-16:** Varun picked question 6 (weak judge, two debaters) on JudgeBench, matching Adrian's lean; final once Adrian approves the PR.
  The question and hypothesis are recorded in `AGENTS.md`. Question 8 is the fallback if the go/no-go pilot fails.
  PR #2 (research report) was reviewed by Varun and merged.
- **2026-11-16:** Research on which question to pick is in `docs/research/question_selection.md`.
  It ranks question 8 (judge computation) first and question 6 (weak judge, two debaters), redesigned to run on JudgeBench, a close second.
  Adrian leans toward question 6. This is input for our meeting, not a decision. The proposal is due 2026-11-23.
  Facts for Varun's `chat()` helper: thinking is on by default and billed as output, `temperature` has no
  effect in thinking mode, and off-peak hours are half price (peak is 01:00–04:00 and 06:00–10:00 UTC on weekdays).
- **2026-11-16:** Varun joined the repo and chose Role B (evaluation lead); Adrian takes Role A (method lead).
  Recorded in `docs/ROLES.md` and `AGENTS.md` on branch `varun/roles`; Adrian approved and merged it (PR #1), so the roles are final.
- **2026-11-14:** Repo created. Two roles proposed (see `docs/ROLES.md`), not assigned yet.
  The course provides no framework code, so we build it ourselves.
  The research question is not chosen yet.

## Next steps

- [x] Both: assign Role A and Role B, then record it in `docs/ROLES.md` in a pull request (merged in PR #1).
- [x] Both: read `docs/research/question_selection.md` before the meeting.
- [x] Both: choose the research question (question 6 on JudgeBench, Adrian to confirm in the PR).
- [ ] Both: write the 1-page proposal (`report/proposal.md`), due 2026-11-23. Draft in PR #5, waiting for Varun's review.
- [ ] Both: settle the go/no-go pilot rule. The proposal draft (PR #5) suggests 200 pairs; continue only if the thinking judge is better
  with a paired 95% confidence interval above zero and fewer than 1 in 5 debaters concede.
- [x] Evaluation lead (Varun): `chat()` helper with cache and call log (PR `varun/chat-helper`).
- [x] Evaluation lead (Varun): confirm the model id (`deepseek-flash` is in the models list).
- [x] Evaluation lead (Varun): add credit, then rerun `python scripts/check_model.py` to confirm the thinking switch (passed).
- [ ] Evaluation lead (Varun): JudgeBench loader and both-order scoring (`data.py`), next.
- [x] Method lead (Adrian): judge prompt and `judge_pair()` (branch `adrian/judge`).
- [ ] Method lead (Adrian): dry-run the judge on 10–20 pairs with the real API once the loader exists; those pairs are left out of reported results.
- [ ] Method lead (Adrian): debater prompt, one-round debate and one-sided argument (`debate.py`), next.

## For the report

- **Limitations:** JudgeBench has been public since 2024, so `deepseek-flash` may have seen its questions and responses in training.

## Decisions

| Date | Decision | Why | Who |
|---|---|---|---|
| 2026-11-16 | Match costs on `cost_match_usd`: off-peak list price with no cache discount | Peak hours and caching would otherwise make the same compute look cheaper or dearer depending on when and in what order we ran it | Varun |
| 2026-11-16 | Research question: question 6 (weak judge, two debaters), run on JudgeBench; question 8 is the fallback | Most novel option; the JudgeBench redesign gives a real strength gap and simpler protocols; a fair null result is acceptable under the brief; code is shared with question 8 | Varun, matching Adrian's lean; Adrian to confirm |
| 2026-11-16 | Varun is Role B (evaluation lead), Adrian is Role A (method lead) | Varun chose Role B; final once Adrian approves the PR | Varun |
| 2026-11-14 | Proposed two roles, Role A (method lead) and Role B (evaluation lead); each of us picks one, and a tie is settled on a call | The split works for any research question, both of us write code, and Varun should choose rather than be assigned | Adrian |
| 2026-11-14 | Match costs on logged tokens and dollars, not on the number of calls | Debate prompts get longer each round | Both |

## Budget ledger (cap: US$30)

| Date | Who | Run | Dataset and number of questions | Cost (US$) | Total so far (US$) |
|---|---|---|---|---|---|
| 2026-11-16 | Varun | `check_model` (setup check, 6 tiny calls, all thinking levels, peak hours) | none; one arithmetic question | 0.0002 | 0.0002 |

Account balances: Varun US$10.00 topped up (2026-11-16).

## Experiment log

<!-- One entry per run: date, who, git commit, settings, accuracy, cost, notes. -->

## Collaboration log

Record entries here for the report's Collaboration section.

| Date | Who | What | AI tools used and how the code was checked |
|---|---|---|---|
| 2026-11-16 | Adrian | Judge prompt, `judge_pair()` and 24 unit tests | Claude Code wrote them, adapting JudgeBench's vanilla judge prompt; tests use a fake `chat()` and the full suite passes (53); Adrian to review the diff in the PR |
| 2026-11-16 | Adrian | Reviewed PR #4 (`chat()`) and merged it after the fixes | Claude Code read the code and found seven issues, posted as a review; after Varun's fixes it re-read the diff and checked the committed API log for keys |
| 2026-11-16 | Varun | Fixed the seven points from Adrian's PR #4 review | Adrian's Claude Code found them by reading the code; Varun's Claude Code fixed them and added a test for each (29 tests pass); a good example of agent-assisted cross-review for the report |
| 2026-11-16 | Varun | `chat()` helper, unit tests, `scripts/check_model.py` | Claude Code wrote the code and tests; Varun reviewed it; the unit tests pass with a fake client; not yet checked against the real API |
| 2026-11-16 | Varun | Recorded the question 6 choice and hypothesis in `AGENTS.md` and these notes | Claude Code made the edits; Varun reviewed the diff |
| 2026-11-16 | Varun | Reviewed PR #2 (research report) twice and merged it | Claude Code checked that it merges cleanly and recomputed the scores, cost totals and confidence intervals; findings posted as a review comment (pilot size, vote cap) |
| 2026-11-16 | Adrian | Research report comparing the nine questions | Claude Code searched and read the sources (official DeepSeek docs, dataset pages, paper abstracts) and wrote the report; its limits section lists what was not verified; Adrian reviewed it, and Varun reviewed and merged it (PR #2) |
| 2026-11-16 | Varun | Recorded role choice in `docs/ROLES.md`, `AGENTS.md` and these notes | Claude Code made the edits; Varun reviewed the diff |
| 2026-11-14 | Adrian | Repo setup, roles, shared agent context | Claude Code wrote the scaffold; Adrian reviewed the files |
