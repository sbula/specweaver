# Implementation Plan: Scenario Testing [SF-G: Run control]
- **Feature ID**: B-FLOW-01
- **Sub-Feature**: SF-G — Run control: one spec, the side at fault only, models, overlap
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-01/B-FLOW-01_design.md
- **Design Section**: §Sub-features → SF-G
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-01/B-FLOW-01_sfg_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-15

**FRs owned**: FR-7, FR-15, FR-16, FR-17, NFR-5 · **Depends on**: SF-D (committed)

## Goal

Both sides read one reviewed spec that does not change during the run. After a verdict only the
side at fault runs again, at most twice, then the person is asked. The two sides use different
models where the settings allow it.

## Shape

| Piece | Where | Tag |
|---|---|---|
| an accepted spec review of a registered project writes the spec's SHA-256 to `<store>/reviewed/<stem>.json` | `core/flow/handlers/review.py` | MODIFY |
| the dual run refuses a spec with no review or a changed one, naming `sw review` | `core/flow/handlers/dual_pipeline.py` | MODIFY |
| the arbiter refuses when the spec changed since its review: "the spec changed — run `sw review`, then resume"; after that review both sides run again | `core/flow/handlers/arbiter.py` | MODIFY |
| the coding side's pipeline drops `draft_spec` and `review_spec` | `dual_pipeline.py` (`_build_runner`) | MODIFY |
| a loop back runs only the side whose feedback entry is waiting; with none, both | `dual_pipeline.py` | MODIFY |
| `arbitrate_verdict` loops back at most 2 times; the 3rd failure parks the run for the person, through a new gate option `on_exhausted: park` (default `stop`) | `workflows/pipelines/scenario_integration.yaml`, `core/flow/engine/gates.py`, `engine/models.py` | MODIFY |
| the scenario agent gets its own role, `roles.scenario`; unset, it falls back to `roles.default`; the settings accept it, so `sw config set-role scenario …` works | `infrastructure/llm/models.py` (`TaskType`), `core/flow/handlers/_llm.py`, `scenario.py` | MODIFY |
| the dual run refuses one model for both sides when the settings name two or more; with one it warns and the run summary says so | `dual_pipeline.py`, `infrastructure/llm/resolve.py`, `core/flow/interfaces/run_summary.py` | MODIFY |
| `--model` sets the coding side only; this narrows `C-FLOW-13` FR-3 for one role, noted in FR-17's row | `infrastructure/llm/resolve.py` (`_every_role`) | MODIFY |
| the sides run at the same time and the scenario tests wait for both | test only | — |
| the roles of a dual run's two sides are checked before the run starts, for `sw run` and the REST API | `core/flow/handlers/_llm.py` (`roles_of`) | MODIFY |
| the spec fingerprint has one home; the arbiter's park check and the review record use it | `core/flow/handlers/arbiter.py` (`_spec_sha`) → a shared helper | MODIFY |
| `roles` in the setup guide lists `scenario` | `docs/user_guides/1_installation_and_setup.md` | MODIFY |

> [!CAUTION]
> A resume after an exhausted park gives the loop 2 new rounds: the person chose to try again
> `[agreed 2026-10-15]`. The gate resets the step's stored count when it parks, because a resume
> re-runs the arbiter step and reads that count back (`LoopState.for_run`). A resume never
> approves this park: approval is only for a HITL gate with a passing result (`approval.py`).

> [!NOTE]
> A test router (`FixedRouter`) knows no settings. The model check reads the models from the
> router; a router that cannot name them is reported as unknown, never as a pass.

> [!WARNING]
> Three existing tests change meaning, as agreed: the e2e retry journey (E5) ends parked after 3
> verdicts instead of failing after 4; the arbiter's "spec edited, the round runs again" case now
> needs a review first; and every dual-run e2e first runs `sw review`.

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the review fingerprint; the dual run's and the arbiter's checks; the coding side skips the spec steps | FR-15 | a dual run starts on a spec nobody reviewed, and its coding side runs `review_spec` — red today |
| CB-2 | one side per loop; 2 loops, then park; the overlap proof | FR-16, NFR-5, FR-7 | a code bug re-runs the scenario side too, and a 4th verdict runs — red today |
| CB-3 | the scenario role and its settings name; the model check; `--model` for the coding side only; the sides' roles checked at start; the run summary line | FR-17 | settings with two models give both sides the same one and the run starts — red today |

| CB | Tier | Test |
|---|---|---|
| CB-1 | integration + e2e | the real review step records; the real dual handler refuses; the e2e reviews the spec with `sw review` first, then runs |
| CB-2 | integration + e2e | the real runner's loop with recorded sides; the e2e code-bug journey runs the coding side twice and the scenario side once |
| CB-3 | integration | the real role resolver from real settings files; the real dual handler refuses or warns |

## Mutants

| id | Line neutralised | Must kill |
|---|---|---|
| `review-not-recorded` | the fingerprint write | CB-1 |
| `unreviewed-spec-runs` | the dual run's fingerprint check | CB-1 |
| `changed-spec-arbitrated` | the arbiter's fingerprint check | CB-1 |
| `both-sides-rerun` | the choice of the side at fault | CB-2 |
| `exhausted-loop-fails` | the park on the 3rd failure | CB-2 |
| `sides-not-joined` | `ALL_COMPLETED` → `FIRST_COMPLETED` | CB-2 |
| `same-model-runs` | the model check | CB-3 |
| `model-flag-sets-both` | `--model` skipping the scenario role | CB-3 |

## Research Notes

- No spec review records anything today; the arbiter fingerprints the spec only to tell whether a
  park can resume (`arbiter.py:159 _spec_sha`).
- Every spec review — `sw review`, the REST API and a pipeline step — runs `ReviewSpecHandler`
  (`workflows/review/interfaces/cli.py:72`, `interfaces/api/v1/review.py:42`).
- `new_feature.yaml` starts with `draft_spec`, `validate_spec`, `review_spec`; the dual run builds
  the coding side from it (`dual_pipeline.py _build_runner`).
- A loop back rewinds to `run_dual_pipelines`, which starts both sides; the arbiter has already put
  the side's entry under `feedback["generate_code"]` or `["generate_scenarios"]`.
- On exhaustion a loop-back gate fails the run (`gates.py _handle_loop_back`);
  `GateDefinition.max_retries_hitl` is read by nothing.
- Roles are `TaskType` values; scenario generation uses `implement`, the same role as the code
  (`_llm.py ROLE_OF_STEP`). `--model` gives every named role and `default` one model
  (`resolve.py _every_role`).
- The dual handler already waits for both sides with `asyncio.wait(..., ALL_COMPLETED)`.
- Settings accept only the role names in `RoleName` (`core/config/llm_settings.py:35`); a new role
  must be added there, or `roles.scenario` is refused when the file is read.
- `sw run` and the REST API check `roles_of(parent pipeline)` before the first call; the parent of a
  dual run has only `review`, so a missing model for a side fails mid-run (`flow/interfaces/cli.py:297`,
  `interfaces/api/v1/pipelines.py:92`).
- A gate can already return `park` (`gates.py:58,126`); `step_execution` persists and parks on it.
- `C-FLOW-13` (finished) FR-3: `--model` is the last word for every role; FR-17 makes `scenario` the
  one exception.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | Where the reviewed fingerprint is kept | a file in the project's scenario store, `reviewed/<stem>.json`, removed with the project; no migration `[agreed 2026-10-15]` |
| Q2 | A resume after the person edits the spec | the resume stops until the changed spec is reviewed; then both sides run again `[agreed 2026-10-15]` |
| Q3 | How the 3rd failure asks the person | a gate option `on_exhausted: park`, default `stop`, so other pipelines are unchanged `[agreed 2026-10-15]` |
| Q4 | Which settings key chooses the scenario agent's model | a new role `roles.scenario`, falling back to `roles.default` `[agreed 2026-10-15]` |

## Backlog

none
