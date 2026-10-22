# Implementation Plan: Paths From Outside Can Leave the Project [SF-01: The boundary refuses every way out]
- **Feature ID**: TECH-075
- **Sub-Feature**: SF-01 — The boundary refuses every way out
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-075/TECH-075_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-075/TECH-075_sf01_implementation_plan.md
- **Status**: APPROVED (by the user, 2026-10-22)

## Scope

FR-1 (harden `WorkspaceBoundary`), FR-4 (protocol atom and tool), FR-5 (all QA intents). Kind
`bugfix`. Depends on nothing. Outputs the hardened boundary that SF-02 and SF-03 call.

## Research Notes

- **Reachability, measured 2026-10-22.** No production handler gives an agent the protocol or QA
  tool: `allowed_tools` is `["fs", "ast", "web"]` (`core/flow/handlers/review.py:57`), `["ast"]`
  (`agentic_coder.py:47`), `["fs"]` (`scenario.py:35`). `protocol` is registered
  (`sandbox/registry.py:100-105`) but no handler enables it; `QARunnerTool` is not in the registry,
  only its tests build it (`create_qa_runner_interface`). So Fix first #3 is latent for agents. The
  atoms are reached today by the engine: `ProtocolAtom()` in `validation_hydrator.py:203`,
  `QARunnerAtom` in `validation.py:509,514`, `lint_fix.py:202`, `validation_hydrator.py:128`, with
  targets from the engine or the project's pipeline files.
- `WorkspaceBoundary.__init__(roots: list[Path], api_paths: list[Path] | None = None)`,
  `validate_path(requested: Path) -> Path`, `resolve_relative(relative: str) -> Path`
  (`sandbox/security.py:90-129`). Probed: `validate_path(Path("x.txt"))` resolves against the
  process folder; `resolve_relative("a\x00b")` raises `ValueError`.
- `ReadOnlyWorkspaceBoundary` has `roots=[]`, so `resolve_relative` hits `self.roots[0]` →
  `IndexError` (`sandbox/security.py:128,152-166`).
- The only `validate_path` caller outside `security.py` passes an absolute path
  (`sandbox/execution/core/atom.py:101`), so FR-1's relative rule changes no caller.
- The dispatcher already passes the whole `boundary` to every registry closure
  (`sandbox/dispatcher.py:290`), so `create_protocol` can take `kwargs["boundary"]`, API contract
  paths included (NFR-4).
- `QARunnerAtom.__init__(cwd, language=None, sandbox_settings=None, scenarios_root=None)`;
  `run()` dispatches `_intent_<name>` (`sandbox/qa_runner/core/atom.py:106-152`). Path arguments
  per intent: `target`/`targets` (all six), `entrypoint` (`run_debugger`, run as
  `python <entrypoint>`, `sandbox/language/core/python/runner.py:403`). Only `run_tests` calls
  `_traversal_error` (:196-212); `_in_scenarios_mount` (:214-217) allows `/scenarios/…` in a
  scenario run.
- QA `cwd` and targets agree under isolation: `validation.py:506` binds `cwd` to
  `execution_root or project_path` and passes relative targets; `lint_fix.py:202` and
  `validation_hydrator.py:128` use `project_path` with targets relative to it; no engine caller
  passes a `/workspace/…` container path. So the FR-5 check refuses no target the engine sends today.
- Layer rules: every `sandbox` sub-package may import `sandbox.security` (one tach module,
  `tach.toml:53-54`); `sandbox/execution/core/atom.py:17` is the precedent for a core atom doing so.
- Test patterns to follow: `tests/unit/sandbox/test_security.py` (boundary units),
  `tests/integration/sandbox/test_agent_file_tools_stay_inside.py` (tools built with
  `ToolDispatcher.create_standard_set`, called through `execute`, real files and links).

## Approach (pseudocode, ordered)

**FR-1 — `WorkspaceBoundary`**
1. `resolve_relative(relative)`: refuse empty or whitespace-only, refuse a null byte, refuse when
   there is no root — each as `WorkspaceBoundaryError`; then join to `roots[0]`, resolve, validate.
2. `validate_path(requested)`: a relative `requested` is joined to `roots[0]` before resolving
   (refused when there is no root); a null byte refuses as `WorkspaceBoundaryError`.

**FR-4 — protocol**
1. `ProtocolAtom.__init__(boundary: WorkspaceBoundary)` — required; no boundary means no atom
   (NFR-1, fail closed).
2. `run()`: validate `file_path` through the boundary **before** opening it; a refusal returns
   `FAILED` with a message that echoes the given `file_path` only.
3. `ProtocolTool(boundary)`; `create_protocol` passes `kwargs["boundary"]`.
4. `validation_hydrator.py:203` builds `ProtocolAtom(WorkspaceBoundary([project_root]))`.

**FR-5 — QA**
1. One check in `QARunnerAtom.run()`, before dispatch, over every path argument the intent takes
   (`target`, each of `targets`, `entrypoint`): a `/scenarios/…` path passes only in a scenario run;
   everything else must pass `WorkspaceBoundary([cwd]).resolve_relative`. Refusal = `FAILED`, no
   runner call. Absent or empty values are skipped here, so each intent still reports its own
   "missing target" (`test_run_tests_missing_target` asserts that message).
2. Remove `_traversal_error` and its call in `_intent_run_tests`; keep `_in_scenarios_mount`.

## Proposed Changes

| Tag | File | Change |
|---|---|---|
| [MODIFY] | `src/specweaver/sandbox/security.py` | FR-1: refusals in `resolve_relative` and `validate_path` |
| [MODIFY] | `src/specweaver/sandbox/protocol/core/atom.py` | FR-4: required boundary, check before read |
| [MODIFY] | `src/specweaver/sandbox/protocol/interfaces/tool.py` | FR-4: tool holds the boundary |
| [MODIFY] | `src/specweaver/sandbox/registry.py` | FR-4: `create_protocol` passes `kwargs["boundary"]` |
| [MODIFY] | `src/specweaver/core/flow/handlers/validation_hydrator.py` | FR-4: atom built over the project root |
| [MODIFY] | `src/specweaver/sandbox/qa_runner/core/atom.py` | FR-5: one check in `run()`; `_traversal_error` removed |
| [MODIFY] | `tests/unit/sandbox/test_security.py`, `tests/unit/sandbox/protocol/core/protocol/test_protocol_atom.py`, `tests/unit/sandbox/qa_runner/core/qa_runner/test_qa_runner_atom.py` | new cases, red first |
| [NEW] | `tests/integration/sandbox/test_protocol_tool_stays_inside.py`, `tests/integration/sandbox/test_qa_targets_stay_inside.py` | seam tests |
| [NEW] | `docs/roadmap/features/topic_07_technical_debt/TECH-075/TECH-075_mutants.json` | FR-1, FR-4, FR-5 campaigns |
| [MODIFY] | `docs/architecture/06_lessons_and_future/anti_patterns.md`, `docs/dev_guides/agent_tools_reference.md`, `docs/architecture/01_foundational_principles/security_guardrails.md` | AD-1 and the new checks |

Existing constructions change with the constructors and are updated in CB-2: `ProtocolAtom()` in
`test_protocol_atom.py` and `test_atom_edge_cases.py`; `ProtocolTool()` in `test_protocol_tool.py`,
`test_protocol_tool_edge_cases.py` and `tests/unit/sandbox/test_sandbox_registry.py`.

## Test Plan

| FR | Tier | Test file | Cases (bucket) |
|---|---|---|---|
| FR-1 | unit | `tests/unit/sandbox/test_security.py` | inside path accepted (happy); `.` is the root (boundary); empty, whitespace, null byte refused (hostile); relative judged against the root when the process folder differs (degradation); read-only boundary refuses a relative path, no `IndexError` (degradation) |
| FR-4 | unit | `tests/unit/sandbox/protocol/core/protocol/test_protocol_atom.py` | a valid OpenAPI file inside parses (happy); the same file outside, `../`, an absolute path, an escaping link: `FAILED`, file never opened (hostile); refusal text has no resolved absolute path (NFR-2 spirit) |
| FR-4 | integration | `tests/integration/sandbox/test_protocol_tool_stays_inside.py` | built through `ToolDispatcher.create_standard_set(…, allowed_tools=["protocol"])`, called through `execute`: outside refused, a contract under an API path read (NFR-4) |
| FR-5 | unit | `tests/unit/sandbox/qa_runner/core/qa_runner/test_qa_runner_atom.py` | each of the six intents with an outside `target`; `targets` with one outside; `entrypoint` outside; runner never called (hostile); inside target runs (happy); `/scenarios/x` passes only when mounted (boundary) |
| FR-5 | integration | `tests/integration/sandbox/test_qa_targets_stay_inside.py` | a real `QARunnerAtom` over a tmp project, reached through `create_qa_runner_interface`: `../` and an escaping link refused before any tool runs |

Each new test is run red first; the red reason goes in the walkthrough. Mutants written to
`TECH-075_mutants.json`, one campaign per FR:
- FR-1: drop the null-byte refusal; drop the empty refusal; skip the join to `roots[0]`.
- FR-4: read before validating; build the tool without the boundary.
- FR-5: skip the check for `run_linter`; skip `entrypoint`; accept `/scenarios/` when not mounted.

## Commit Boundaries

| CB | Tasks | Done when |
|---|---|---|
| CB-1 | FR-1 + correct `anti_patterns.md:10` (AD-1: `WorkspaceBoundary` is the one guard for outside paths) | FR-1 tests green; the three FR-1 mutants killed |
| CB-2 | FR-4, protocol atom, tool, registry, hydrator call site | unit + integration green; both FR-4 mutants killed; existing hydrator tests green |
| CB-3 | FR-5 | unit + integration green; the three FR-5 mutants killed; `test_run_tests_prevents_path_traversal`, the validation, lint-fix and scenario tests still green. Closes SF-01: stops for the user's acceptance |

## Documentation

CB-1: `docs/architecture/06_lessons_and_future/anti_patterns.md:10`. CB-2/CB-3:
`docs/dev_guides/agent_tools_reference.md` and
`docs/architecture/01_foundational_principles/security_guardrails.md` say the protocol and QA tools
check every path through `WorkspaceBoundary`.

## Audit (Phase 2)

| # | Question | Options | Proposal | Severity |
|---|---|---|---|---|
| 1 | The debugger runs `python <entrypoint>`, and `entrypoint` comes from the agent. FR-5 named only `target`. | A: check `entrypoint` where it is a file (Python, TypeScript). B: leave it. | **Answered A `[agreed 2026-10-22]`.** FR-5 reworded in the design. Java/Kotlin pass a class name and Rust ignores it, so checking every `entrypoint` as a path changes nothing for them: a class name resolves inside the root. | HIGH |
| 2 | Fix first #3 is latent for agents: no handler enables the protocol or QA tool. | A: keep SF-01 first — SF-02 needs FR-1, and the atoms are reached by the engine today. B: reorder. | A — informational, shown to the user 2026-10-22 | MEDIUM |
| 5 | Two language gaps seen while planning: one test method cannot be run in Java, Kotlin or Rust; the Rust debugger ignores its target. | A: findings in `TECH-078`. B: fix here. | **Answered A `[agreed 2026-10-22]`** — added to `TECH-078`'s design | — |
| 3 | Protocol atom without a boundary: optional or required? | required (NFR-1 decides) | required | — decided by NFR-1 |
| 4 | Where the QA check sits: in `run()` for all intents, or per intent | `run()` | `run()` — covers future intents | — implementation |

## Architecture Verification (Phase 3)

- All changes stay inside the `sandbox` tach module plus one call site in `core/flow`
  (`validation_hydrator.py`), which already consumes `sandbox/security` (`core/flow/context.yaml`).
- No new module, no new import edge, no cycle: `sandbox.security` imports `core.flow` only under
  `TYPE_CHECKING` (`security.py:22`), unchanged.
- Archetypes: protocol and QA cores are adapters; a path check there wraps I/O, which adapters may do.

### Mechanism vs constraint

| Change | Module · archetype | I/O & state | Execution | LLM | Dependencies | Domain | Verdict |
|---|---|---|---|---|---|---|---|
| boundary hardening | `sandbox` (`security.py`, no manifest of its own) | path resolution (filesystem read) | none | none | none new | workspace boundary | ok |
| protocol atom check | `sandbox/protocol/core` · adapter | reads the file it already read | none | none | `sandbox.security` (same tach module) | protocol schemas | ok |
| QA atom check | `sandbox/qa_runner/core` · adapter | path resolution | unchanged (runner) | none | `sandbox.security` (same tach module) | QA execution | ok |
| hydrator call site | `core/flow` · orchestrator | none new | none | none | consumes `sandbox/security` already | validation flow | ok |

Zoom-out: no new capability; the guard exists and this plan only puts it in front of two atoms.
No CRITICAL architecture finding.
