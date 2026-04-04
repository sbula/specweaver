# Feature 3.20a: Internal Layer Enforcement (Tach)

- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/proposals/roadmap/phase_3/feature_3_20a/feature_3_20a_design.md
Currently, SpecWeaver relies on standard Python linting (`ruff`) and `__init__.py` boilerplate encapsulation to prevent architectural spaghetti. This is insufficient to guarantee that L3 Capabilities do not accidentally depend on L1 Interface dependencies. Feature 3.20a formally adopts `Tach` (a Rust-based Python architectural linter) to mathematically enforce a strict Domain-Driven "Layer Cake" architecture across the `src/specweaver/` directory.

## 2. Requirements & Constraints
### Functional Requirements
*   **FR1:** `Tach` must be added as a dev-dependency in `pyproject.toml`.
*   **FR2:** A `tach.yml` configuration must formally define the structural layout of SpecWeaver (Base Layer, Resources, Capabilities, Orchestrators, Presentation).
*   **FR3:** Strict dependency boundaries must be enforced (e.g., Domain Logic cannot import CLI utilities).
*   **FR4:** Public Interfaces must be formally explicitly declared via Tach.

### Non-Functional Requirements
*   **NFR1:** Must replace/delete unnecessary `__init__.py` encapsulation hacks (`__all__ = [...]`).
*   **NFR2:** Tach execution (`tach check`) must be integrated into the `pre-commit` workflow.

## 3. Codebase Patterns (Where to Implement)

To prevent breaking the CI pipeline, the implementation of Feature 3.20a must physically target the following files:

*   **SF-1 (Base Layer Initialization):**
    *   `pyproject.toml`: Add `tach` to dev dependencies.
    *   `tach.toml` (or `tach.yml`): Root configuration defining the Base Layer boundaries (`src.specweaver.config`, `src.specweaver.standards`).
*   **SF-2 (Resource/Capability Hardening):**
    *   `tach.toml`: Define Resource Layer (`src.specweaver.llm`, `src.specweaver.graph`) and block upward dependencies.
*   **SF-3 (Presentation Layer):**
    *   `tach.toml`: Define Presentation Layer (`src.specweaver.api`, `src.specweaver.cli`) and block internal logic from importing them.
*   **SF-4 (Interface Enforcement):**
    *   `tach.toml`: Enable `interfaces:` mapping.
    *   Delete `__init__.py` boilerplate across `src/specweaver/**`.

## 4. Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | **Standalone Refactor Feature** | Adopting Tach across the core architecture generates massive diffs. Sneaking it into 3.20b violates single-responsibility and destroys CI green-state reliability. It must be isolated as Feature 3.20a. | No |
| AD-2 | **Replacing `__init__.py`** | Use `Tach` `interfaces` mapping to formally define public module boundaries and delete messy `__init__.py` encapsulation hacks throughout `src/specweaver/`. | No |
| AD-3 | **Replacing Ruff TID252** | Drop Reliance on `ruff` tidy-imports in favor of true Domain-Driven Layer graphing via `Tach`. | No |

## 5. Sub-Feature Decomposition

| SF ID | Name | Description | Status |
|:---|:---|:---|:---|
| **SF-1** | Initialization & Base Layer Isolation | Install Tach. Map `config`, `standards`, and `logging.py` as strict base layers. Ensure they import absolutely nothing else from SpecWeaver. | [ ] Pending |
| **SF-2** | Resource & Core Capability Hardening | Apply Tach rules to the `llm`, `graph`, `context`, and `project` modules. Formally isolate the `llm` engine from the business logic. | [ ] Pending |
| **SF-3** | Presentation Layer Sterilization | Enforce that no domain logic inside `src/specweaver` is allowed to depend on `api` or `cli`. | [ ] Pending |
| **SF-4** | Public Interface Enforcement | Use Tach's `interfaces:` to declare strict public boundaries and delete the messy `__init__.py` boilerplate hacks. | [ ] Pending |

## 6. Progress Tracker
- [ ] Requirements Finalized
- [ ] SF-1 Implementation
- [ ] SF-2 Implementation
- [ ] SF-3 Implementation
- [ ] SF-4 Implementation
- [ ] Merged

## 7. Session Handoff

**Current status**: Design APPROVED.
**Next step**: Run the following command to begin implementation planning:
`/implementation-plan docs/proposals/roadmap/phase_3/feature_3_20a/feature_3_20a_design.md SF-1`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there using the appropriate workflow.
