# Design: The Layer Check Reports Clean While the Layers Are Broken

- **Feature ID**: TECH-081
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `refactor`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 18 below.

## Problem Statement

`tach check` passes while modules import the wrong way: four modules are not registered, manifests
describe modules that moved, and sandbox, flow and the CLIs have back-edges hidden by lazy imports.

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **Fix first #8** — Wrong-way dependencies no gate sees: `assurance.graph`, `commons`,
  `workflows.scenarios`, `workflows.evaluators` are not tach modules; sandbox imports workflows and
  flow; engine and handlers import each other; the CLI shell and 9 domain CLIs import each other.
  Where: `tach.toml`, `sandbox/dispatcher.py:234`, `sandbox/security.py:22`, `core/flow/engine/*`.
- **CW-11** — `commons` holds sandbox-domain I/O to dodge layer rules; not registered in tach.
  Where: `commons/prepare_plan.py`, `tooling_sources.py`, `async_bridge.py`.
- **CW-14** — Manifests describe tables and modules that moved or never existed. Where:
  `core/config/context.yaml`, `workspace/context.yaml`, `workspace/project/context.yaml`, no
  `workspace/memory/context.yaml`.
- **AG-16** — The manifest names classes and modules that do not exist; real imports undeclared.
  Where: `assurance/standards/context.yaml`.
- **SB-18** — No `name` or `purpose`; mixed dotted and slash paths; archetypes wrong
  (`web/interfaces` does raw HTTP as "orchestrator"). Where: 15 sandbox `context.yaml` files.
- **WV-21** — Manifests drifted after refactors; `tach_sync` generates rules from them. Where:
  several `context.yaml`, the boundary ledger.
- **CW-24** — Ledger rows are stale (fixed items still listed); real gaps (CW-5, CW-12, CW-15)
  missing. Where: `known_boundary_violations.md`.
- **AG-22** — Lists `exclusions.py`, which no longer does I/O; misses `topology.py`. Where:
  `known_boundary_violations.md:14`.
- **FL-7** — Declared `consumes` misses about 12 real dependencies; flow CLI and top-level CLI
  depend on each other. Where: `core/flow/context.yaml:20-34`, `interfaces/context.yaml`.
- **AG-3** — The most-used graph module is not a tach module; lazy cross-layer imports and a loop
  graph → assurance → graph. Where: `tach.toml` (no `assurance.graph`), `topology.py:179,296`,
  `changes.py:29`, `orchestrator.py:255`.
- **CW-15** — Workspace imports `assurance.graph` and `graph.topology`, invisible to tach. Where:
  `workspace/project/tach_sync.py:17`, `project/interfaces/cli.py:299`.
- **SB-16** — Sandbox imports `workflows` and `core.flow`; tach cannot see it. Where:
  `dispatcher.py:234`, `python/scenario_converter.py:40`, `security.py:22`.
- **SB-17** — Flow imports `language` internals (`_detect`) past the atom it says it uses. Where:
  `task_files.py:60`, `arbiter.py:373`, `qa_targets.py:69`.
- **FL-6** — Engine and handlers import each other; lazy imports hide the cycle; neither has a
  `context.yaml`. Where: `handlers/run_context.py` (used by ~20 engine files),
  `engine/isolation.py:164`, `handover.py:83`.
- **EP-9** — The CLI shell and the domain CLIs depend on each other; a CLI helper lives in
  `infrastructure/llm`. Where: `tach.toml:69` and 9 back-edges; `llm/interfaces/command.py:11`.
- **WV-13** — Python's converter in workflows, four others in sandbox; sandbox imports workflows;
  scenarios and evaluators have no manifest. Where: `workflows/scenarios/scenario_converter.py` vs
  `sandbox/language/core/*/scenario_converter.py`.
- **WV-14** — "Pure-logic" validation does file I/O and loads user code; depends on workflows by
  string. Where: `pipeline_loader.py:77`, `rubrics/loader.py:85`, `validation/loader.py:244`,
  `tach.toml:25`.
- **CW-16** — "context" holds the HITL provider, analyzer protocols and a `context.yaml` writer.
  Where: `workspace/context/`.

## Goal

Every module is registered and every manifest matches the real imports, so `tach check` sees the
truth; then the wrong-way imports are removed.

## Open Decisions (for the grilling, not answered here)

- `T-ARCH`: where each moved module lives (for example `commons`, the scenario converters).

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-081`. Write each fix's test
red
first.
