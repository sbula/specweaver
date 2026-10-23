# Implementation Plan: Paths From Outside Can Leave the Project [SF-03: The engine judges paths by where they land]
- **Feature ID**: TECH-075
- **Sub-Feature**: SF-03 — The engine judges paths by where they land
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-075/TECH-075_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-075/TECH-075_sf03_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-6 (mention resolution), FR-8 (`relative_to_root` and its callers), FR-9 (graph export and the
directory walk compare by component). Kind `bugfix`. Depends on SF-01 (committed `b6dfede6`).
NFR-1, NFR-3, NFR-4, NFR-5 apply. SF-02 is committed (`28ff0dad`); its helper
`core.flow.engine.project_paths.project_file` exists.

## Research Notes

- **Mentions** (`core/flow/handlers/review.py:375-430`): `_resolve_mentions(candidates, project_path)`
  joins each candidate to the project root, resolves it, then asks the private `_is_within`. That
  copy is already correct (resolve, then `relative_to`), so FR-6 changes no behaviour: no test can
  go red on today's code. The proof is a mutant on the new check. `_inject_resolved_mentions`
  (`review.py:69-107`) reads each resolved file into a USER message: that is the prompt seam (P-5).
  Unit tests: `tests/unit/core/flow/handlers/test_mention_scanning.py` (imports `_is_within`).
- **`project_file(project_root, relative) -> Path`** (`core/flow/engine/project_paths.py`, SF-02) is
  `WorkspaceBoundary([project_root])` with no API paths, refuses blank, `..`, absolute outside,
  escaping links and null bytes with `ProjectPathError(ValueError)`. It is exactly the project-root-only
  check NFR-4 asks for mentions, and it takes an absolute path inside the root too.
- **`relative_to_root(path, root) -> str`** (`core/flow/handlers/archetype_pipelines.py:190`) answers
  the full path unchanged when it is outside. Callers:
  - `add_payload` (`archetype_pipelines.py:131`): passes it to `CodeStructureAtom` (`read_file_structure`,
    `extract_framework_markers`). The atom reads through `FileExecutor`, which already refuses an
    outside path, so today the hint is lost with a failed atom result and no WARNING.
  - `generated_code` (`core/flow/handlers/qa_targets.py:95-102`): becomes the QA `source`; the Python
    runner puts `source`'s folder on `PYTHONPATH` (`sandbox/language/core/python/runner.py:144`).
    An outside `output_dir` therefore puts an outside folder on the import path today. SF-01's QA
    check covers `target`, `targets` and `entrypoint`, not `source`.
  - `tests/integration/core/flow/handlers/test_archetype_spec_pipeline.py:80-86` asserts today's
    "unchanged when outside": it changes with FR-8.
- **Not a caller, same job**: `validation_hydrator._hydrate_coverage` (`core/flow/handlers/validation_hydrator.py:262-286`)
  computes `target`, `coverage_source` and `source` with a lexical `Path.relative_to`; a link inside
  the project that points outside passes it (audit #2).
- **Graph export** (`graph/core/builder/orchestrator.py:209-235`): the text check on `output_name`
  (RT-16) refuses `..`, `/`, `\`; then `str(output_path).startswith(str(root_path))`. An
  `output_name` that is an existing link to `<root>c/x.graphml` (a sibling whose name starts with the
  root's name) passes and is written. `graph/core/builder` may import only `pathlib`, `os` and its
  listed modules (`context.yaml`), not `sandbox`: use `Path.is_relative_to` on resolved paths.
  Test: `tests/unit/graph/core/builder/test_orchestrator.py:28-52`.
- **Directory walk** (`workspace/project/directory_walk.py:21-55`), used only by
  `find_constitution` (`workspace/project/constitution.py:96`): the stop test is
  `str(current).startswith(str(project_resolved))`. A spec in sibling `/a/bc` of project `/a/b`
  walks to `/a` and further, so a `CONSTITUTION.md` above the project is loaded as an override.
  The spec's own folder is appended before any test, so a spec outside the project always has its
  own folder searched (audit #1). `workspace/project` forbids `sandbox/*`: `Path.is_relative_to`
  on resolved paths. Tests: `tests/unit/workspace/project/test_project_constitution.py:138, 406`.
- **Other string-prefix checks swept** (`grep startswith(str(`, `commonprefix`): `ast/refactor/moves.py:36`
  compares module names, `ast/parsers/_body.py:56` indentation, `sandbox/security.py:221` uses
  `root + "/"`. None is a path containment bug.
- `pathlib.Path.is_relative_to` is lexical: resolve both sides first (design §External Tools).

## Decisions (Phase 4, user answered "all A" 2026-10-23)

1. The constitution walk searches only folders inside the project; a spec outside gets the root
   constitution only (FR-9, design row widened).
2. `_hydrate_coverage` takes its paths from `relative_to_root` (FR-8, design row widened).
3. FR-6 and FR-8 reuse `project_file`; no boundary is built per call site.
4. FR-6 is proven by a killed mutant, not by a red: today's check already works. The walkthrough
   records it.

## Approach (pseudocode, ordered)

**FR-6 — mentions**
1. `_resolve_mentions`: for each candidate, `project_file(project_path, candidate)`; on
   `ProjectPathError` skip (DEBUG log, as today). Keep: `is_file()`, dedup by resolved path, specs
   first, cap. Drop the `roots` loop and `_is_within`; move its two unit tests to the new check.
   Why `project_file` and not a new `WorkspaceBoundary` here: one helper, already project-root only
   (audit #3).

**FR-8 — `relative_to_root`**
2. `relative_to_root(path, root) -> str | None`: `project_file(root, str(path.absolute()))`, then
   `.relative_to(root.resolve()).as_posix()`; `None` when `ProjectPathError`. It never answers an
   outside path.

   > [!CAUTION]
   > `path.absolute()`, not `str(path)`: `sw check src/x.py` gives a path relative to the working
   > folder, and `project_file` joins a relative path to `root`. `absolute()` keeps today's meaning
   > and leaves link resolution to the boundary (Red/Blue R1.2).
3. `add_payload`: `None` → WARNING naming the file and the root, no atom call, every step gets an
   empty `ast_payload` (as a failed atom gives today).
4. `generated_code`: `None` → WARNING, answer `""` (the QA step runs without a `source`).
5. `_hydrate_coverage` uses `relative_to_root` for the test file (`target`) and the code file
   (`source`, `coverage_source`);
   `None` → the existing FAILED result with a message naming the file, no atom call.

**FR-9 — component compare**
6. `export_graph_to_disk`: keep the RT-16 text check; replace the string test with
   `output_path.is_relative_to(root_path)` (both resolved).
7. `walk_up_dirs`: compare `current.is_relative_to(project_resolved)`, never strings, and test
   before appending, so a folder outside the project is never in the list; a spec outside the
   project gets `[project_resolved]` only.

## Proposed Changes

| File | Change |
|---|---|
| `src/specweaver/core/flow/handlers/review.py` | `_resolve_mentions` uses `project_file`; `_is_within` removed |
| `src/specweaver/core/flow/handlers/archetype_pipelines.py` | `relative_to_root` → `str | None`; `add_payload` skips with WARNING |
| `src/specweaver/core/flow/handlers/qa_targets.py` | `generated_code` → `""` with WARNING when outside |
| `src/specweaver/core/flow/handlers/validation_hydrator.py` | `_hydrate_coverage` through `relative_to_root` |
| `src/specweaver/graph/core/builder/orchestrator.py` | component compare |
| `src/specweaver/workspace/project/directory_walk.py` | component compare, tested before appending |

## Test Plan

| FR | Tier | Test file | Cases (bucket) |
|---|---|---|---|
| FR-6 | unit | `test_mention_scanning.py` | inside file (happy); `./x` and `x` dedup (boundary); missing file (degradation); `../x` to an existing file, absolute outside, escaping link, null byte, blank (hostile); link inside → inside (NFR-3) |
| FR-6 | integration | `tests/integration/core/flow/handlers/test_mentions_stay_inside.py` (new) | P-5: real files, an assistant message naming an inside file and an escaping link → `_inject_resolved_mentions` adds the inside file's text and never the outside file's text |
| FR-8 | integration | `test_archetype_spec_pipeline.py` (changed) + `tests/integration/core/flow/handlers/test_engine_paths_stay_inside.py` (new) | `relative_to_root`: inside → relative (happy); root itself (boundary); outside, escaping link → `None` (hostile). a relative `path` resolved against the working folder (boundary, R1.2). `add_payload` with a file outside `--project`: WARNING, the atom never gets the path, empty payload (degradation). `generated_code` with an outside `output_dir` → `""` + WARNING. Red on today's code: today answers the full outside path |
| FR-8 | integration | same file | `_hydrate_coverage` with a code file behind an escaping link → FAILED, atom not called |
| FR-9 | unit | `test_orchestrator.py` | name inside → written (happy); `output_name` an existing link to a sibling `<root>c/x.graphml` → `ValueError`, nothing written (hostile). Red on today's code |
| FR-9 | unit | `test_project_constitution.py` (+ `walk_up_dirs` direct) | sibling `/a/bc` spec with a constitution in `/a` → not loaded (hostile, red today); nested spec walk unchanged (happy); spec at the root (boundary); spec outside with its own constitution → root's only |

Agreement (two jobs, one rule): `relative_to_root` and `_resolve_mentions` both go through
`project_file`; the FR-8 integration file asserts both refuse the same escaping link.

Mutants to write to `TECH-075_mutants.json`:
- FR-6: `_resolve_mentions` accepts every candidate (skip the `project_file` refusal).
- FR-8: `relative_to_root` answers `str(path)` again on refusal; `generated_code` ignores `None`.
- FR-9: graph export string compare back; walk string compare back.

## Commit Boundaries

| CB | Tasks | Done when |
|---|---|---|
| CB-1 | FR-6 + FR-8 (one helper, both in `core/flow/handlers`). The FR-8 integration test is written first and is red on today's code | unit + integration green; FR-6, FR-8 mutants killed |
| CB-2 | FR-9: graph export, directory walk. Closes SF-03 and the last SF: stops for the user's acceptance | unit green; FR-9 mutants killed |

## Documentation

`security_guardrails.md` "One boundary" bullet gains mentions and engine-chosen paths;
`anti_patterns.md:10` row ("parallel security class") corrected (design §Developer Guides);
`agent_tools_reference.md` checked; design Findings table rows already map FL-18 and FR-9.

## Audit (Phase 2) — answered: all A, 2026-10-23

| # | Question | Options | Proposal | Severity |
|---|---|---|---|---|
| 1 | **Constitution from outside the project.** A spec outside the project has its own folder searched for a `CONSTITUTION.md` override. With today's string bug, a spec in a sibling folder also walks above the project. FR-9 fixes only the second. | A: only folders inside the project are searched; a spec outside gets the root constitution only. B: fix the comparison only; a spec outside still uses its own folder's file. | A — the constitution is project policy; "judged by where it lands" | HIGH |
| 2 | `_hydrate_coverage` uses a lexical `relative_to`; an escaping link inside the project passes. Not named in FR-8. | A: route it through `relative_to_root` (FR-8 covers it). B: leave. | A — same job, same helper, 3 lines | MEDIUM |
| 3 | FR-6 and FR-8 reuse SF-02's `project_file` rather than building `WorkspaceBoundary` in each handler | A: reuse. B: a boundary per call site. | A — one helper, already project-root only (NFR-4) | LOW |
| 4 | FR-6 cannot go red: today's `_is_within` is already correct. | A: accept; the proof is a killed mutant, recorded in the walkthrough. B: — | A | LOW |

## Architecture Verification (Phase 3)

| Change | Module · archetype | I/O & state | Execution | LLM | Dependencies | Domain | Verdict |
|---|---|---|---|---|---|---|---|
| mentions, `relative_to_root`, hydrator | `core/flow/handlers` · orchestrator | path resolution | none | none | `core.flow.engine.project_paths` (same package tree) | run inputs | ok |
| graph export | `graph/core/builder` · application | path resolution | none | none | `pathlib` only | graph files | ok |
| directory walk | `workspace/project` · adapter | path resolution | none | none | `pathlib` only | project discovery | ok |

No new module edge, no cycle, no `tach.toml` change (NFR-5). No CRITICAL architecture finding.

## Consistency Check and Red/Blue (Phase 5)

- **Coverage**: FR-6 (CB-1), FR-8 incl. the hydrator (CB-1), FR-9 incl. the constitution scope
  (CB-2). NFR-1: every caller holds a root; a refused path is skipped, never passed. NFR-3: the
  boundary resolves links (FR-6, FR-8); FR-9 resolves both sides. NFR-4: mentions use the project
  root only (`project_file` has no API paths). NFR-5: no new edge. AD-1 (`WorkspaceBoundary` via
  `project_file`) and AD-6 (no race hardening) hold. Risk "`sw check` on a file outside `--project`
  loses its hint": the WARNING in step 3.
- **Open questions**: none. All decisions are resolved and documented inline in the plan.
- **Handoff risk**: the one trap a fresh agent would hit is the relative `path` (caution in step 2).
  The old "unchanged when outside" assertion in `test_archetype_spec_pipeline.py:84` must change,
  not be kept.
- **Architecture**: `core/flow/handlers` already imports `core.flow.engine`; `graph/core/builder` and
  `workspace/project` gain no import. No cycle.
- **DDD/KISS/DRY/hexagonal/SoC**: one helper for every "inside the project" question in the engine;
  the two modules that may not import it use `Path.is_relative_to` on resolved paths. No new class.
- **Code detail limit**: no code block; the steps are pseudocode.
- **Red/Blue**, 2 cycles:
  - R1.1 (MEDIUM) a real run might lose `source`. Blue: invalid. Worktree runs set `project_path`
    and `execution_root` to the worktree and `output_dir` to None; other runs set `output_dir` to
    `<project>/src` (`interfaces/api/v1/pipelines.py:64`, `core/flow/interfaces/cli.py:269`). No
    real run has an outside code file.
  - R1.2 (MEDIUM) a relative `path` would be joined to `root`, not the working folder. Blue: valid,
    fixed with `path.absolute()` (step 2) and a test case.
  - R1.3 (MEDIUM) the hydrator's test file path is also lexical. Blue: valid, step 5 covers it.
  - R1.4 (MEDIUM) the walk change could drop a nested override. Blue: invalid. Folders inside the
    project are kept; the nested and override cases in `test_project_constitution.py` stay.
  - R1.5 (LOW) WARNING lines name absolute paths. Blue: accepted. Server log only; NFR-2 covers API
    bodies.
  - Cycle 2: R1.2's fix keeps today's meaning for a relative path. No new finding. Below every
    threshold: stop.
