# C-EXEC-03 SF-01 — Domain Realignment

**Status**: APPROVED · **Feature ID**: 3.26a (SF-01) · **Depends on**: — ·
Design: [C-EXEC-03_design.md](C-EXEC-03_design.md) §Sub-features → SF-01

**FRs owned: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-9, FR-10.** The `src/` relocations, the
import sweep, and the boundary config that describes them. Recorded 2026-08-17 under
`specweaver-dev` §3.2c, from `INT-US-01-SF02-MIG`. Proof:
`tests/unit/test_macro_domain_layout.py`, each guard verified by mutating the tree.

**FR-5's `loom` clause is struck** — there is no `loom` package; the Loom is the top-level
`sandbox/`. See the design's findings section.

## Goal

Move the flat root source directories and tests into the 6 macro-domains (`workflows`, `assurance`,
`workspace`, `interfaces`, `core`, `infrastructure`), patch all absolute imports, and move the
`roadmap` and `design` directories under `docs/`.

## Changes

1. **Source** — `mkdir` the 6 macro-domains under `src/specweaver/`, then move each module per the
   design mapping:

```bash
# Group 1: Workflows
mv src/specweaver/drafting src/specweaver/workflows/
mv src/specweaver/planning src/specweaver/workflows/
mv src/specweaver/implementation src/specweaver/workflows/
mv src/specweaver/review src/specweaver/workflows/
mv src/specweaver/pipelines src/specweaver/workflows/

# Group 2: Assurance
mv src/specweaver/validation src/specweaver/assurance/
mv src/specweaver/standards src/specweaver/assurance/
mv src/specweaver/graph src/specweaver/assurance/

# Group 3: Workspace
mv src/specweaver/project src/specweaver/workspace/
mv src/specweaver/context src/specweaver/workspace/

# Group 4: Interfaces
mv src/specweaver/cli src/specweaver/interfaces/
mv src/specweaver/api src/specweaver/interfaces/

# Group 5: Core
mv src/specweaver/flow src/specweaver/core/
mv src/specweaver/loom src/specweaver/core/
mv src/specweaver/config src/specweaver/core/

# Group 6: Infrastructure
mv src/specweaver/llm src/specweaver/infrastructure/
```

2. **Unit & integration tests** — `tests/unit/` and `tests/integration/` mirror the 6 macro-domains:

```bash
# Example mapping
mkdir -p tests/unit/workflows
mv tests/unit/drafting tests/unit/workflows/
mv tests/unit/flow tests/unit/core/
# ... and so forth across unit and integration.
```

3. **E2E** — `tests/e2e/` from a flat tree into business capability folders (epics/features).
4. **Import sweep and `context.yaml` topologies** — find-and-replace across `src/specweaver/`,
   `tests/` and `docs/`: `.py` (imports), `.md` (references), `.yaml` (including `context.yaml`
   `consumes`/`forbids`). Old paths become e.g. `specweaver.workflows.drafting`,
   `specweaver.assurance.validation`.
5. **NFR-3** — file counts before/after prove 0 logic or models lost in the `mv` operations.
6. **Documentation** — relocate feature design documents and the roadmap:

```bash
mv docs/architecture/* docs/architecture/
rm -r docs/proposals/design/
mv docs/roadmap docs/roadmap
```

## Tests

- `pytest` (all 3884 tests) — runs on `PYTHONPATH` without `ModuleNotFoundError`.
- `git status` — file maps as expected.
- No manual verification; the structure tests catch failures.

## Decisions (audit)

1. **Implicit namespaces**: per Feature 3.20a, zero `__init__.py` files for the structural
   boundaries — folders move, topologies stay implicit.
2. **Replace scope**: string replacements across Python (`.py`), Markdown (`.md`) and Configuration
   (`.yaml`) with shell scripting, so legacy absolute paths are gone everywhere, docs included.
