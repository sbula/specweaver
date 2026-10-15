# B-FLOW-01: what the scenario pipeline promises, and what holds (2026-10-15)

B-FLOW-01 writes tests from the spec and the API contract only, and the coder must never see them,
so code cannot be fitted to the tests. Measured against the code on 2026-10-15; `file:line` as of
commit `d0041591`.

## Leaks of the scenario side to the coder

| # | Leak | Where | State |
|---|---|---|---|
| 1 | The coder's `run_tests` (no file named) ran the **scenario** tests and retried `generate_code` until they passed | `validation.py` default target | **Fixed** 2026-10-15: only a `kind: scenario` step falls back to the scenario file |
| 2 | A failed `scenario_integration` run's memory handover (scenario words, arbiter text) reaches the next run's coder prompt | `handover.py:88-101`, `hydrator.py:190`, `prompting.py:63-80` | open |
| 3 | C09 counts the scenario tests' `@trace` tags as the coder's coverage | `c09_traceability.py:111`, `factory.py:221` | open |
| 4 | Planner and reviewer have READ over the project root, `scenarios/` included; the plan reaches the coder's prompt | `dispatcher.py:182-188`, `generation.py:220` | open, latent |
| 5 | The coding sub-run can redraft the spec while the scenario side reads it | `dual_pipeline.py:108`, `draft.py:52` | open, latent |
| 6 | Rust, Java and Kotlin scenario files land inside `tests/` or `src/` | SF-B2 converters | open |
| 7 | Sub-runs share one `feedback` dict; it holds `scenario_test_path` and `scenario_test_failures` | `fan_out.py:42`, `scenario.py:174`, `validation.py` | open, no reader yet |
| 8 | Giving the coder tools (`D-INTL-09`) gives the implementer FULL over the root, `scenarios/` included | `dispatcher.py:190` | opens with `D-INTL-09` |

## FR text that says more than the code does

| FR | Says | Code |
|---|---|---|
| FR-2 | `contracts/api_contract.py`, Protocol/ABC | `contracts/<stem>_contract.py`, Protocol only |
| FR-3 | ≥1 scenario per public method; happy, error, boundary | a prompt line asks; nothing checks; `req_id` never checked against the spec |
| FR-5a | scenario agent restricted by folder grants | no caller gives it tools at all |
| FR-5b | coder has zero awareness: grants, prompt, context | only the feedback filter is built (`arbiter.py:51-87`) |
| FR-6 | 4 steps and a READY signal | 2 steps; no READY signal exists |
| FR-7 | parallel runs, JOIN gate | built; no test shows the runs overlap |
| FR-8 | exactly two filtered reports | one report, to the side at fault; the scenario side's has no code filter |

FR-5a and FR-5b were never judged: `check_fr_coverage.py` reads only `FR-<digits>`.

## Related roadmap items

`E-SENS-03` (task-scoped grants) was the first idea for leaks 4, 7 and 8; the approved design closes them by moving the scenario files out of the project instead. `D-INTL-08` (polyglot)
meets FR-2's Python-only contract and leak 6. `B-INTL-07` (planned Arbiter) duplicates the built
arbiter. `B-INTL-06` (multi-agent isolation) is the general form of FR-5b.

## Next

Designed and approved 2026-10-15: SF-D..SF-H of [B-FLOW-01](../roadmap/features/topic_03_flow_engine/B-FLOW-01/B-FLOW-01_design.md). Scenario files move out of the project; dual runs need a container.
