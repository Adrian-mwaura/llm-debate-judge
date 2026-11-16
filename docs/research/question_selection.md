# Which research question should we pick?

Research by Adrian with Claude Code, 2026-11-16. This is input for the meeting with Varun, not a decision.
The proposal is due 2026-11-23.

## Recommendation

**Pick question 8: "Does more computation make the judge more accurate?"**
Frame it as a comparison of the *kinds* of computation a judge can buy at the same API cost:
thinking harder, voting over several verdicts, solving the question first, or reading a debate between two advocates.
Add our own method on top: a judge that spends extra computation only when its two answer orders disagree.

Why this one:

1. **The effect is large enough to measure.** On JudgeBench, published judges range from 51% (GPT-4o) to 81% (o3-mini at high reasoning effort), and o3-mini alone gains 10 points from low to high effort (table below). The debate questions (1–5) are fighting over 0–3 points on MMLU-Pro, which our budget cannot detect reliably.
2. **It fits the budget.** A full design costs about US$14–20 at off-peak prices. A judge call is cheap, and the whole dataset is only 620 pairs.
3. **It leaves room for a new idea.** It is already known that more reasoning helps a judge. I found no head-to-head comparison of the kinds of computation at equal cost, and none on `deepseek-flash`, which has a built-in four-level thinking dial.
4. **The required plot is the result.** The brief asks for an accuracy-vs-cost plot, and for this question that plot is the main finding.
5. **It uses everything we build.** The debate engine becomes one arm (two advocates argue, the judge decides), and question 7's bias analysis explains the errors.

**Second choice: question 7** (judge bias). It is the safest and cheapest, and it reuses the same code, so it is also the fallback if question 8 hits a problem.
**Third choice: question 6** (weak judge, two debaters). It is the most novel, but also the riskiest and the hardest to compare fairly at equal cost.

## Facts that drive the choice

All of these are checked against primary sources (listed at the end).

### The model and its price

- `deepseek-flash` is DeepSeek-V4.1-Flash-1017. It is the name to use in the API.
- **Price per million tokens:** input US$0.15 off-peak and US$0.30 at peak; output US$0.60 off-peak and US$1.20 at peak; cached input US$0.003 off-peak.
- **Peak hours are 01:00–04:00 and 06:00–10:00 UTC, Monday to Friday** (04:00–07:00 and 09:00–13:00 in UTC+3). Everything else, including weekends, is off-peak at half price. Running off-peak doubles our budget.
- **Thinking is on by default**, at effort `high`. Thinking tokens are billed as output. Switch it with `extra_body={"thinking": {"type": "disabled"}}`, or set `reasoning_effort` to `none`, `low`, `high` or `max`. Our `chat()` helper must set this on every call, or every call silently pays for thinking.
- **`temperature` has no effect in thinking mode.** We cannot tune how different the samples are when thinking is on.
- `logprobs` (token probabilities) and JSON output are supported. There is no `n` or `seed` parameter, so k samples means k calls.
- Input caching is automatic for repeated prefixes. The concurrency limit is 2,500 requests, so runs finish quickly.

### The datasets

| Dataset | Size | Where `deepseek-flash` stands | Room to improve |
|---|---|---|---|
| GSM8K | 1,319 test questions | No official score for the chat model; the base model scores 90.8 with 8 examples | Very little. Frontier models are near the ceiling |
| MMLU-Pro | 12,032 test questions, 10 options | V4-Flash: 83.0 without thinking, 86.4 with thinking `high` (official model card) | About 14–17 points, minus some label noise. Thinking adds only 3.4 points |
| JudgeBench | 620 pairs (350 from GPT-4o, 270 from Claude 3.5 Sonnet), one correct and one wrong response each | Not published for V4.1 | Large. See the next table |

The official scores are for V4-Flash. `deepseek-flash` now points to V4.1-Flash, which I could not find official scores for.

### How published judges do on JudgeBench

I computed these from the judge outputs that the JudgeBench leaderboard publishes (GPT-4o split, 350 pairs).
A pair counts as correct only if the two answer orders together favour the right response. A **split** means the judge picked the same position both times, so its verdict flipped when the order flipped.

| Judge | Score | Right in both orders | Wrong in both | Split | Tie or no verdict |
|---|---|---|---|---|---|
| GPT-4o, plain prompt | 50.9 | 50.9 | 19.4 | 29.7 | 0.0 |
| GPT-4o, Arena-Hard prompt | 56.6 | 50.3 | 17.4 | 21.7 | 10.6 |
| GPT-4o, multi-agent debate judge (ChatEval) | 34.0 | 24.9 | 15.4 | 41.7 | 18.0 |
| Claude 3.5 Sonnet | 64.3 | 60.0 | 14.0 | 18.3 | 7.7 |
| DeepSeek-R1 | 73.1 | 63.1 | 5.7 | 18.0 | 13.1 |
| o3-mini, reasoning effort low | 70.6 | 66.9 | 12.6 | 12.3 | 8.3 |
| o3-mini, reasoning effort medium | 76.6 | 75.4 | 9.7 | 11.1 | 3.7 |
| o3-mini, reasoning effort high | 80.9 | 79.7 | 9.1 | 8.6 | 2.6 |

What this shows:

- **More reasoning helps a lot:** the same model gains 10 points from effort low to high. Kim et al. (2025) report the same trend.
- **A naive multi-agent debate judge is worse than a single judge** (34.0 against 56.6 for the same model). Ma et al. (2025) find that debate between judges amplifies bias.
- **Order matters even for strong judges.** 9–30% of pairs are split. In DeepSeek-R1's 63 splits, it chose the second response 61 times. Wang et al. (2025) independently report that reasoning models prefer later positions. Whether `deepseek-flash` does the same is untested.
- The knowledge category (154 pairs from MMLU-Pro) is the hardest: o3-mini at effort high scores 67.5 there, and DeepSeek-R1 59.1.

The script for this table is `docs/research/judgebench_published_scores.py`.

## How I scored the questions

Each question gets 1–5 on the three grading criteria we control by choosing well, weighted as in the grading table:
innovation (30), experiment design (20), and results and analysis (25). The maximum is 75.
Budget fit and risk are shown separately.

| Rank | Question | Innovation | Design | Results | Score /75 | Est. cost | Risk |
|---|---|---|---|---|---|---|---|
| 1 | **8. More computation for the judge** | 4 | 5 | 5 | **69** | US$14–20 | Low |
| 2 | 7. Judge bias and how to reduce it | 3 | 5 | 4 | 58 | US$8–12 | Low |
| 3 | 6. Weak judge, two debaters | 5 | 3 | 3 | 57 | US$10–20 | High |
| 4 | 5. How much communication | 3 | 4 | 3 | 49 | US$15–20 | Medium |
| 5 | 4. Agent confidence | 3 | 4 | 2.5 | 46.5 | US$15–20 | Medium |
| 6 | 2. Thinking and non-thinking agents | 4 | 3 | 2 | 46 | US$23+ | High |
| 7 | 3. Correct or spread errors | 2 | 4 | 3 | 43 | US$12–18 | Medium |
| 8 | 9. Judge and human experts | 2 | 2 | 3 | 35 | US$3–6 | Medium |
| 9 | 1. Debate against majority vote | 1 | 4 | 2 | 32 | US$10–18 | Medium |

The scores are my judgement from the evidence below. The ranking is stable at the top: question 8 leads on every criterion except innovation, where question 6 is ahead.

## The nine questions, one by one

### 1. Does debate beat majority voting at the same cost?

- **What is known:** this is the most studied question in the field, and the answer is mostly no.
  Choi et al. (2025, NeurIPS spotlight) show that voting explains most of debate's gains and that debate alone does not raise expected accuracy.
  Smit et al. (2023), Zhang et al. (2025) and Tran and Kiela (2026) reach similar conclusions.
  One recent study disagrees: Wunderlich et al. (2026) find debate 1.3 points ahead of self-consistency on MMLU-Pro at equal compute.
- **Problem for us:** the expected difference is about 1–3 points. Detecting 1.3 points needs roughly 3,700 questions, which is over budget. Detecting 3 points needs about 700.
- **Verdict:** every debate question includes this comparison anyway. On its own it has no new idea in it.

### 2. Do thinking and non-thinking agents make debate better?

- **What is known:** mixing *different models* sometimes helps (Zhang et al. 2025) and sometimes does not (Ferreira et al. 2026). I found no study that mixes thinking and non-thinking modes of one model at matched cost, so there is a gap.
  A related finding: a thinking model changed its answer in 2–6% of cases against 42–90% for non-thinking models (Bertalanič and Fortuna 2026).
- **Problem for us:** thinking adds only 3.4 points on MMLU-Pro, so every condition lands within about 3 points of the others. Thinking calls cost about six times more, so we could afford roughly 300–500 questions, which cannot separate differences that small.
- **Verdict:** a real gap, but we cannot afford to measure it on our datasets.

### 3. Does debate correct errors or spread them?

- **What is known:** heavily studied in 2025–2026: Wynn et al. (2025), Bertalanič and Fortuna (2026), Qian (2026).
  Hao et al. (2026) already ran this analysis on MMLU-Pro with DeepSeek-V4-Flash among their models.
- **Verdict:** rich material for the analysis section, but the ground is covered, including on our model family and dataset.

### 4. Can agent confidence make debate better?

- **What is known:** also crowded: ReConcile (Chen et al. 2023), DebUnc (Yoffe et al. 2024), ConfMAD (Lin and Hooi 2025), Zhu et al. (2026), Elahi et al. (2026).
- **In our favour:** the API returns token probabilities, so we could compare stated confidence with measured confidence at no extra cost.
- **Problem for us:** the same small-effect problem as question 1.

### 5. How much communication do agents need?

- **What is known:** sparse communication saves up to 44% of tokens with similar or better accuracy (Li et al. 2024). Follow-ups include S²-MAD (Zeng et al. 2025) and "Debate Only When Necessary" (Eo et al. 2025).
- **In our favour:** communication is tokens, so the accuracy-vs-cost curve is natural.
- **Problem for us:** crowded, and the accuracy differences are again small.

### 6. Can a weak judge find the right answer when two agents debate?

- **What is known:** this is an active AI-safety question with mixed results.
  With hidden information, debate helps a lot: an LLM judge reached 76% against 48% alone (Khan et al. 2024).
  Without hidden information, which is our case, results are mixed (Kenton et al. 2024).
  In 2026, Elasky et al. find debate helps only when the critic is clearly stronger than the judge, and that one critique gives most of the benefit. Carro et al. find debate helps human judges but not weaker LLM judges.
- **In our favour:** the most novel option, and any clean result adds to a live debate.
- **Problems for us:**
  - We have one model, so "weak" has to mean a non-thinking judge against thinking debaters. On MMLU-Pro that gap is only 3.4 points.
  - The fair same-cost baseline is "let the judge think instead", which probably wins and undercuts the setup.
  - It is the most complex to build: assigned positions, multi-turn transcripts, a one-sided baseline.
- **Verdict:** worth doing as one arm inside question 8, where the equal-cost comparison is the point.

### 7. How biased is the DeepSeek judge, and how can we reduce it?

- **What is known:** position, length and style biases are well documented (Zheng et al. 2023; Wang et al. 2023; Shi et al. 2024; Ye et al. 2024).
  Soumik (2026) compares nine fixes and finds style bias (markdown against plain text) much larger than position bias on easier benchmarks.
  Wang et al. (2025) find reasoning models still biased and preferring later positions.
- **Gap:** I found no controlled test that turns thinking on and off for the same model. On JudgeBench, position effects are large (9–30% of pairs split), unlike on the easier benchmarks.
- **Verdict:** safe, cheap and measurable. The innovation depends on the fix we invent. It overlaps so much with question 8 that it works best as that question's error analysis.

### 8. Does more computation make the judge more accurate?

- **What is known:** yes for reasoning tokens (Kim et al. 2025; the o3-mini rows above). Voting helps thinking judges if aggregated well (2512.03019). Libraries such as Verdict (Kalra and Tang 2025) and debate-style evaluators such as D3 (Harrasse et al. 2026) spend judge compute in structured ways.
  Krumdick et al. (2025) show a judge cannot reliably grade a question it cannot answer itself.
- **Gap:** no equal-cost comparison of the kinds of computation that I could find, and nothing on `deepseek-flash`.
- **Verdict:** recommended. Details in the sketch below.

### 9. Does the judge agree with human experts?

- **What is known:** GPT-4 agreed with experts about 85% of the time on MT-Bench, where humans agree with each other 81% (Zheng et al. 2023). Recent work argues raw agreement overstates quality (Rao and Callison-Burch 2026).
- **Problem for us:** none of our three datasets has human expert labels. JudgeBench's labels are objective correctness. We would need a fourth dataset and its loader, and the work is mostly measurement.

## Sketches for the top three

### Question 8 (recommended)

- **Hypothesis:** at equal API cost, more thinking raises `deepseek-flash`'s JudgeBench score more than voting or a debate between advocates. Voting mainly removes split verdicts, while thinking also fixes pairs the judge gets wrong in both orders.
- **Conditions,** all on the same 620 pairs, in both answer orders:
  1. Baseline: one non-thinking verdict.
  2. Vote: 3, 5 and 9 non-thinking verdicts, majority wins.
  3. Think: effort `low`, `high` and `max`.
  4. Solve first: the judge answers the question itself, then compares.
  5. Debate: two advocates each defend one response, and the judge reads the exchange. This uses the debate engine.
  6. **Our method:** escalate on disagreement. Give a cheap verdict in both orders, and spend more (thinking or votes) only on pairs that split or have low token-probability confidence.
- **Same-cost baseline:** for each method, the vote condition with the number of verdicts chosen to match its measured cost.
- **Measures:** JudgeBench score, split rate, which position wins in splits, cost per pair, all with 95% confidence intervals and paired tests, also by category.
- **Statistics:** 620 pairs give about ±3.8 points and can detect paired differences of about 6 points. Published effects are 10–20 points.
- **Estimated cost:** US$14–20 off-peak, with effort `max` on a subset, plus about US$2 for pilots.
- **Risks:** the top effort levels may hit a ceiling; the model may have seen these questions in training; 620 pairs limits fine comparisons.
  A fix for the last one is to build extra pairs from MMLU-Pro using `deepseek-flash`'s own right and wrong answers, following JudgeBench's recipe.
- **Roles:** method lead builds the judge variants, the advocate debate and the escalation method. Evaluation lead builds the JudgeBench loader and scoring, cost matching, statistics and plots.

### Question 7 (second choice)

- **Hypothesis:** when unsure, `deepseek-flash` favours the second-listed response; the bias shrinks with thinking, and a cheap fix removes most of it for less than thinking costs.
- **Experiment:** measure position preference and split rate on JudgeBench with thinking off and on. Then add controlled changes to the wrong response (markdown styling, padding, "wait, let me think" phrases) and measure how often the verdict flips.
- **Fixes to test:** escalate on disagreement, rewrite both responses in one neutral style before judging, solve first.
- **Same-cost baseline:** voting.
- **Estimated cost:** US$8–12.

### Question 6 (third choice)

- **Hypothesis:** a non-thinking judge is more accurate after a debate between two thinking debaters than after a one-sided argument, but no more accurate than it is alone at the same cost.
- **Experiment:** about 500 MMLU-Pro questions. One debater gets the key answer and the other a wrong option. Compare judge alone, judge with votes at matched cost, one-sided argument, one critique, and a full debate.
- **Estimated cost:** US$10–20, mostly thinking tokens for the debaters.
- **Risks:** the model may refuse or hedge when told to defend a wrong answer; small capability gap; the baseline problem described above.

## Combined and own questions

- **Question 8 with 7 and 6 inside it** is the recommendation. It is still question 8, so it needs no instructor approval.
- **Questions 3 and 4 together** ("does confidence stop errors spreading?") is the best debate-side option, but Zhu et al. (2026) and Hao et al. (2026) cover most of it, and the effects are small.
- **An own question** I considered: use the right and wrong answers from our own debate logs as new judge test pairs, to test whether the judge favours its own model's answers. It fits better as an extension of question 8 than as a separate question.

## Budget and statistics

Assumptions that a pilot must confirm: about 300 input and 400 output tokens for a non-thinking MMLU-Pro answer, about 2,800 output tokens with thinking `high`, and about 1,500 input tokens per JudgeBench judge call (measured from the data: 1,300 for the question and two responses).

| Item, off-peak | Cost |
|---|---|
| One non-thinking answer on MMLU-Pro | US$0.0003 |
| One thinking answer on MMLU-Pro | about US$0.0017 |
| One debate, 3 agents and 3 rounds, non-thinking | about US$0.0043, about 15 single answers |
| One debate with thinking agents | about US$0.017 |
| JudgeBench, all 620 pairs in both orders, short non-thinking verdict | about US$0.43 |
| Same, thinking `high` | about US$2.50 |
| Same, thinking `max` | about US$6 |

- **Confidence intervals:** at 83% accuracy, ±3.3 points with 500 questions and ±2.3 with 1,000. At 65% accuracy on 620 pairs, ±3.8.
- **Smallest detectable difference with paired tests:** about 3 points needs roughly 700 questions; about 2 points needs 1,600; 1.3 points needs 3,700.
- **Consequence:** the debate questions need 1,000 or more questions per condition and four or five conditions, which is US$17 or more for effects that may still be too small to see. The judge questions need under US$1 per cheap condition, and their effects are large.

## What I could not verify

- I read abstracts, not full papers, for most of the literature. I read the official DeepSeek docs and the JudgeBench data in full.
- Three numbers come from search excerpts of the papers, not from text I read directly: the answer-change rates in question 2, the token savings in question 5, and the 76% against 48% in question 6. Check them in the papers before citing them in the report.
- "No one has done this" is a search result, not a proof. I searched in several ways and found nothing matching, which is the most I can say.
- The official benchmark scores are for V4-Flash, not V4.1-Flash.
- Token counts for thinking mode are estimates. A 50-pair pilot would replace them with real numbers.
- One source I found, a large judge study (arXiv 2606.19544), has been withdrawn from arXiv, so I did not use it.
- I do not know what the instructor prefers or what other teams will pick.

## Sources

Official documentation and data:

- [DeepSeek models and pricing](https://api-docs.deepseek.com/quick_start/pricing)
- [DeepSeek thinking mode](https://api-docs.deepseek.com/guides/thinking_mode)
- [DeepSeek context caching](https://api-docs.deepseek.com/guides/kv_cache)
- [DeepSeek chat completions API](https://api-docs.deepseek.com/api/create-chat-completion)
- [DeepSeek-V4-Flash model card](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash)
- [JudgeBench code](https://github.com/ScalerLab/JudgeBench), [dataset](https://huggingface.co/datasets/ScalerLab/JudgeBench) and [leaderboard outputs](https://huggingface.co/spaces/ScalerLab/JudgeBench)
- [MMLU-Pro dataset](https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro) and [GSM8K dataset](https://huggingface.co/datasets/openai/gsm8k)

Datasets and models:

- Tan et al. 2024, JudgeBench, [arXiv 2410.12784](https://arxiv.org/abs/2410.12784)
- Wang et al. 2024, MMLU-Pro, [arXiv 2406.01574](https://arxiv.org/abs/2406.01574)
- Cobbe et al. 2021, GSM8K, [arXiv 2110.14168](https://arxiv.org/abs/2110.14168)
- DeepSeek-AI 2026, DeepSeek-V4, [arXiv 2606.19348](https://arxiv.org/abs/2606.19348), and V4.1-Flash, [arXiv 2609.19969](https://arxiv.org/abs/2609.19969)

Debate (questions 1–5):

- Du et al. 2023, multiagent debate, [arXiv 2305.14325](https://arxiv.org/abs/2305.14325)
- Smit et al. 2023, Should we be going MAD?, [arXiv 2311.17371](https://arxiv.org/abs/2311.17371)
- Zhang et al. 2025, Stop Overvaluing Multi-Agent Debate, [arXiv 2502.08788](https://arxiv.org/abs/2502.08788)
- Choi et al. 2025, Debate or Vote, [arXiv 2508.17536](https://arxiv.org/abs/2508.17536)
- Tran and Kiela 2026, equal thinking-token budgets, [arXiv 2604.02460](https://arxiv.org/abs/2604.02460)
- Wunderlich et al. 2026, Pareto-optimal test-time scaling, [arXiv 2605.01566](https://arxiv.org/abs/2605.01566)
- Bertalanič and Fortuna 2026, The Cost of Consensus, [arXiv 2605.00914](https://arxiv.org/abs/2605.00914)
- Ferreira et al. 2026, Beyond Symmetric Agents, [arXiv 2609.35875](https://arxiv.org/abs/2609.35875)
- Wynn et al. 2025, Talk Isn't Always Cheap, [arXiv 2509.05396](https://arxiv.org/abs/2509.05396)
- Hao et al. 2026, Not All Flips Are Conformity, [arXiv 2606.00820](https://arxiv.org/abs/2606.00820)
- Qian 2026, What Does Multi-Agent Debate Actually Change?, [arXiv 2609.08016](https://arxiv.org/abs/2609.08016)
- Chen et al. 2025, When and Why Does Multi-Agent Debate Fail, [arXiv 2510.20963](https://arxiv.org/abs/2510.20963)
- Chen et al. 2023, ReConcile, [arXiv 2309.13007](https://arxiv.org/abs/2309.13007)
- Yoffe et al. 2024, DebUnc, [arXiv 2407.06426](https://arxiv.org/abs/2407.06426)
- Lin and Hooi 2025, ConfMAD, [arXiv 2509.14034](https://arxiv.org/abs/2509.14034)
- Zhu et al. 2026, The Role of Confidence and Diversity, [arXiv 2601.19921](https://arxiv.org/abs/2601.19921)
- Elahi et al. 2026, Confidence Composition, [arXiv 2606.13591](https://arxiv.org/abs/2606.13591)
- Li et al. 2024, Sparse Communication Topology, [arXiv 2406.11776](https://arxiv.org/abs/2406.11776)
- Zeng et al. 2025, S²-MAD, [arXiv 2502.04790](https://arxiv.org/abs/2502.04790)
- Eo et al. 2025, Debate Only When Necessary, [arXiv 2504.05047](https://arxiv.org/abs/2504.05047)
- Motger et al. 2026, debate survey, [arXiv 2607.26212](https://arxiv.org/abs/2607.26212)

Weak judge and debaters (question 6):

- Khan et al. 2024, Debating with More Persuasive LLMs, [arXiv 2402.06782](https://arxiv.org/abs/2402.06782)
- Kenton et al. 2024, weak LLMs judging strong LLMs, [arXiv 2407.04622](https://arxiv.org/abs/2407.04622)
- Michael et al. 2023, Debate Helps Supervise Unreliable Experts, [arXiv 2311.08702](https://arxiv.org/abs/2311.08702)
- Elasky et al. 2026, Debate Helps Weak Judges Reward Stronger Models, [arXiv 2605.27483](https://arxiv.org/abs/2605.27483)
- Carro et al. 2026, Humans Correct Their Judgments Through Debate, but Weaker AI Models Do Not, [arXiv 2610.28539](https://arxiv.org/abs/2610.28539)

Judges (questions 7–9):

- Zheng et al. 2023, Judging LLM-as-a-Judge, [arXiv 2306.05685](https://arxiv.org/abs/2306.05685)
- Wang et al. 2023, LLMs are not Fair Evaluators, [arXiv 2305.17926](https://arxiv.org/abs/2305.17926)
- Shi et al. 2024, position bias, [arXiv 2406.07791](https://arxiv.org/abs/2406.07791)
- Ye et al. 2024, Justice or Prejudice?, [arXiv 2410.02736](https://arxiv.org/abs/2410.02736)
- Wang et al. 2025, judging bias in reasoning models, [arXiv 2504.09946](https://arxiv.org/abs/2504.09946)
- Soumik 2026, bias mitigation strategies, [arXiv 2604.23178](https://arxiv.org/abs/2604.23178)
- Ma et al. 2025, Judging with Many Minds, [arXiv 2505.19477](https://arxiv.org/abs/2505.19477)
- Kim et al. 2025, Scaling Evaluation-time Compute, [arXiv 2503.19877](https://arxiv.org/abs/2503.19877)
- Kalra and Tang 2025, Verdict, [arXiv 2502.18018](https://arxiv.org/abs/2502.18018)
- Distribution-calibrated compute for thinking judges, 2025, [arXiv 2512.03019](https://arxiv.org/abs/2512.03019)
- Harrasse et al. 2026, D3, [arXiv 2410.04663](https://arxiv.org/abs/2410.04663)
- Krumdick et al. 2025, No Free Labels, [arXiv 2503.05061](https://arxiv.org/abs/2503.05061)
- Rao and Callison-Burch 2026, agreement metrics, [arXiv 2606.00093](https://arxiv.org/abs/2606.00093)
