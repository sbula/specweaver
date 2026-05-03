# [US-XX] Integration Contract

**Story Name:** [Feature Name]
**Status:** [Integrated / In Progress]
**Date Integrated:** [YYYY-MM-DD]

## 1. Architectural Boundary
*Define the exact physical boundaries of this feature inside the codebase.*
- **Core Module Path:** `src/specweaver/...`
- **External Dependencies Allowed:** [List any cross-domain calls allowed]
- **Dependent Modules:** [List any domains that rely on this feature]

## 2. Input / Output Schemas
*Define the explicit data structures that cross the boundary of this module. Do not list internal implementation details, only the public API.*
- **Input Contracts:**
  - `[ClassName]` (e.g. `ValidationContext`): [Brief description of what it accepts]
- **Output Contracts:**
  - `[ClassName]` (e.g. `ValidationResult`): [Brief description of what it returns]

## 3. Tach Sealing Configuration
*Explicitly list the rules added to `tach.toml` to enforce this boundary.*
```toml
[[modules]]
path = "<exact.module.path>"
depends_on = [
    "<allowed.dependency.1>",
]
strict = true
```

## 4. E2E Verification Matrix
*This contract is void without a passing E2E test. Explicitly list the filepath and what scenario it proves.*
- **E2E Filepath:** `tests/e2e/capabilities/.../test_foo_e2e.py`
- **Verification Scenario:** [Brief description of the E2E user flow being tested]
