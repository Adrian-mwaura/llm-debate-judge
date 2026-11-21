# Can a weak judge find the right answer when two agents debate?

Adrian Mwaura (method lead) and Varun Chopra (evaluation lead). Course research question 6.

## Question and hypothesis

Debate is proposed as a way for a weak supervisor to oversee stronger models (Khan et al. 2024).
We test it inside one model: the judge is weak (`deepseek-flash`, thinking off) and the debaters are strong (`deepseek-flash`, thinking on).

- **H1 (primary test):** the weak judge is more accurate on JudgeBench after reading a debate than when it spends the same API cost on extra votes of its own.
- **H2:** the benefit grows as the debaters think harder (effort `low` against `high`).
- **H3:** the benefit is larger on reasoning, math and coding, where thinking adds 16–33 points on DeepSeek's benchmarks, than on knowledge, where it adds about 3.

Other comparisons are exploratory. **Expected result:** a small gain, mostly on reasoning, math and coding.
Results are mixed when the judge sees what the debaters see (Kenton et al. 2024; Carro et al. 2026), so a null result is plausible and still informative.

## Method

- **Data:** JudgeBench (Tan et al. 2024): 620 hard questions, each with one correct and one wrong response. 20 went into a prompt dry run, so results use the other 600 (298 knowledge; 302 reasoning, math and coding).
- **Debaters (one round):** each is assigned one response. In one call it argues for it and critiques the other, without conceding or seeing the other argument.
- **Judge:** it sees the question and both responses, is told that exactly one is correct, and checks each debater claim rather than accepting it (Elasky et al. 2026). It judges both answer orders; a pair is correct only if the two verdicts together favour the correct response.

| Condition | What the judge reads |
|---|---|
| 1. Judge alone | Question and both responses |
| 2. **Votes (same-cost baseline)** | As 1, majority of k verdicts per order (k odd): the smallest k costing at least as much as each protocol |
| 3. One-sided argument | As 1, plus one of the two `high` debate arguments, chosen at random |
| 4–5. Debate | As 1, plus both arguments; debaters at effort `low` and `high` |
| 6. Thinking judge (reference) | As 1, judge thinking at `low` and `high`: the cost of upgrading the judge instead |

If budget allows, we add debaters at effort `max`.

## Pilot (done)

With the prompts frozen (git tag `prompts-v1`), a 200-pair pilot ran on 19 November for US$1.40.
The rule, set in advance: continue only if the thinking judge beats the weak judge (paired 95% interval above zero) and fewer than one in five wrong-side debaters concede; otherwise switch to question 8.
**Result: GO.** Weak judge 71.0% [64.4, 76.8]; thinking judge (`high`) 89.5% [84.5, 93.0]; difference **+18.5 points [+12.0, +25.0]**.
None of the 60 wrong-side debaters conceded, by hand labels that match the automatic check on all 60.

## Evaluation

- Accuracy with 95% Wilson intervals; paired tests (Newcombe interval, McNemar) of each condition against votes at the same cost.
- An accuracy-vs-cost plot, results by category, concession rates, and how often verdicts depend on answer order.
- 600 pairs give at most ±4 points and detect paired differences of about 6. The pilot pairs are among them, so we also report the 400 pairs outside the pilot.
- Every call is logged with tokens and cost; costs are matched at off-peak list price. Total spend: about US$12 (pilot US$1.40, full runs about US$10.20), within the US$30 limit.

## Division of work

- **Adrian:** prompts, the debate and one-sided protocols, counting concessions, error analysis.
- **Varun:** `chat()` helper, JudgeBench loader and scoring, vote baseline and cost matching, statistics, plots, results table.

**References:** Khan et al. 2024 (arXiv 2402.06782); Kenton et al. 2024 (2407.04622); Tan et al. 2024 (2410.12784); Elasky et al. 2026 (2605.27483); Carro et al. 2026 (2610.28539).
