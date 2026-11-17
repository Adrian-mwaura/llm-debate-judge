<!--
Draft for Varun's review. Before submitting: add the pilot's result in one line,
or switch the proposal to question 8 if the pilot fails. Target length: one page.
-->

# Can a weak judge find the right answer when two agents debate?

Adrian Mwaura (method lead) and Varun Chopra (evaluation lead). Course research question 6.

## Question and hypothesis

Debate is proposed as a way for a weak supervisor to oversee stronger models (Khan et al. 2024).
We test it inside one model by making the judge weak (`deepseek-flash` with thinking off) and the debaters strong (`deepseek-flash` with thinking on).

- **H1:** the weak judge is more accurate on JudgeBench after reading a debate than when it spends the same API cost on extra votes of its own.
- **H2:** the benefit grows as the debaters think harder (effort `low` against `high`).
- **H3:** the benefit is larger on reasoning, math and coding questions, where thinking adds 16–33 points on DeepSeek's own benchmarks, than on knowledge questions, where it adds about 3.

**Expected result:** a small gain, mostly on reasoning, math and coding.
Results are mixed when the judge sees the same information as the debaters (Kenton et al. 2024; Carro et al. 2026), so a null result is plausible and still informative.

## Method

- **Data:** all 620 JudgeBench pairs (Tan et al. 2024). Each pair is a hard question with one correct and one wrong response: 308 knowledge, 312 reasoning, math and coding.
- **Debaters:** each is assigned one response and argues for it without conceding.
- **Judge:**
  - It sees the question and both responses, and is told to check each debater claim rather than accept it (Elasky et al. 2026).
  - It gives a verdict in both answer orders. A pair counts as correct only if the two verdicts together favour the correct response.

| Condition | What the judge reads |
|---|---|
| 1. Judge alone | Question and both responses |
| 2. **Votes (same-cost baseline)** | As 1, majority of up to 15 verdicts per order, matched to each protocol's cost |
| 3. One-sided argument | As 1, plus one argument (effort `high`) for a randomly chosen response |
| 4–5. Debate | As 1, plus one argument for each response that also critiques the other; debaters at effort `low` and `high` |
| 6. Thinking judge (reference) | As 1, judge thinking at effort `low` and `high`: the cost of upgrading the judge instead |

If budget allows, we add debaters at effort `max` (300 pairs) and a second debate round (200 pairs).

## Pilot and fallback

A 200-pair pilot first compares the judge with thinking off and on, and runs 30 debaters on the wrong side.
We continue only if the thinking judge is clearly better (paired 95% confidence interval above zero) and fewer than one in five debaters concede.
Otherwise we switch to question 8 ("Does more computation make the judge more accurate?") on the same code.
All prompts are fixed before the pilot.

## Evaluation

- Accuracy with 95% confidence intervals, and paired tests of each condition against votes at the same cost.
- An accuracy-vs-cost plot; results by category; how often debaters concede; how often verdicts flip with answer order.
- 620 pairs give about ±3.8 points and detect paired differences of about 6 points.
- Every API call is logged with tokens and cost; costs are matched at list price. Estimated total: about US$21 off-peak, including the pilot, within the US$30 limit.

## Division of work

- **Adrian:** prompts, the debate and one-sided protocols, counting concessions, error analysis.
- **Varun:** `chat()` helper, JudgeBench loader and scoring, vote baseline and cost matching, statistics, plots, results table.

**References:** Khan et al. 2024 (arXiv 2402.06782); Kenton et al. 2024 (2407.04622); Tan et al. 2024 (2410.12784); Elasky et al. 2026 (2605.27483); Carro et al. 2026 (2610.28539).
