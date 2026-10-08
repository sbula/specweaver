# Indicators of complexity, risk and effort — research for `B-FLOW-07`, 2026-10-08

Asked by the user during the `B-FLOW-07` grilling (Q5): *what are common and good indicators for
complexity, risk and expected effort to fulfil a task?* — researched before applying it to the
spend-limit matrix. Web research; sources linked. The 2026 arXiv items are recent preprints, not
peer-reviewed.

## Bottom line

Don't set the budget from the task text. Take it from what the task touches, and let it grow
while the agent works. Agent cost has a heavy tail, and nobody, the models included, forecasts it
well before a run.

## Indicators

| Indicator | Measures | Work kinds | Obtained | Gameable by a vague request | Evidence |
|---|---|---|---|---|---|
| Size of what is touched (lines, files, pages, requirements) | effort, complexity | all | automatic | no | strong; size drives most metrics — [El Emam 2001](https://www.researchgate.net/publication/3188171_The_Confounding_Effect_of_Class_Size_on_the_Validity_of_Object-Oriented_Metrics) |
| How widely a change is spread (subsystems, files, change entropy) | risk, complexity | code; adaptable to docs, specs | automatic | no | strong — [Kamei et al.](https://sailresearch.github.io/sail-website/data/pdfs/StudyingJustInTimeDefectPredictionUsingCross-projectModels.pdf) |
| Relative churn | risk | code, docs | automatic (git) | no | strong — [Nagappan & Ball 2005](https://dl.acm.org/doi/10.1145/1062455.1062514) |
| Cyclomatic / cognitive complexity | complexity | code | automatic | no | moderate — [Muñoz Barón 2020](https://arxiv.org/pdf/2007.12520) |
| Coupling (fan-in/out) | complexity, risk | code | automatic | no | moderate, mostly explained by size — El Emam 2001 |
| Criticality tier (DAL / SIL / ASIL) | risk; sets required rigour | all | policy label on the target | no | strong as an obligation: DO-178C has 71/69/62/26 objectives for levels A–D — [DO-178C](https://en.wikipedia.org/wiki/DO-178C) |
| Severity first (FMEA Action Priority) | risk | all | judgement | partly | established; the multiplied RPN score was dropped in 2019 — [AIAG-VDA](https://quality-one.com/aiag-vda-fmea/) |
| COCOMO II drivers (reliability, complexity, documentation, precedent, risk resolution) | all three | software, carries over | judgement | partly | established — [COCOMO II manual](https://www.rose-hulman.edu/class/cs/csse372/201410/Homework/CII_manual2000.pdf) |
| Requirements volatility | risk, effort | specs, design, code | automatic (revisions) | no | moderate — [Zowghi & Nurmuliani](https://www.semanticscholar.org/paper/A-study-of-the-impact-of-requirements-volatility-on-Zowghi-Nurmuliani/5e62224991e1e8ac46a397607c9180e852e60795) |
| "Messiness": no clear success check, needs prior context | complexity, risk | agent tasks | derivable (does an acceptance check exist?) | a vague task scores high — the right direction | moderate — [METR](https://arxiv.org/html/2503.14499v1) |
| Expert difficulty / time buckets, story points | effort | coding, agile | judgement | yes | weak for agent tokens — [arXiv 2604.22750](https://arxiv.org/abs/2604.22750) |
| The model's own forecast of its tokens | effort | agent | automatic | yes | weak (r = 0.05–0.39), always too low — arXiv 2604.22750 |
| Past cost of similar tasks (reference class) | effort, risk | all | automatic once a log exists | no | strong — [Flyvbjerg](https://arxiv.org/pdf/1302.3642) |

Not found: solid evidence for estimating research, documentation or spec writing. Stakeholder and
interface counts are folk practice.

## Strongest general indicators for an automatic per-call budget

1. Past cost of the same role and kind of work (reference class): the outside view.
2. Footprint: files, modules or documents in scope, and how spread out they are.
3. Criticality tier of the target.
4. Size of what must be read (input tokens drive agent cost).
5. Whether an acceptance check exists: a vague task should raise the budget, not lower it.
6. Volatility and churn of the target.
7. Spend so far in the run: the forecast improves once work starts ([TokenCast](https://arxiv.org/abs/2609.35760)).

## Approaches

- **Base × multipliers (COCOMO-style):** explainable; needs calibration; multipliers compound;
  judged ratings can be gamed.
- **Reference class / history:** resists optimism; needs a log; new kinds of work have no class yet.
- **Classify, then budget (router):** cheap, but classifiers reading the request can be steered
  ([Rerouting LLM Routers](https://arxiv.org/abs/2501.01818)).
- **Adaptive / escalating budgets:** compute matched to difficulty beats fixed budgets
  ([Snell](https://arxiv.org/abs/2408.03314), [s1](https://arxiv.org/abs/2501.19393)); needs
  checkpoints and a stop rule.
- **Best fit found:** a reference-class base, scaled by criticality and footprint, with a ceiling
  that rises at checkpoints.

## Warnings

- **Heavy tails:** one task can cost 30× more on one run than another (arXiv 2604.22750). Budget at
  a high percentile, not the mean.
- **Wording moves estimates:** "minor extension" lowers estimates
  ([Jørgensen & Grimstad](https://www.semanticscholar.org/paper/The-Impact-of-Irrelevant-and-Misleading-Information-J%C3%B8rgensen-Grimstad/bccd942718afb162ea4a8dc83bcb4c0e3e6f0d74));
  a bare user story costs ~30% more tokens than a full spec ([arXiv 2608.25399](https://arxiv.org/abs/2608.25399)).
- **Multiplying scores misleads:** FMEA dropped RPN because a safety-critical row could score below
  a cosmetic one. Let severity set a floor rather than multiply it in.
- **Size confound:** most complexity metrics add little once size is controlled for; do not count
  size twice.
