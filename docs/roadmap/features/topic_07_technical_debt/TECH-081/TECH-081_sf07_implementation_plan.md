# Implementation Plan: The Layer Check Reports Clean While the Layers Are Broken [SF-07: Pure-logic and contract modules do no I/O]
- **Feature ID**: TECH-081
- **Sub-Feature**: SF-07 — Pure-logic and contract modules do no I/O
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-07
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_sf07_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-18: `assurance/validation` reads no files and loads no code; the readers move to
`assurance/validation/io` (archetype `adapter`); `loader.py` is deleted (AD-11). FR-19:
`workspace/context` holds contracts only; `inferrer.py` moves to `workspace/analyzers` (AD-12). No
command, option or output changes (NFR-1). No `deprecated` edge is added (NFR-2); one home per
symbol (NFR-3).

## Research Notes

Read 2026-10-28.

- **I/O measured** with the purity guard's own detector (`tests/unit/test_pure_modules_do_no_io.py`
  `_io_calls`) over both modules (`interfaces/` excluded):

  | File | Calls | Plan |
  |---|---|---|
  | `assurance/validation/pipeline_loader.py` | `is_file`, `read_text`, `iterdir` (project file, package resources) | → `io/pipeline_loader.py` |
  | `assurance/validation/rubrics/loader.py` | `is_file`, `read_text` | → `io/rubrics.py` |
  | `assurance/validation/loader.py` | `is_dir`, `glob`, `importlib` `exec_module` | deleted (AD-11) |
  | `assurance/validation/project_root.py` | `is_dir`, `is_file`, `rglob` | ledger row `:13`, `TECH-078` decision 2 — stays |
  | `assurance/validation/rules/code/c09_traceability.py` | `rglob`, `read_text`, `exists`, `is_dir` | **not in the design** — Q1 |
  | `assurance/validation/rules/spec/s04_dependency_dir.py` | `exists` (dead-link check) | **not in the design** — Q1 |
  | `workspace/context/inferrer.py` | `is_file`, `write_text` | → `workspace/analyzers/inferrer.py` |

- **`pipeline_loader.py`** (166 lines): `load_pipeline_yaml(name, *, project_dir=None)` reads
  `{project}/.specweaver/pipelines/`, then `workflows.pipelines`, then its `frameworks`, and resolves
  `extends` through `inheritance.resolve_pipeline`. `resolve_pipeline_name(level, pipeline=None, *,
  active_profile=None)` is pure; it moves with the file (one home, whole-file move; it has the same
  callers). `src` callers: `interfaces/api/v1/validation.py:71,145`,
  `core/flow/handlers/archetype_pipelines.py:182`, `core/config/interfaces/cli.py:209`,
  `assurance/validation/interfaces/cli.py:111,243,327`; `runner.py:19` names it in a docstring. Tests:
  ~45 import or patch lines in 20 files (all path strings).
- **`rubrics/loader.py`**: `load_rubric`, `Rubric`, `RubricNotFoundError`; `_SHIPPED_DIR =
  Path(__file__).parent` (the `.md` files beside it). `rubrics/__init__.py` re-exports the three
  names. `src` caller: `core/flow/handlers/review.py:127`. Tests: `test_rubrics.py`. Corpus
  `C-VAL-05` holds 5 mutants on `rubrics/loader.py`.
- **`loader.py`** (custom-rule loader): no `src` caller; `tests/unit/assurance/validation/test_loader.py`
  only. Exposed as `loader` in the `tach.toml` interface and the manifest.
- **`inferrer.py`**: `ContextInferrer(analyzer_factory)`, `infer_and_write(directory)`; imports only
  stdlib, `ruamel.yaml`, type-only `workspace.context.analyzer_protocols`. Callers:
  `assurance/graph/topology.py:266`, `workspace/project/interfaces/cli.py:14,279`; both modules
  already depend on `workspace.analyzers`. Tests: `tests/unit/workspace/context/test_inferrer.py`,
  `tests/integration/workspace/context/test_exposes_seam.py`, `test_scan_and_infer.py`.
- **tach**: `assurance.validation` depends on `workspace.analyzers`, `core.config`; its
  `[[interfaces]]` expose lists `loader`, `pipeline_loader.*`, `rubrics.*`
  (`test_validation_context_exposes.py` keeps it equal to the manifest). `workspace.context`
  depends on nothing; `workspace.analyzers` on `workspace.ast.parsers`, `workspace.context`.
- **The refactor gate** (`scripts/_refactor_diff_safety.py`) passes a moved test whose diff is
  path-only; it blocks a deleted test file and any edited line. A new untracked test file also
  counts as not provably safe.

## Approach (pseudocode, ordered)

**CB-1 — the context writer leaves the contract module (FR-19)** — kind `tooling` (`test_logging_rollout.py` splits one import; `[agreed 2026-10-28]`)
1. Red: `workspace/context/context.yaml` and the guard are unchanged; tach unchanged. The red is
   CB-3's guard; this boundary is a pure move proven by the existing tests.
2. Green: `git mv workspace/context/inferrer.py workspace/analyzers/inferrer.py`; the two `src`
   callers and the three test files import the new path; the unit test moves to
   `tests/unit/workspace/analyzers/`, the two integration tests to
   `tests/integration/workspace/analyzers/`. Manifests: `workspace/analyzers` exposes
   `ContextInferrer`, `workspace/context` drops it.

**CB-2 — the validation readers move to `assurance/validation/io` (FR-18)** — kind `refactor`
3. Red: `tach.toml` registers `specweaver.assurance.validation.io` (`depends_on`
   `assurance.validation`, `core.config`); `assurance.validation`'s expose drops
   `pipeline_loader.*` and `rubrics.*`. Tach red on every caller.
4. Green: `git mv pipeline_loader.py io/pipeline_loader.py`; `git mv rubrics/loader.py io/rubrics.py`
   with `_SHIPPED_DIR` pointing at the `rubrics/` data folder; `rubrics/__init__.py` re-exports
   nothing (NFR-3; the package stays for the shipped `.md` files). Callers and tests re-pointed
   (path-only). The four calling modules depend on `assurance.validation.io` (pruned with tach's
   unused report). Manifest `assurance/validation/io/context.yaml`, archetype `adapter`. `C-VAL-05`
   mutants re-pointed (`.tmp/stale.py`).

**CB-3 — the guard holds both labels (FR-18, FR-19)** — kind `tooling` (Q2 `[agreed 2026-10-28]`) — closes SF-07
5. Red: `test_pure_modules_do_no_io.py` lists `assurance/validation` and `workspace/context`; the
   files Q1 keeps (`project_root.py`, `c09_traceability.py`, `s04_dependency_dir.py`) are allowed
   only while the ledger names them, and an allowed file with no I/O left fails as stale (a new test asserts each allowed file
   has a ledger row). Red on `loader.py`, and on c09/s04 until their rows exist.
6. Green: delete `loader.py` and `test_loader.py`; drop `loader` from the expose list and the
   manifest. Add the ledger rows for c09 and s04 (DEFERRED, `TECH-081` Q1 `[agreed 2026-10-28]`).
7. Mutants: `validation-reads-again` (`pipeline.py` reads a file → guard red);
   `context-writes-again` (`provider.py` writes a file → guard red); `rubrics-from-old-dir`
   (`_SHIPPED_DIR` back to `io/` → `test_rubrics.py` red).

## Test Plan

| Tier | Test | Proves | Red first because |
|---|---|---|---|
| arch | `test_tach_architectural_boundaries` | FR-18 (callers reach `io`, not `validation`) | expose shrinks before the move |
| unit | `test_pure_modules_do_no_io.py` over `assurance/validation`, `workspace/context` | FR-18, FR-19 | `loader.py` still reads |
| unit | an allowed file must have a ledger row | FR-5 | no such check today |
| all | the suite | NFR-1 | — |

## Commit Boundaries

| CB | Holds | Done when |
|---|---|---|
| CB-1 | steps 1–2 | suite green; commit |
| CB-2 | steps 3–4 | suite green; 0 stale mutants; commit |
| CB-3 | steps 5–7 | suite green; the three mutants killed; stage and stop (closes SF-07) |

## Documentation

`docs/dev_guides/` mentions of `pipeline_loader`, `rubrics` and `ContextInferrer` re-pointed (found
by grep in dev). No user-facing change.

## Architecture Verification (Phase 3)

- `assurance/validation/io` (`adapter`): reads project files and package resources; depends on
  `assurance.validation` (pipeline model, inheritance) and `core.config` (profiles, lazy). Nothing
  below it imports it; its callers are orchestrators (`interfaces.api`, `core.flow.handlers`, the
  two CLIs). No loop.
- `workspace/analyzers` (`adapter`) gains a file writer; it already parses files. `workspace/context`
  keeps the protocols and `provider.py` (`contract`).
- No `deprecated` edge added.

## Audit (Phase 2) — settled

❓ **Q1 — two rules read files and the design does not name them.** `c09_traceability.py` reads the
project's specs and test files; `s04_dependency_dir.py` checks a linked file exists. Taking the reads
out means the runner reads ahead and hands rules data, which `TECH-078` decision 2 refused for
`project_root.py` (`sw check` runs rules with no hydration).
- **A:** keep them; two ledger rows like `project_root.py`'s; the guard allows only files the ledger
  names; FR-18 gains "except the files the ledger names".
- **B:** move their reads out in this SF.

The user chose A `[agreed 2026-10-28]`.

❓ **Q2 — CB-3 edits a test and deletes one.** The `refactor` gate blocks both.
- **A:** CB-3 runs `--kind tooling`; the design's kind line says so.
- **B:** move `loader.py` and the guard to SF-08.

The user chose A `[agreed 2026-10-28]`.

## Consistency (Phase 5)

- Red/Blue, 2 cycles:
  - R1 (MEDIUM) `rubrics/__init__.py` stops re-exporting, so `from ...validation.rubrics import
    load_rubric` breaks. Blue: the only users are `review.py:127` and `test_rubrics.py`; both move to
    `io.rubrics` in CB-2; mypy and the suite catch any other.
  - R2 (MEDIUM) a package named `io` beside `import io` in `pipeline_loader.py`. Blue: absolute
    imports resolve the stdlib `io`; the name is the design's `[agreed 2026-10-27]`.
  - R3 (MEDIUM) `_SHIPPED_DIR` must still find the shipped `.md` files after the loader moves.
    Blue: it points at the `rubrics/` package folder; mutant `rubrics-from-old-dir` proves a test
    sees it.
  - R4 (MEDIUM) the allow-list could drift from the ledger. Blue: step 5's new test fails when an
    allowed file has no ledger row; a row goes when its file is clean (`test_pure_modules_do_no_io`
    reports an allowed file with no I/O as stale).
  - R5 (LOW) CB-1 has no red of its own. Blue: a move proven by the existing tests; CB-3's
    guard is the check that keeps it.
  - R6 (LOW) `test_validation_context_exposes.py` pins the manifest to tach's expose. Blue: both
    change in the same step.
  - R7 (LOW) `test_logging_rollout.py:149` lists `pipeline_loader`. Blue: re-pointed in CB-2.
  - Cycle 2: no new finding.
