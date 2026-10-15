# Implementation Plan: Scenario Testing [SF-D: Isolation core]
- **Feature ID**: B-FLOW-01
- **Sub-Feature**: SF-D — Isolation core
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-01/B-FLOW-01_design.md
- **Design Section**: §Sub-features → SF-D
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-01/B-FLOW-01_sfd_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-15

**FRs owned**: FR-11, FR-14, FR-5b, FR-18, FR-21 · **Depends on**: none ·
**Paths**: US-24 P-4 (seam), P-7 (partly)

## Goal

No scenario file is ever in the project, each side of a dual run has its own `feedback`, and every
process that runs the coder's code in a dual run — or in any run of a project that keeps a scenario
set — runs in a container. Without a container a dual run refuses; a normal run warns.

## Shape

| Piece | Where |
|---|---|
| the scenario store: `specweaver_root() / "projects" / <registered project name> / "scenarios"`, keeping the `definitions/` and `generated/` layout so the trace filters still match `[agreed 2026-10-15]` | a small module beside `core/config/paths.py` |
| `container_available() -> bool`: a plain function, injectable, never cached at module level; probed only for a dual run or when the store holds a set | `sandbox/execution/container_executor.py` |
| `ContainerMounts.scenarios_root: Path \| None`, mounted read-only at `/scenarios` in `_build_container_cmd` only — never in `_prepare_container` (network on, `uv sync`), and `None` for every executor that runs the coder's code | `execution/models.py`, `container_executor.py` |
| a scenario run's scratch directory per run, outside the project, removed afterwards | the scenario executor's `ContainerMounts` |
| the QA atom accepts a target under `/scenarios` for the scenario executor only; every other path outside the project stays refused | `sandbox/qa_runner/core/atom.py:171-185` |
| the Python scenario test names its code as `/workspace/<code path relative to the execution root>`, from `_generated_code(context)` at convert time, with no `parents[2]` fallback | `workflows/scenarios/scenario_converter.py:101-128` |
| `spawn(pipe, feedback=...)`; `_build_runner` **pops** the side's entry from the parent and hands only `{name: entry}` to that side; `isolate_sub_run_context` stays shallow, so decompose is unchanged | `engine/runner.py:104`, `handlers/dual_pipeline.py` |
| the composition roots (CLI `_apply_isolation_policy`, `engine/isolation.py`) resolve the registered name and freeze `scenario_store` and `requires_container` onto `context.isolation`; handlers never read the database or `execution_mode` | `core/flow/interfaces/cli.py`, `core/flow/engine/isolation.py`, `run_context.py` |
| the container rule for every step that runs the coder's code: `run_tests`, the C03 and C04 runs, `lint_fix` `[agreed 2026-10-15]` | `ValidateTestsHandler._get_atom`, `lint_fix.py:199`, `validation_hydrator.py:126` |
| the FR checker reads lettered ids, and `FR-5` never matches `FR-5a` either way | `scripts/check_fr_coverage.py`, `scripts/_citations.py` |

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | lettered FR ids declared and cited | tooling | `FR-5a` reads as undeclared; `FR-5` and `FR-5a` must not credit each other; the checker run over `B-FLOW-01`, `TECH-006`, `TECH-049` |
| CB-2 | `spawn(pipe, feedback=...)`; each side gets only its own entry, popped from the parent; `scenario_test_path` stays on the scenario side | FR-5b | in a scripted dual run the coder's `feedback` holds `scenario_test_path`, and a code-bug verdict reaches the coder in two rounds — both red today |
| CB-3 | `container_available()`; the `/scenarios` mount for the scenario executor only; per-run scratch outside the project; the target allow-list; the converter's absolute code path; a dual run **refuses without a container** (FR-18's engine part) | FR-14, FR-18 (engine) | a unit test on the argv (`<store>:/scenarios:ro`, none in prepare, none for a coder executor); `/etc/x` still refused; the e2e cases that need an engine are skipped without one in this CB; a live-engine integration test runs a scenario test from the mount and leaves the project tree unchanged, `.specweaver/.sandbox` included |
| CB-4 | the store; handlers write there; `remove_project` deletes it; a dual run refuses for an unregistered project, while the project still holds `scenarios/generated`, and for a language whose container is not proven; coder-code steps use the container in a dual run, on the CLI and the API paths | FR-11, FR-18 | a unit test on the store path; the e2e asserts COMPLETED and the files in the store (skipped without an engine); an e2e with the check injected as False asserts the refusal names its reason; a parametrised refusal for Java, Kotlin, TypeScript, Rust; an API-path test |
| CB-5 | a normal run of a project whose store holds a set runs every coder-code step in the container, or warns | FR-21 | the store is looked up before the engine probe; with the check injected, host today |

Every unit and refusal test injects `container_available`; tests that need an engine follow the
existing `skipif(_LIVE_ENGINE is None)` pattern (`tests/integration/sandbox/execution/test_container_executor_integration.py:58`).
A mutant must be killed by a test that runs on a machine without an engine.

## Mutants

| id | Line neutralised | Must kill |
|---|---|---|
| `feedback-shared-again` | the per-side seed | CB-2 |
| `seed-copied-not-popped` | the pop from the parent | CB-2 |
| `scenario-mount-dropped` | the `/scenarios` `-v` pair | CB-3 (argv unit test) |
| `scenario-mount-rw` | `:ro` on that mount | CB-3 |
| `scenario-mount-on-coder` | `scenarios_root=None` for coder executors | CB-3 |
| `traversal-allowlist-widened` | the `/scenarios`-only allow-list | CB-3 |
| `dual-run-without-container` | the refusal when no container can run | CB-3 |
| `store-in-project` | the store root | CB-4 (unit) |
| `kept-set-on-host` | the FR-21 container choice | CB-5 |

## Accepted, and out

- A resumed dual run starts its sides with no per-side feedback: `replay_feedback` keys on
  `run_dual_pipelines` (`hydration.py:219-268`); the next round heals it, as today.
- `facades.py:180` has no caller outside tests; it is not routed.

## Research Notes

- `SandboxSettings.execution_mode: Literal["host","container"] = "host"` (`core/config/settings.py:141`)
  is the only switch; `QARunnerAtom(cwd, language, sandbox_settings)` builds the container executor
  only in `container` mode (`sandbox/qa_runner/core/atom.py:51-97`).
- `ContainerSubprocessExecutor._ensure_engine` tries podman then docker and raises
  `ContainerEngineUnavailableError`; nothing public answers "can a container run" (`container_executor.py:152-174`).
- `_build_container_cmd` mounts `source_root:/workspace:ro`, `scratch_root:/scratch:rw`,
  `cache_root:/cache:ro` (`container_executor.py:506-564`; `ContainerMounts`, `execution/models.py:63-77`).
- The Python scenario test finds the code by `Path(__file__).resolve().parents[2] / 'src'`
  (`workflows/scenarios/scenario_converter.py:101-128`): a test outside the project finds nothing.
- `dual_pipeline` relies on the shared `feedback` today: the arbiter writes `feedback["generate_code"]`
  and `["generate_scenarios"]` in the parent (`arbiter.py:199-205, 380-392`), and the sub-runs read
  them by reference (`generation.py:43-56`, `scenario.py:58-62`).
- Stack-trace filters hide scenario frames by the path `scenarios/generated/`
  (`python/stack_trace_filter.py:19`, `typescript/stack_trace_filter.py:20`).
- Projects are named by `project_name_at(db, root)` (`workspace/store.py:95-100`); there is no
  per-project data directory today; the logs use `logs_dir()/<project_name>/`.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| P1 | FR-14 with FR-11? | FR-14 moved into SF-D: the files leave the project only together with the container run that reads them `[agreed 2026-10-15]` |
| P2 | How the store names a project | the registered project name; a dual run refuses for an unregistered project `[agreed 2026-10-15]` |
| P3 | Which steps use the container | every step that runs the coder's code: `run_tests`, the C03 and C04 runs, `lint_fix` `[agreed 2026-10-15]` |
| P4 | `bash` pipeline steps | out of SF-D: a `bash` step is the person's own pipeline code, and no shipped dual-run pipeline has one `[agreed 2026-10-15]` |
| P7 | Where the sandbox image comes from | built on the machine SpecWeaver runs on, from `Containerfile.sandbox` shipped in the package, the first time it is needed; no registry. The image carries pytest for the scenario tests, and its tag carries the recipe's fingerprint, so a changed recipe rebuilds `[agreed 2026-10-15]`. Found in CB-3: the GHCR image was never published (`403`), so container runs had never worked out of the box |
| P5 | The store when a project is removed | `remove_project` deletes the project's store too `[agreed 2026-10-15]` (CB-4) |

Consequences, not decisions: a dual run of a Java, Kotlin, TypeScript or Rust project refuses until
containers are proven for that language (FR-18); the scenario e2e checks the store, not the project;
the store keeps the `scenarios/generated/` layout, so the stack-trace filters still match and hide
scenario frames from the coder.

## Backlog

none
