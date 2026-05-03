# US-25 Integration Contract

**Story Name:** Compliance & Constitution Governance
**Status:** Integrated
**Date Integrated:** 2026-05-03

## 1. Architectural Boundary
*Define the exact physical boundaries of this feature inside the codebase.*
- **Core Module Path:** `src.specweaver.workspace.project`
- **External Dependencies Allowed:** None (Strictly foundational)
- **Dependent Modules:** 
  - `src.specweaver.workspace.context` (Consumes domain profiles)
  - `src.specweaver.core.flow` (Consumes constitution constraints)
  - `src.specweaver.assurance.validation` (Consumes profile paths)

## 2. Input / Output Schemas
*Define the explicit data structures that cross the boundary of this module. Do not list internal implementation details, only the public API.*
- **Output Contracts:**
  - `Constitution` (`src/specweaver/workspace/project/constitution.py`): Yields raw string data injected into LLM prompts to override Agent behavior.
  - `scaffold_project` (`src/specweaver/workspace/project/scaffold.py`): Produces physical `.specweaver/` environment bound to constraints.
  - `Discovery` (`src/specweaver/workspace/project/discovery.py`): Finds `CONSTITUTION.md` relative to `project_path`.

## 3. Tach Sealing Configuration
*Explicitly list the rules added to `tach.toml` to enforce this boundary.*
```toml
[[modules]]
path = "src.specweaver.workspace.project"
depends_on = []
strict = true

[[interfaces]]
from = [
    "src.specweaver.workspace.project",
]
expose = [
    "constitution",
    "scaffold",
    "discovery",
]
```

## 4. E2E Verification Matrix
*This contract is void without a passing E2E test. Explicitly list the filepath and what scenario it proves.*
- **E2E Filepaths:** 
  - `tests/e2e/capabilities/workspace/test_constitution_e2e.py`
  - `tests/e2e/capabilities/workspace/test_domain_profile_e2e.py`
- **Verification Scenario:** 
  - Proves `sw constitution show/check/init` interacts correctly with the filesystem and SQLite boundaries.
  - Proves Constitution strings are successfully appended to the internal `test_gen` and `code_gen` prompts dynamically.
