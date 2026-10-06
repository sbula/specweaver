# B-FLOW-05 redesign — decisions, 2026-10-06

Grilling for the `B-FLOW-05` redesign after `C-FLOW-13`. Builds on
[llm_settings_grilling_2026-09-26.md](llm_settings_grilling_2026-09-26.md) §"Owned by B-FLOW-05"
and the `C-FLOW-13` SF-05 plan §Decisions (2026-10-03). Where they disagree, the later date holds.
Every row was answered by the user `[agreed 2026-10-06]`.

| # | Decision |
|---|---|
| Q1 | `B-FLOW-05` is the emergency brake only. Measuring models to choose between them is `A-FLOW-01` |
| Q2 | A local model is limited by tokens, per model (`[models."<id>"] tokens_per_run`). GPU time is dropped (supersedes 2026-09-26 Q13/Q10) |
| Q3 | At 100% of a limit the run pauses and asks. With nobody to answer (nightly, CI) it parks, resumable with `sw resume` (2026-09-26 Q21/Q36) |
| Q4 | Loop detection is not part of `B-FLOW-05`; the round limit `[brake] agent_turns` stays here |
| Q5 | Loop detection is its own capability, `B-FLOW-06` (minted 2026-10-06, no design yet) |
| Q6 | A local model with no limit of its own falls under `[brake] tokens_per_run`, which counts only models on private servers; hosted models are bounded by money |
| Q7 | Approving a pause lets the run go on by the same step again: 20 → 40 → 60 |
| Q8 | One warning at 80% of a limit, then the pause at 100% |
| Q9 | A REST request at a limit stops with an HTTP error naming the limit; it does not park |
| Q10 | A model's or a role's own limit behaves like the run total: pause and ask, then its own step size |
| Q11 | Renamed "Spend Brake"; the ID stays `B-FLOW-05` |
| Q12 | The worst-case check before a call estimates the prompt's tokens (characters ÷ 4, Gemini counts exactly) plus a 25% margin; no extra request to the provider |
| Q13 | Answering "no" at a pause parks the run; the spend so far stays with it, and `sw resume` continues after the limit is raised |
| Q14 | A hosted model whose output cap is not known to bound its thinking (`thinking_in_output_cap` unset — today Mistral and hosted Qwen) is refused until the user sets it for that model; models on private servers are bounded by tokens and exempt |

Still in force from 2026-09-26 and 2026-10-03: a hosted model with no known price is refused
(Q10); the worst case of each call (input × price + max output × price) is checked before it is sent,
and crossing it pauses first (Q40); every call carries an output cap that includes thinking, and a
model that cannot be capped is refused (Q41); one brake per run, covering the whole call tree (Q33);
calls already running may overshoot, and the pause says by how much (Q39); no monthly limit (Q34);
a role limit only lowers the model's (2026-10-03); no limit or default value in code (2026-10-03).
