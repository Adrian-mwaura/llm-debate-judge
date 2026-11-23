# Shared project notes

This is the running log for both members and their coding agents.
Read it at the start of every work session, and update it at the end.
Put the newest entries first in each section.

## Status

- **2026-11-23:** PR #18 (full results, `make_table.py`) is merged. A fresh clone of `main` rebuilds the table with `python scripts/make_table.py` and all 199 tests pass there. The README still said the experiments were not built, so it was rewritten (branch `varun/readme`): result, one-command rebuild, the script order with the cost of each step, layout.
- **2026-11-21:** **Full run done** (Varun, 11:08–12:01 UTC+8, off-peak weekend, commit `e386a90`, frozen against `prompts-v1`,
  US$8.68, matching the drop in the DeepSeek balance exactly). All 600 report pairs in every condition. `python scripts/make_table.py`:
  - Weak judge alone 70.5 [66.7, 74.0]; votes level off at 77–78 (k = 5 to 11); thinking judge 89.2 (`low`) and 89.7 (`high`).
  - Weak judge + debate 85.3 (`high`) and 85.2 (`low`); one-sided 75.5.
  - **H1 (primary): debate `high` minus 9 votes at the same cost: +8.0 points [+4.6, +11.4], McNemar p = 7e-6. Supported.**
  - H2: debaters `high` minus `low` +0.2 [-2.5, +2.8]: not supported; `low` debates are as good and cheaper.
  - H3: the gain is +11.9 [+7.3, +16.7] on reasoning/math/coding and +4.0 [-1.0, +9.1] on knowledge: in the predicted direction.
  - Exploratory: the thinking judge alone beats same-cost votes by 11–13 points, and is cheaper and better than debate.
    One-sided is no better than same-cost votes (-2.3 [-6.1, +1.4]): the second argument is what helps.
  - Split rate (verdict follows answer order): weak judge 21%, votes 14%, debate 8–9%, thinking judge 4–5%.
  - The 400 pairs outside the pilot give the same picture (H1 +7.5 [+3.3, +11.7]).
  - Concessions (automatic check): 0 of 600 wrong-side arguments at each effort. Incomplete calls: 165 of 13,200 vote calls
    and 9 of 1,200 weak-judge calls hit the 1,000-token cap (missing votes; counted as missing verdicts), 0 incomplete arguments.
  - `make_table.py` first picked 11 votes for H1 (k times the cost of one vote, an estimate); fixed to use measured vote costs, which
    gives 9 under the proposal's rule. The conclusion is the same either way (+7.5 against 11 votes).
- **2026-11-21:** Varun reviewed Adrian's PR #16 (hand labels and final GO: recomputed `decide` from his CSV independently, same result;
  only `hand_label` changed) and PR #17 (proposal with the pilot result). Updated PR #15: built on #16, votes now go to k = 11, because
  the proposal's rule is "the smallest odd k costing at least as much as each protocol" and debate `high` cost 8.95 weak verdicts in
  the pilot, so k = 9 would be too small if the full run costs even slightly more. **No full run yet; the deadline is Mon 23 Nov.**
  Then fixed Adrian's three #15 review points: the peak check now runs before every condition, and the concession checks are
  in the printed spend and in the estimate (shared US$5.68, debate US$5.34, total US$11.02). Balance after top-up: US$18.45.
- **2026-11-19:** **Final go/no-go: GO for question 6.** Adrian hand-labelled all 60 wrong-side pilot arguments blind (automatic verdict,
  topic and effort hidden, order shuffled): all 60 defend their assigned response, 0 concede at `low` and 0 at `high`. The hand labels agree
  with the automatic check on 60 of 60, so the automatic check can be trusted for the full run. `python scripts/run_pilot.py decide`
  wrote `go_no_go_final` into `results/pilot/summary.json` (no API calls). Its `decided_utc` was corrected by hand from 14:13 to 09:13 UTC:
  Adrian's PC clock reads UTC 5 hours ahead (Windows time zone set to UTC+3, clock showing UTC+8), to be fixed before he runs anything paid.
- **2026-11-19:** Varun built the full-run script (`scripts/run_full.py`, `src/debate_judge/full.py`): the 600 report pairs, in a
  "shared" group (weak judge, vote baseline, thinking judge low and high; useful for question 6 and question 8) and a
  "debate" group (debates low and high, one-sided, concession check; refuses without the final GO). Budget check before every
  condition. 8 new tests. PR #14 was merged before Adrian's review.
  Hugging Face is unreachable from Varun's PC at times; `load_judgebench()` falls back to the cached copy of the pinned revision.
- **2026-11-19:** Varun made the fixes from Adrian's post-merge reviews of PR #11 and PR #12 (Adrian asked for #12's before the pilot;
  they landed just after it, and none of them changes a pilot number). SciPy-only tests skip without SciPy, the rest run.
  The freeze check now needs tag `prompts-v1` and `prompts.py`, `judge.py`, `debate.py` identical to it with no uncommitted
  changes, so later commits to other files no longer block runs. `python scripts/run_pilot.py decide` reads the hand labels and writes
  `go_no_go_final`. Votes are capped at 15 per order with conditions over the cap flagged. Incomplete arguments leave the concession
  denominator. Checked on the pilot without API calls: concessions still 0/30 and 0/30 (no incomplete arguments), largest k 9,
  and the pilot ran on `5509a74` = the tag, so it passes the stricter check (recorded as `freeze_check_post_hoc`). 166 tests pass.
- **2026-11-19:** **Pilot done: automatic decision GO (question 6)**, pending Adrian's hand labels of the 60 wrong-side arguments.
  Prompts frozen as tag `prompts-v1` on `5509a74`; pilot run 13:01–13:24 UTC+8, off-peak (it was set for 12:00, but the PC slept), US$1.40.
  On the 200 pilot pairs: weak judge (thinking off) 71.0 [64.4, 76.8]; thinking `low` 89.0 [83.9, 92.6]; thinking `high` 89.5 [84.5, 93.0].
  **Thinking `high` minus weak: +18.5 points [+12.0, +25.0]**, McNemar p = 6e-8, so the weak-judge premise holds.
  H3 sign already: the gap is +24.0 [+14.4, +33.7] on reasoning/math/coding and +13.0 [+4.1, +21.9] on knowledge.
  Weak judge splits (same position in both orders) on 40/200 pairs, against 8/200 for the thinking judge.
  On the 30 debate pairs (too few to conclude; full run needed): weak judge with debate `high` 93.3 (+26.7 [+6.3, +45.2] over the weak judge alone),
  debate `low` 80.0 (+13.3, interval includes 0), one-sided 80.0.
  Automatic concession check: 0 of 30 wrong-side arguments concede at `low` and at `high`; 1 "Response A/B" rewrite in 120 arguments.
  4 of 1,600 judge calls were incomplete (2 weak judge cut at 1,000 tokens, 1 `low` at 16,000, 1 `high` blank); they count as missing verdicts.
  Measured cost per pair (`cost_match_usd`, both orders, incl. arguments): weak 0.00056, thinking low 0.00227, high 0.00300,
  debate low 0.00344, debate high 0.00500, one-sided 0.00277; suggested votes per order 5, 5, 7, 9, 5.
  Balance after the pilot: US$8.50. Outputs `results/pilot/`, logs `logs/calls/pilot_*.jsonl`.
- **2026-11-19:** Adrian made the fixes from his PR #8 review, which was merged before they were made (branch `adrian/data-fixes`):
  `summarize()` no longer counts knowledge pairs twice (group keys are now `group:knowledge` and `group:rmc`); the pilot is
  balanced by response author (gpt or claude) as well as category; the 20 dry-run pairs are unchanged, so the dry run stays valid
  and those pairs stay out of reported results; real-data tests now fail instead of skipping, except when `datasets` is missing or
  Hugging Face is unreachable; `non_pilot_pairs()` gives the 400-pair check. **The 200 pilot pairs change**; the pilot has not run yet.
  The project is about a day and a half behind `docs/SCHEDULE.md`. We keep every agreed step in order and work into the night rather than skip.
- **2026-11-18:** Varun built the pilot runner (`scripts/run_pilot.py`, logic in `src/debate_judge/pilot.py`) and ran the
  **real dry run on the 20 dry-run pairs** (US$0.15, off-peak). Everything works: 0 incomplete replies, 0 unparsed verdicts,
  0 incomplete debater arguments, 0 "Response A/B" rewrites, 0 automatic concessions. Varun read two wrong-side `high`
  arguments: both defend the wrong answer firmly with checkable specifics. `high` debaters used about 2,800 reasoning tokens.
  Dry-run accuracy (n=20, too small to decide anything): weak judge 60.0, thinking `low` 70.0, `high` 70.0.
  Measured cost per pair (both orders, incl. debater arguments, `cost_match_usd`): weak judge 0.00054, thinking low 0.00195,
  high 0.00298, debate low 0.00330, debate high 0.00475, one-sided 0.00262. Next: freeze prompts, run the 200-pair pilot.
  The project is about a day behind `docs/SCHEDULE.md`: the go/no-go due Wednesday midday moves to Wednesday night.
- **2026-11-17:** Adrian built the debaters (PR #10): debater prompt `debater-v1` (one call per side, defend and critique, at most
  250 words, "my response"/"the other response" instead of letters), one-sided argument reusing a `high` debate argument, the
  concession check `concession-v1`, and `temperature` passed through `judge_pair()` (Varun's PR #6 request); 80 offline tests.
  Adrian also wrote the schedule (PR #7, finish by Friday 20 November), corrected it to UTC+8 (PR #9; his PC's time zone is set to UTC+3,
  to be fixed), and reviewed PR #8 (seven points, posted as a review comment).
- **2026-11-17:** Varun built `src/debate_judge/stats.py`: Wilson 95% intervals for accuracy, Newcombe's paired interval for
  the difference between two conditions on the same pairs, McNemar's exact test, a seeded paired bootstrap as a cross-check,
  and per-group versions for H3. The go/no-go rule is `paired_comparison(weak, thinking).b_better`.
  Checked against SciPy (Wilson, McNemar), the research report's interval widths, the bootstrap, and a coverage simulation (about 95%).
  Branch `varun/stats`, built on PR #8. Adrian's PR #9 (schedule in UTC+8) approved; his commits show his time zone is set to UTC+3.
- **2026-11-17:** Varun built `src/debate_judge/data.py`: JudgeBench loader pinned to revision `57dd5e0` (620 pairs: 350 gpt, 270 claude;
  308 knowledge, 149 reasoning, 90 math, 73 coding), fixed stratified subsets (20 dry-run pairs, never reported; 200 pilot pairs,
  inside the 600 reported pairs so the full run reuses their cache), and both-order scoring with JudgeBench's rule.
  Scoring reproduces JudgeBench's published results exactly (GPT-4o 50.9, DeepSeek-R1 73.1, o3-mini high 80.9).
  79 tests pass with PRs #6 and #7 (77, plus 2 that download JudgeBench). Varun merged PR #5 (proposal draft); its open points (pilot result line, cost wording, odd vote counts) are for Wednesday.
  Labels lean to A (336 `A>B`, 284 `B>A`), one more reason to score in both orders.
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
- [ ] Both: write the 1-page proposal (`report/proposal.md`), due 2026-11-23. Draft merged (PR #5); add the pilot result and fix the review points.
- [x] Both: settle the go/no-go pilot rule (200 pairs; the thinking judge better with a paired 95% interval above zero, and fewer than
  1 in 5 wrong-side debaters concede). Applied 2026-11-19: GO.
- [x] Evaluation lead (Varun): `chat()` helper with cache and call log (PR `varun/chat-helper`).
- [x] Evaluation lead (Varun): confirm the model id (`deepseek-flash` is in the models list).
- [x] Evaluation lead (Varun): add credit, then rerun `python scripts/check_model.py` to confirm the thinking switch (passed).
- [x] Evaluation lead (Varun): JudgeBench loader and both-order scoring (`data.py`, branch `varun/judgebench-loader`).
- [x] Evaluation lead (Varun): `stats.py` (branch `varun/stats`).
- [x] Evaluation lead (Varun): pilot runner and the real dry run (branch `varun/pilot-runner`).
- [x] Both: freeze the prompts (tag `prompts-v1` on `5509a74`, pushed 2026-11-19).
- [x] Varun: run the 200-pair pilot off-peak (2026-11-19, US$1.40; automatic decision GO).
- [x] Varun: fixes from Adrian's post-merge reviews of PR #11 (SciPy-only skip) and PR #12 (strict freeze check, `decide` step,
  vote cap 15, concession denominator), branch `varun/pilot-results`.
- [x] Adrian: fill `hand_label` for the 60 wrong-side rows in `results/pilot/concession_review.csv` and run
  `python scripts/run_pilot.py decide` (done 2026-11-19: GO; branch `adrian/pilot-labels`, PR #16, reviewed by Varun 2026-11-21).
- [x] Evaluation lead (Varun): vote baseline and the full-run script (`scripts/run_full.py`, PR #15; votes up to k = 11).
- [x] Varun merged #16 and #17 (2026-11-21 10:44).
- [x] Varun: Adrian's three PR #15 review points (peak check before each condition; concession checks in the spend and in the estimate).
- [x] Adrian: approve and merge PR #15 (merged 2026-11-21 11:03).
- [x] Top up: balance US$18.45 on 2026-11-21 (US$10 added).
- [x] Varun: full run, shared then debate (2026-11-21 11:08–12:01, US$8.68). Results on branch `varun/full-results`.
- [x] Evaluation lead (Varun): `make_table.py` (results table with intervals and the H1 test at matched cost) and the accuracy-vs-cost plot
  (branch `varun/make-table`). H1 is taken as debate `high` against its same-cost votes; Adrian to confirm in the PR.
- [x] Both: add the pilot result line to `report/proposal.md` (Adrian, PR #17).
- [ ] Adrian: review and merge `varun/make-table`, then `varun/full-results`.
- [ ] Adrian: error analysis from `results/full/pairs.jsonl` and the logs (what debate fixes, what it breaks, one-sided, by category);
  report sections Method and Analysis.
- [ ] Varun: report sections Experiment setup, Results (Tables 1–2 and the plot from `results/full/`) and Limitations.
- [ ] Both: Question and hypothesis, Collaboration; final edit to 6–8 pages; rebuild the table from a fresh clone; submit Mon 23 Nov.
- Optional, budget left: `max`-effort debaters (about US$3 on 300 pairs), only if the report is on track.
- [x] Method lead (Adrian): judge prompt and `judge_pair()` (branch `adrian/judge`).
- [x] Dry-run the judge and debaters with the real API on `dry_run_pairs()` (done by Varun with the runner, 2026-11-18).
- [x] Method lead (Adrian): debater prompt, one-round debate and one-sided argument (`debate.py`, PR #10).

## For the report

- **Primary test (Adrian's PR #11 review):** H1, the weak judge after a debate against the weak judge with votes at the same cost,
  on the 600 report pairs, is the one primary test. Every other comparison (by group, by category, against the thinking judge,
  one-sided, debater effort) is exploratory, with no correction for multiple comparisons; say so in Method and Limitations.
- **Limitations:** JudgeBench has been public since 2024, so `deepseek-flash` may have seen its questions and responses in training.
- **Limitations:** the 200 pilot pairs decide go/no-go and are also part of the 600 reported pairs (to save money).
  Say so, and also report results on the 400 non-pilot pairs as a check; that is a slice of the same run and costs nothing.
- **Method:** the judge is told in every condition that exactly one response is correct (true of every JudgeBench pair). Varun's PR #6 review.
- **Results/limitations:** the go/no-go used the pilot pairs, which are also reported; report the 400 non-pilot pairs as a check.
  About 0.25% of judge calls (4 of 1,600 in the pilot) were incomplete and count as missing verdicts; say so.
- **Analysis idea:** the weak judge picks the same position in both orders on 20% of pilot pairs (thinking judge 4%); position bias
  is one way debate could help the weak judge, so compare split rates across conditions.
- **Method:** one round only. Debaters do not see or rebut each other's arguments; the second round was dropped for time.
- **Method:** the one-sided condition reuses one of the two `high` debate arguments, so it differs from the debate only in
  whether the judge sees the second argument.

## Decisions

| Date | Decision | Why | Who |
|---|---|---|---|
| 2026-11-19 | Go/no-go: GO for question 6. Thinking judge minus weak judge +18.5 points [+12.0, +25.0] on 200 pilot pairs; 0 of 30 wrong-side debaters concede at `low` and at `high` (hand labels, 60/60 agreement with the automatic check) | Both conditions of the rule agreed before the pilot are met | Adrian (hand labels and `decide`); Varun to confirm in the PR |
| 2026-11-17 | Debater prompt `debater-v1`: one call per side, defend and critique, at most 250 words, "my response"/"the other response" instead of letters | One argument then fits both answer orders; letters can't be swapped safely because MMLU-Pro answers use option letters | Adrian |
| 2026-11-17 | One-sided condition reuses one `high` debate argument, the correct side about half the time | No extra debater calls (saves about US$1.75), and a cleaner comparison with the debate | Adrian |
| 2026-11-17 | Concessions: pilot runs debaters at `low` and `high` on 30 pilot pairs, both sides (120 calls, about US$0.20); Adrian reads the 30 wrong-side arguments per effort by hand; the full run uses a thinking-off check, validated against those labels | The go/no-go needs a reliable concession count; the same calls give the measured debater costs Varun needs to set k | Adrian |
| 2026-11-17 | Keep 600 reported pairs with the 200 pilot pairs inside them; report the 400 non-pilot pairs as a check | Avoids paying for extra pairs; the check is free | Adrian |
| 2026-11-17 | Finish everything by Friday 20 November, following `docs/SCHEDULE.md`; drop the two-round debate, and run max effort only if time and budget allow | Leaves Saturday to Monday as buffer before the 23 November deadline | Adrian; Varun to agree in the PR |
| 2026-11-16 | Match costs on `cost_match_usd`: off-peak list price with no cache discount | Peak hours and caching would otherwise make the same compute look cheaper or dearer depending on when and in what order we ran it | Varun |
| 2026-11-16 | Research question: question 6 (weak judge, two debaters), run on JudgeBench; question 8 is the fallback | Most novel option; the JudgeBench redesign gives a real strength gap and simpler protocols; a fair null result is acceptable under the brief; code is shared with question 8 | Varun, matching Adrian's lean; Adrian to confirm |
| 2026-11-16 | Varun is Role B (evaluation lead), Adrian is Role A (method lead) | Varun chose Role B; final once Adrian approves the PR | Varun |
| 2026-11-14 | Proposed two roles, Role A (method lead) and Role B (evaluation lead); each of us picks one, and a tie is settled on a call | The split works for any research question, both of us write code, and Varun should choose rather than be assigned | Adrian |
| 2026-11-14 | Match costs on logged tokens and dollars, not on the number of calls | Debate prompts get longer each round | Both |

## Budget ledger (cap: US$30)

| Date | Who | Run | Dataset and number of questions | Cost (US$) | Total so far (US$) |
|---|---|---|---|---|---|
| 2026-11-21 | Varun | `run_full.py debate` (debates high/low, one-sided, concession checks; weekend, commit e386a90) | JudgeBench report pairs, 600 | 4.8452 | 10.2230 |
| 2026-11-21 | Varun | `run_full.py shared` (weak judge, votes k ≤ 11, thinking judge low/high; weekend, commit e386a90) | JudgeBench report pairs, 600 | 3.8298 | 5.3778 |
| 2026-11-19 | Varun | `run_pilot.py pilot` (go/no-go pilot, off-peak, tag prompts-v1, commit 5509a74) | JudgeBench pilot pairs, 200 (debaters on 30) | 1.3993 | 1.5480 |
| 2026-11-18 | Varun | `run_pilot.py dry` (prompt dry run, off-peak, commit adf143e) | JudgeBench dry-run pairs, 20 (debaters on 5) | 0.1485 | 0.1487 |
| 2026-11-16 | Varun | `check_model` (setup check, 6 tiny calls, all thinking levels, peak hours) | none; one arithmetic question | 0.0002 | 0.0002 |

Account balances: Varun US$10.00 topped up (2026-11-16); US$8.50 left after the pilot (DeepSeek balance API, 2026-11-19);
US$10.00 more added, balance US$18.45 (2026-11-21). Top-ups so far US$20; the US$30 cap is on spend, not on top-ups.
After the full run: balance US$9.77 (2026-11-21 12:05), a drop of US$8.68, matching the logged spend. Total spend US$10.22 of US$30.

## Experiment log

<!-- One entry per run: date, who, git commit, settings, accuracy, cost, notes. -->

- **2026-11-21, Varun, full run, commit `e386a90` (frozen against `prompts-v1`: judge-v1, debater-v1, concession-v1).** The 600 report pairs.
  Weak judge: thinking off, temperature 1.0, max_tokens 1000; votes = samples 0–10 per order, majority of the first k for k = 1–11.
  Thinking judge `low` (16000) and `high` (32000). Debaters `low` and `high`, one round, both sides; weak judge reading both arguments;
  one-sided = one `high` argument (seed `one-sided-v1`). Automatic concession check on all 2,400 arguments.
  Accuracy and tests: see Status above and `results/full/table.md`. Spend US$8.6750 (shared 3.8298, debate 4.8452 incl. concession
  checks 0.1595). Outputs `results/full/` (pairs.jsonl, concessions.jsonl, table.md, table.csv, accuracy_vs_cost.png), logs `logs/calls/full_*.jsonl`.

- **2026-11-19, Adrian, go/no-go decision (no API calls).** Hand labels for the 60 wrong-side pilot arguments in
  `results/pilot/concession_review.csv`; `python scripts/run_pilot.py decide` → `go_no_go_final`: GO (question 6).
  Concessions by hand: 0/30 at `low`, 0/30 at `high`; agreement with the automatic check 60/60. Spend US$0.
- **2026-11-19, Varun, pilot, tag `prompts-v1` = commit 5509a74 (judge-v1, debater-v1, concession-v1).** 200 pilot pairs
  (100 knowledge, 48 reasoning, 29 math, 23 coding; 112 gpt, 88 claude). Weak judge: thinking off, temperature 1.0, max_tokens 1000.
  Thinking judge: `low` (16000) and `high` (32000). Debaters `low` and `high` on the first 30 pilot pairs, both sides;
  weak judge reading each debate and the one-sided argument. Seed: subsets `SUBSET_SEED` 20261117, one-sided `one-sided-v1`.
  Accuracy: weak 71.0, low 89.0, high 89.5 (n=200); debate low 80.0, debate high 93.3, one-sided 80.0 (n=30).
  Go/no-go: high minus weak +18.5 [+12.0, +25.0]; automatic concessions 0/30 and 0/30. Spend US$1.3993. Full numbers in `results/pilot/summary.json`.
- **2026-11-18, Varun, dry run, commit adf143e (prompts judge-v1, debater-v1, concession-v1).** 20 dry-run pairs; weak judge
  thinking off, temperature 1.0, max_tokens 1000; thinking judge `low` (16000) and `high` (32000); debaters `low` and `high` on 5 pairs,
  both sides. Accuracy (not reported; n too small): weak 60.0, low 70.0, high 70.0; debate low 4/5, debate high 5/5, one-sided 5/5.
  No incomplete or unparsed calls. Spend US$0.1485. Outputs: `results/dry/`, logs `logs/calls/dry_*.jsonl`.

## Collaboration log

Record entries here for the report's Collaboration section.

| Date | Who | What | AI tools used and how the code was checked |
|---|---|---|---|
| 2026-11-23 | Varun | Fresh-clone check of `main`; README rewrite | Checked in a fresh clone from GitHub that `make_table.py` rebuilds the table (only line endings differ from the committed files; the plot is byte-identical), that the tests pass and that the API key is in no tracked file; every command, link and number in the new README was checked against the repo |
| 2026-11-21 | Varun | Full run and the first real results table | Claude Code ran both groups in the background with a keep-awake request, checked every condition has all 600 pairs, counted incomplete calls, checked the spend against the account balance (equal) and the logs for the API key (none), then built the table; reading the real table it caught that `make_table` chose 11 votes for H1 by estimating vote costs as k times one vote, fixed it to use measured costs (9 votes, as the rule says) and added a test with the real numbers |
| 2026-11-21 | Varun | `make_table.py`, `table.py` and 11 tests | Claude Code wrote them in a separate git worktree while the full run used the main one; tests on synthetic records with known answers check the proposal's same-cost rule (including the switch to 11 votes), that H1 detects a clear gain and none when there is none, the 400-pair restriction, and that the table and plot are written |
| 2026-11-21 | Varun | Adrian's PR #15 review points (3) and 7 tests | Claude Code made them; tests check the peak check at the window edges and the weekend, that a run drifting into peak stops before the next condition with finished work saved, the concession-check estimate (pilot cost per call x 4 per pair) and that nested vote records are counted once in the spend; the new estimate (US$11.02) was run against the real pilot logs |
| 2026-11-21 | Varun | Reviewed PR #16 and #17; updated PR #15 (rebased on #16, votes to k = 11) | Claude Code recomputed `decide` from Adrian's labelled CSV with the committed code (GO, 0/60 concessions, 60/60 agreement) and checked that no CSV cell other than `hand_label` changed; it checked the proposal's numbers (298/302 pairs, ±4 points, US$12) and found that the proposal's k rule needs votes beyond 9 |
| 2026-11-19 | Adrian | Hand labels for the 60 wrong-side pilot arguments; final go/no-go | Adrian labelled by hand on a page Claude Code built from the committed pilot files: automatic verdict, topic and effort hidden, order shuffled, so the labels are an independent check. Claude Code checked the labels matched the 60 wrong-side rows, wrote them into the CSV (only `hand_label` changed), ran `decide`, and corrected the timestamp the PC clock got wrong |
| 2026-11-19 | Adrian | Post-merge reviews of PR #11 and #12 | Claude Code read the code and checked the interval formulas against their published definitions; found the SciPy import that stops the whole suite, the too-blunt freeze check, the missing path from hand labels to the decision, the missing vote cap and the concession denominator; posted as PR comments |
| 2026-11-19 | Varun | Full-run script and vote baseline; 8 tests | Claude Code wrote them; tests with a fake API check vote k=1 equals the judge alone, vote costs scale with k, debate and one-sided costs include their arguments, and the budget check stops a run while keeping finished conditions; a test against the NOTES cost figures caught an underestimate of the vote cost (votes 2–9 are new on all 600 pairs, not 400) |
| 2026-11-19 | Varun | Fixed Adrian's PR #11 and #12 review points; 22 new tests | Claude Code made the fixes; freeze-check tests run against a throwaway git repo; the SciPy fix was checked by running the suite with SciPy made unimportable (11 SciPy tests skip, 155 run); the new rules were applied to the committed pilot files without API calls and changed no number. What went wrong: #11 and #12 were merged before Adrian reviewed them, and the pilot ran before his #12 fixes; from now on PRs wait for review |
| 2026-11-19 | Varun | Reviewed and merged PR #13; tagged the prompts; ran the pilot | Claude Code ran the full suite on main + #13 (144 pass, real-data tests included), then scheduled the tag and pilot for the off-peak window; checked the logs for the API key before committing (none; one "Risk-free" false positive) |
| 2026-11-19 | Adrian | Fixes from the PR #8 review (`data.py`) and 6 new tests | Claude Code made them; it checked on synthetic data that the dry-run pairs and the 600 reported pairs are unchanged and only the pilot changes; real-data tests compare the dry-run pairs with the committed dry-run logs (run once `datasets` is installed) |
| 2026-11-18 | Varun | Pilot runner (`pilot.py`, `run_pilot.py`), 10 tests, real dry run | Claude Code wrote them; an end-to-end test with a fake API caught one bug (wrong argument passed to `one_sided_arguments`) before any money was spent; then the real 20-pair dry run, with two wrong-side arguments read by hand |
| 2026-11-17 | Adrian | Debater prompt, `debate.py`, concession check and 27 tests (PR #10) | Claude Code wrote them; tests use a fake `chat()` (80 pass); a test checks that one argument reads correctly in both answer orders; Varun's dry run then checked them on real pairs |
| 2026-11-17 | Adrian | Reviewed PR #8 (`data.py`) | Claude Code read the diff and ran the tests; found seven points, including knowledge pairs counted twice in `summarize()` and a pilot not balanced by response author; posted as a review comment |
| 2026-11-17 | Adrian | Schedule (PR #7) and its UTC+8 correction (PR #9) | Claude Code drafted them after Adrian agreed the plan; the UTC+3 error came from the agent trusting the PC's time zone setting; caught when Adrian gave his local time |
| 2026-11-17 | Varun | `stats.py` (intervals, paired tests) and 23 tests | Claude Code wrote them; Wilson and McNemar checked against SciPy, interval widths against the research report, Newcombe against a 20,000-resample bootstrap and a 1,500-trial coverage simulation (about 95%); caught and fixed one deviation from Newcombe's formula while re-reading the paper's adjustment rule |
| 2026-11-17 | Varun | `data.py` (loader, subsets, scoring) and 26 tests | Claude Code wrote them; checked the real dataset's counts, and scored three of JudgeBench's published judge output files with `score_pair`, matching Adrian's script and the published scores exactly; 79 tests pass with PRs #6 and #7 |
| 2026-11-17 | Varun | Reviewed PR #6 (judge) and PR #7 (schedule) | Claude Code ran PR #6's tests in a separate worktree (53 pass) and read the code; comments: pass `temperature` for votes, check JSON mode with thinking in the dry run |
| 2026-11-16 | Adrian | Judge prompt, `judge_pair()` and 24 unit tests | Claude Code wrote them, adapting JudgeBench's vanilla judge prompt; tests use a fake `chat()` and the full suite passes (53); Adrian to review the diff in the PR |
| 2026-11-16 | Adrian | Reviewed PR #4 (`chat()`) and merged it after the fixes | Claude Code read the code and found seven issues, posted as a review; after Varun's fixes it re-read the diff and checked the committed API log for keys |
| 2026-11-16 | Varun | Fixed the seven points from Adrian's PR #4 review | Adrian's Claude Code found them by reading the code; Varun's Claude Code fixed them and added a test for each (29 tests pass); a good example of agent-assisted cross-review for the report |
| 2026-11-16 | Varun | `chat()` helper, unit tests, `scripts/check_model.py` | Claude Code wrote the code and tests; Varun reviewed it; the unit tests pass with a fake client; not yet checked against the real API |
| 2026-11-16 | Varun | Recorded the question 6 choice and hypothesis in `AGENTS.md` and these notes | Claude Code made the edits; Varun reviewed the diff |
| 2026-11-16 | Varun | Reviewed PR #2 (research report) twice and merged it | Claude Code checked that it merges cleanly and recomputed the scores, cost totals and confidence intervals; findings posted as a review comment (pilot size, vote cap) |
| 2026-11-16 | Adrian | Research report comparing the nine questions | Claude Code searched and read the sources (official DeepSeek docs, dataset pages, paper abstracts) and wrote the report; its limits section lists what was not verified; Adrian reviewed it, and Varun reviewed and merged it (PR #2) |
| 2026-11-16 | Varun | Recorded role choice in `docs/ROLES.md`, `AGENTS.md` and these notes | Claude Code made the edits; Varun reviewed the diff |
| 2026-11-14 | Adrian | Repo setup, roles, shared agent context | Claude Code wrote the scaffold; Adrian reviewed the files |
