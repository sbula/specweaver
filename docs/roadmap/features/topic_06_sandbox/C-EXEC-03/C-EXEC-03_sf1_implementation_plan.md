# Implementation Plan: Domain Realignment (SF-1)

- **Feature ID**: 3.26a (SF-1)
- **Status**: APPROVED
- **Design Doc**: `docs/roadmap/phase_3/feature_3.26a/feature_3.26a_design.md`

## Overview
Physically migrates the flat root Source directories and Tests to the 6 explicit macro-domains (`workflows`, `assurance`, `workspace`, `interfaces`, `core`, `infrastructure`) and systematically patches all Python absolute imports in parallel. Additionally executes the movement of the `roadmap` and `design` directories under `docs/`.

## Resolved Technical Audits
> [!NOTE]
> **Resolution 1 (Implicit Namespaces):** We will strictly adhere to the Feature 3.20a architecture and create exactly zero `__init__.py` files for the structural boundaries. We are physically moving folders, but retaining implicit topologies.
>
> **Resolution 2 (String Replace Scope):** We will aggressively execute the string replacements across Python (`.py`), Markdown (`.md`), and Configuration (`.yaml`) files using global shell scripting to ensure the legacy absolute paths (like `specweaver.workflows.drafting`) are permanently erased physically and documented.

## Proposed Changes

### Component: Source Directory Restructuring
- Physically `mkdir` the 6 macro-domains: `workflows`, `assurance`, `workspace`, `interfaces`, `core`, `infrastructure` under `src/specweaver/`
- Physically move the current modules into their domains according to the Design Doc mappings. 

#### [MODIFY] Physical Folders
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

### Component: Unit & Integration Test Mirroring
- Structure the `tests/unit/` and `tests/integration/` paths to exactly mirror the 6 macro-domains.
- Move test scripts directly over into the matching folders.

#### [MODIFY] Test Folders
```bash
# Example mapping
mkdir -p tests/unit/workflows
mv tests/unit/drafting tests/unit/workflows/
mv tests/unit/flow tests/unit/core/
# ... and so forth across unit and integration.
```

### Component: E2E Restructuring
- Restructure `tests/e2e/` from a flat tree into explicit business capability folders mapping to Jira-style epics/features.

### Component: Broad String Import Patching & Context.yaml Topologies
- Execute a global find-and-replace sweep across all `src/specweaver/`, `tests/`, and `docs/`.
- `specweaver.workflows.drafting` becomes `specweaver.workflows.drafting`.
- `specweaver.assurance.validation` becomes `specweaver.assurance.validation`.
- This definitively targets `.py` files (imports), `.md` files (documentation references), and `.yaml` files (including `context.yaml` topological `consumes`/`forbids` arrays) to ensure clean system-wide handoffs.
- Enforce NFR-3: Validate via file counts before/after that exactly 0 logic or models are lost during the raw `mv` operations.

### Component: Documentation Refactoring
- Relocate Feature Design Documents.
- Relocate Roadmap.

#### [MODIFY] Documentation
```bash
mv docs/architecture/* docs/architecture/
rm -r docs/proposals/design/
mv docs/roadmap docs/roadmap
```


## Verification Plan

### Automated Tests
- Run `pytest` entirely natively. While 3884 tests exist, we will verify the code executes flawlessly inside the `PYTHONPATH` natively without `ModuleNotFoundError`.
- Run `git status` to verify file maps.

### Manual Verification
- None required. Matrix bound tests handle structural failures strictly.
