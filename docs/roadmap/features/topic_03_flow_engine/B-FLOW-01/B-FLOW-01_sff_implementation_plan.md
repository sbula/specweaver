# Implementation Plan: Scenario Testing [SF-F: Scenario side]
- **Feature ID**: B-FLOW-01
- **Sub-Feature**: SF-F — Scenario side: read-only tools, checked scenarios, filtered reports
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-01/B-FLOW-01_design.md
- **Design Section**: §Sub-features → SF-F
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-01/B-FLOW-01_sff_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-15

**FRs owned**: FR-2, FR-3, FR-5a, FR-6, FR-8 · **Depends on**: SF-D (committed) · also cites
FR-4 (SF-B's converter, which had no `Proves:` test)

## Goal

The scenario agent reads the spec and the contracts and nothing else, and it writes nothing. Every
scenario it returns is checked against the spec and the contract before it is stored. A class's
methods are tested like plain functions. The report the arbiter sends to the scenario side holds no
code, and a problem the agent finds in the spec reaches the person.

## Shape

| Piece | Where | Tag |
|---|---|---|
| contract methods keep their owner: `greet` for a function, `Greeter.greet` for a method; `__init__` gives the constructor's parameters and is not a method | `core/flow/handlers/contract_renderers.py` | MODIFY |
| one contract file per spec: Python a `Protocol` per class plus `<Stem>Protocol` for the functions; Java/Kotlin/TypeScript an interface per class, Rust a trait per class | `contract_renderers.py`, `generation.py` | MODIFY |
| a scenario names its method as the contract does, and may carry `constructor_inputs` | `workflows/scenarios/scenario_models.py` | MODIFY |
| the Python converter calls `_target.Greeter(**constructor_inputs).greet(**inputs)`; each dotted part must be an identifier | `workflows/scenarios/scenario_converter.py` | MODIFY |
| the other converters accept a dotted name and use its method part for names | `sandbox/language/core/{java,kotlin,typescript,rust}/scenario_converter.py` | MODIFY |
| the generator refuses: no scenario; a `req_id` the spec lacks; a method the contract lacks; a contract method no scenario calls; `constructor_inputs` on a plain function; a constructor key `__init__` does not declare (unless it takes `**kwargs`). Each refusal is sent back to the model as a retry, then fails the step | `workflows/scenarios/scenario_generator.py` | MODIFY |
| the scenario step gives the generator the contract's method names (from the spec, by `contract_renderers`) and the earlier set for this spec, if the store has one | `core/flow/handlers/scenario.py` | MODIFY |
| the scenario agent's tools: the file tools only, READ only, on `specs/` and `contracts/`; no git, no code-structure, no web | `sandbox/dispatcher.py`, `sandbox/git/interfaces/{tool,facades}.py`, `core/flow/handlers/scenario.py` | MODIFY |
| the generator calls `generate_with_tools` when it has tools, as `Reviewer._execute_review` does | `scenario_generator.py` | MODIFY |
| `ScenarioSet.problems: list[str]` — spec or contract problems the agent names; the step puts them in its output; the dual handler copies the scenario side's into its own output | `scenario_models.py`, `scenario.py`, `dual_pipeline.py` | MODIFY |
| the end of `sw run` shows the coverage and the problems; both move out of `cli.py`, which is at 596 lines | `core/flow/interfaces/run_summary.py` | NEW |
| the arbiter strips code from `scenario_feedback`, and from the error message it builds from it | `core/flow/handlers/arbiter.py` | MODIFY |
| `scenario_validation.yaml` is two steps; the contract is made once, before the sides | test only | — |

> [!NOTE]
> A dual run is Python only (FR-18). The other converters get the dotted name so that a contract
> with a class does not crash them; they do not build objects.

> [!CAUTION]
> NFR-7: a spec with functions only must give the same contract file as today, byte for byte.
> The existing renderer tests stay unchanged and green.

> [!CAUTION]
> The problems text is the scenario side's words. It goes to step outputs and the screen only —
> never into `context.feedback`, task memory or any prompt. CB-3 asserts that.

## The code filter (CB-4)

In order: drop fenced code blocks; drop lines that look like code (`def `, `class `, `return `,
`import `, `from … import`, a line that starts with `if`/`for`/`while`/`with`/`try` and ends in `:`, a line ending in `{`, a call with `self.`). A plain sentence ending in `:` stays; drop any path that
names a source or test file or `/workspace`; collapse what is left. If nothing is left: *"The expected
behaviour for <clause> was judged wrong. Derive it again from the spec."*

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | contract methods keep their owner; the model's `constructor_inputs`; every converter takes a dotted name; the Python one builds the object | FR-2, FR-4 | a spec with `class Greeter` gives a contract with no `Greeter`, and a scenario `Greeter.greet` is refused — red today |
| CB-2 | the generator's four refusals; the step passes the method names and the earlier set; the two-step pipeline and one contract | FR-3, FR-6 | a set with `req_id: FR-99` is stored — red today |
| CB-3 | the scenario agent's tools; `problems` to the end of `sw run` | FR-5a | the agent gets no tools, and `scenario_agent` has git — red today |
| CB-4 | the code filter on the scenario-side report | FR-8 | an arbiter answer with a code block in `scenario_feedback` reaches the scenario prompt — red today |

| CB | Tier | Test |
|---|---|---|
| CB-1 | unit + integration | renderers per language; the real contract step and the real converter run a class's method against a real module |
| CB-2 | integration + e2e | the real scenario step with a scripted model; the e2e's stored set names only spec ids and contract methods |
| CB-3 | integration + e2e | the real dispatcher: a read of `src/` or `tests/` is refused; a dual run's problems reach the `sw run` output; the e2e's tool calls stay in `specs/` and `contracts/` |
| CB-4 | integration | the real arbiter and the real scenario step: no code line reaches the regeneration prompt |

## Mutants

| id | Line neutralised | Must kill |
|---|---|---|
| `contract-drops-class` | the owner kept with each method | CB-1 |
| `object-not-built` | the converter's constructor call | CB-1 |
| `unknown-req-accepted` | the `req_id` check | CB-2 |
| `uncalled-method-accepted` | the check that every contract method is called | CB-2 |
| `scenario-agent-writes` | the READ mode of the scenario grants | CB-3 |
| `scenario-agent-has-git` | the git role row | CB-3 |
| `problems-not-shown` | the problems block of the run summary | CB-3 |
| `scenario-report-unfiltered` | the code filter on `scenario_feedback` | CB-4 |

## Research Notes

- `extract_signatures` keeps `def` lines only and drops any `class`; the class name is built from
  the spec's stem (`contract_renderers.py:380`, `generation.py:443`).
- The Python converter refuses a dotted `function_under_test` and calls `_target.<name>(**inputs)`
  (`scenario_converter.py:69,170`). Dual runs are Python only (FR-18), so only it runs.
- `ScenarioGenerator` takes `tool_dispatcher` and never uses it; it calls `generate(prompt)`
  (`scenario_generator.py:34,105`). `Reviewer._execute_review` is the tool-use pattern
  (`workflows/review/reviewer.py:190`).
- Today `scenario_agent` gets FULL on `<root>/scenarios` (`dispatcher.py:171`) and git read intents
  (`sandbox/git/interfaces/tool.py:44`, `facades.py:250`).
- `FileExecutor` has one root and refuses any path outside it (`filesystem/core/executor.py:384`):
  this is why the earlier set comes in the prompt (Q1).
- The sub-runs' step records stay in their own runs; the dual handler returns only
  `{"component", "status"}` (`dual_pipeline.py:139`), so it must copy the problems up.
- The arbiter guards `coding_feedback` (`_guard_coding_feedback`), and sends `scenario_feedback`
  unchanged to `feedback["generate_scenarios"]` and into its error message (`arbiter.py:381,395`).
- `check_fr_coverage.py B-FLOW-01`: FR-2, FR-3, FR-4, FR-5a, FR-6, FR-8 have no `Proves:` test.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | How the scenario agent sees its earlier set | in its prompt, from the store; its file tools cover `specs/` and `contracts/` only; FR-5a's text says so `[agreed 2026-10-15]` |
| Q2 | Class methods in contracts and scenarios | full support: `Class.method`, constructor values in the scenario, the converter builds the object `[agreed 2026-10-15]` |
| Q3 | What a reported spec or contract problem does | the run goes on; the problems are shown at the end of `sw run` `[agreed 2026-10-15]` |
| Q4 | What the scenario-side report may hold | words only: code blocks, code lines and source paths are removed; a standard sentence if nothing is left `[agreed 2026-10-15]` |

## Backlog

none
