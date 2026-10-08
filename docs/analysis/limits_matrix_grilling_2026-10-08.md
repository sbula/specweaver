# `B-FLOW-07` grilling — spend limits by model, task and DAL, 2026-10-08

The user's answers, in order. The design states each fact once, beside the requirement it governs;
this record keeps the path to it, including the answers a later one replaced. Research behind Q5:
[effort_indicators_2026-10-08.md](effort_indicators_2026-10-08.md).

| Q | Question | Answer |
|---|---|---|
| Q1 | How do limits combine? | Separate limits; a call counts against every one that applies; the lowest decides |
| Q2 | What does DAL mean for a limit? | "Too simple": DAL, kind of task and the work's difficulty decide together. A factor on a base was floated, with two guards: run and model limits stay hard caps; an unknown value is neutral. Replaced by Q6 and Q19 |
| Q3 | How is a base written? | As amounts (money hosted, tokens private). Moot after Q19 cut the per-DAL base |
| Q4 | Exact tiered prices in scope? | No; the highest-price rule stays (`C-FLOW-13` #22) |
| Q5 | Where does difficulty come from? | Not from the task text ("badly described tasks would become an easy-to-do bonus"); not chosen by a person ("this has to be done for each agent call"); not from code only ("also research, documentation, specs"). After the research: **history of similar work** |
| Q6 | What is similar work? | **Same kind of task, same model, same DAL** — "a DAL A algorithm must resist more corner cases than a DAL E one" |
| Q6b | Too little history? | A base per DAL. Replaced by Q19 |
| Q7 | Which steps count? | **Only passed steps, with all their attempts** |
| Q8, Q8b | When is history enough? | 10 steps in 90 days, filled up with older ones. Replaced by Q19 |
| Q9 | Which percentile? | **90%** |
| Q10, Q11 | Footprint | From the graph, never the text, raising and lowering. Cut by Q19, for later |
| Q12, Q12b | A target with no DAL | **The project's default DAL, which becomes DAL_C** for limits and validation |
| Q13 | Per step or per run? | **Per step**; run and model limits stay caps for the run |
| Q14 | Today's task limit (`roles.<task>.spend_per_run`)? | **Kept**, as a cap per kind of task for the run |
| Q15 | At the step limit? | **As at every limit: ask; "yes" raises; "no" or no terminal parks** |
| Q16 | `[step_limits]` missing? | **No step limits**; the other limits apply; `sw config show` says why |
| Q17 | Names | **`[step_limits]`**, keys as proposed (after Q19: `percentile`, `min_steps`) |
| Q18 | History shared across projects? | **Yes, all projects on the machine** |
| Q19 | How much to build? | **Lean**: the 90% value of the last 10 passed steps of the same task, model and DAL; no step limit until a group has 10; the base per DAL, the window and the footprint are cut. "We should not over-engineer the whole price/token limitation" |
| — | Missing history columns | **Add them** (server, DAL, step, outcome); "we do not have any user for now" |
