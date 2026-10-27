# Implementation Plan: The Layer Check Reports Clean While the Layers Are Broken [SF-02: The manifests tell the truth]
- **Feature ID**: TECH-081
- **Sub-Feature**: SF-02 — The manifests tell the truth
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_sf02_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-4 (manifests ↔ `tach.toml` agreement test), FR-6 (`name`, `purpose`, `archetype`; no phantom
`exposes`), FR-7 (missing manifests added; drifted ones rewritten), FR-8 (wrong labels corrected).
Kind `tooling`. No Python source changes; manifests, one new test file, the design.

## Research Notes

Measured 2026-10-27 with a probe over all 63 `src/specweaver/**/context.yaml` and `tach.toml`
(`.tmp/probe_manifests.py`, gitignored).

- **32 manifests lack fields** (FR-6): 26 lack `name` and `purpose` — every `sandbox/*/core|interfaces`
  (14), the `*/interfaces` of standards, validation, config, graph, llm; `graph/core`; `workspace`;
  4 lack only `name` (`core/flow/interfaces`, the drafting, implementation, review and
  `workspace/project` interfaces). 5 also lack `archetype`: `graph`, `graph/core/builder`,
  `graph/core/engine`, `graph/core/store`, `sandbox/execution`.
- **6 phantom `exposes`** (FR-6): `assurance/standards` `StandardsInferrer`; `assurance/graph`
  `Selectors`; `workflows/implementation` `CodeGenerator`; `interfaces/cli` `get_db` (imported, not
  defined, in `_core.py`); `assurance/validation/rules` `spec/*`, `code/*` (directory globs that do
  match). Data files (`workflows/frameworks/*.md`, `workflows/pipelines/*.yaml`) exist.
- **Missing manifests** (FR-7): `sandbox` (the tach module falls back to the root
  `src/specweaver/context.yaml`), `workflows/scenarios`, `workflows/evaluators`, `workspace/memory`,
  `core/flow/engine`, `core/flow/handlers`.
- **83 `tach.toml` edges not covered by `consumes`**, over 28 modules (FR-4). 20 of them are the
  `deprecated` edges SF-01 owes; the other 63 are plain edges the manifests never declared. One
  `forbids` conflict: `core/flow` forbids `workflows/drafting`, a `deprecated` edge owed by FR-13.
- **Another schema** in the six `graph/**` manifests: `module_name`, `layer`, `allowed_imports`,
  `forbidden_imports`, no `archetype`/`consumes`. `tests/unit/graph/core/builder/test_declared_imports.py`
  reads `allowed_imports`. This is `TECH-080` finding **AG-15**.
- **Wrong labels** (FR-8): `sandbox/web/interfaces` `archetype: orchestrator` while `tool.py:112`
  calls `httpx.post`; `sandbox/execution` has none.

## Approach (pseudocode, ordered)

**The agreement rule (FR-4)**, one test file `tests/unit/test_manifests_match_tach.py`:
- a tach module is governed by the manifest in its own directory; a module that is one file
  (`_version`, `telemetry_logger`) has no directory and is governed by `tach.toml` alone;
- every plain `depends_on` target T is covered when some `consumes` entry C (slash → dot, `/*`
  dropped) equals T, contains T, or is a part of T;
- no `forbids` entry names a plain target;
- `deprecated` edges are skipped: they are owed in the ledger, not declared (SF-01, FR-3).

**CB-1 — fields, phantoms and labels (FR-6, FR-8)**
1. Tests first (red), `tests/unit/test_manifests_are_complete.py`: every manifest has non-empty
   `name`, `purpose`, `archetype`; every `exposes` entry is a file, directory or glob in the package, or
   a name the package defines or imports at module level; `sandbox/web/interfaces` is `adapter`.
2. Write `name` and `purpose` for the 32 (purpose from the module's code and existing `description`);
   `archetype` for the 5; drop the 4 phantom names; `web/interfaces` → `adapter`.

**CB-2 — the manifests match `tach.toml` (FR-4, FR-7)** — closes SF-02
3. Test first (red): the agreement rule above.
4. Add the 6 missing manifests with the `consumes` their tach module needs (engine and handlers get
   theirs now; they become tach modules in SF-04).
5. Add the 63 missing `consumes` entries to the 28 manifests; rewrite the drifted `core/config`,
   `workspace`, `workspace/project`, `assurance/standards`, `core/flow` text (CW-14, AG-16, FL-7).
6. `graph/**`: the six manifests take the standard schema (`name`, `purpose`, `archetype`,
   `consumes`, `forbids`); `test_declared_imports.py` reads `consumes` `[agreed 2026-10-27]`.

## Test Plan

| Tier | Test | Proves | Red first because |
|---|---|---|---|
| unit | every manifest has `name`, `purpose`, `archetype` | FR-6 | 32 lack them |
| unit | every `exposes` entry exists | FR-6 | 4 phantoms |
| unit | `sandbox/web/interfaces` is `adapter`; `sandbox/execution` has an archetype | FR-8 | `orchestrator`; none |
| unit | the 6 missing manifests exist | FR-7 | absent |
| unit | every plain tach edge is in `consumes`; no `forbids` names one | FR-4 | 63 uncovered |

Mutants: drop one `consumes` entry; add a phantom to `exposes`; blank a `purpose`; set
`web/interfaces` back to `orchestrator`; delete `workspace/memory/context.yaml` (via `old`=its
`name:` line → empty manifest). Each must turn a test red.

## Commit Boundaries

| CB | Holds | Done when |
|---|---|---|
| CB-1 | steps 1–2 | full suite green; FR-6, FR-8 mutants killed; commit |
| CB-2 | steps 3–6 | full suite green; FR-4, FR-7 mutants killed; stage and stop (closes SF-02) |

## Documentation

`docs/architecture/03_system_topology/context_yaml_spec.md` already defines the fields; no change.

## Architecture Verification (Phase 3)

- Manifests only; no import changes; `tach check` unchanged.
- Declaring a plain edge in `consumes` follows SF-01's approved sort; no `deprecated` edge is declared.

## Audit (Phase 2) — settled

❓ **Q1 — the `graph/**` manifests (`TECH-080` AG-15).** They use another schema (`allowed_imports`,
no `archetype`), so FR-4 and FR-6 cannot hold for `graph` without touching them. AG-15 is filed under
`TECH-080` ("manifests are read five ways").
- **A:** SF-02 converts the six to the standard schema and points `test_declared_imports.py` at
  `consumes`; AG-15 moves from `TECH-080` to `TECH-081`.
- **B:** SF-02 skips `graph/**` in both tests and names `TECH-080` AG-15 as the reason; FR-4 and
  FR-6 hold for every other module.

The user chose A `[agreed 2026-10-27]`: AG-15 moved to `TECH-081`.

## Consistency (Phase 5)

- Red/Blue, 2 cycles:
  - R1 (MEDIUM) "contains or is a part of" lets a coarse `consumes` (`specweaver/sandbox/*`) cover
    any sandbox edge. Blue: that matches tach's own grain (`specweaver.sandbox` is one module); finer
    rules stay with the manifest-level tests like `test_declared_imports.py`.
  - R2 (MEDIUM) skipping one-file modules leaves `telemetry_logger → core.config` unchecked by a
    manifest. Blue: tach still checks it; a manifest needs a directory.
  - R3 (LOW) writing 32 purposes by hand may guess. Blue: each is written from the module's own code
    and existing `description`, read in CB-1.
  - Cycle 2: no new finding.
