# Feature 3.20b: Dynamic Risk-Based Rulesets (DAL) 

- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/proposals/roadmap/phase_3/feature_3_20b/feature_3_20b_design.md
SpecWeaver must be able to support "Mixed Criticality" software systems where some modules require aerospace-grade validation (DAL A) while others run basic startup scripts (DAL E). Feature 3.20b implements a DO-178C / ISO 26262 compliant risk-based testing framework. It utilizes "Fractal Resolution" to evaluate risk independently per-file and employs Pydantic Deep-Merge to override execution profiles based on a standard corporate safety matrix. Furthermore, it explicitly outsources "Freedom from Interference" boundary checks to native linters (e.g., Tach, ArchUnit, ESLint).

## 2. Requirements & Constraints
### Functional Requirements
*   **FR1 (Assignment):** Modules declare their risk tier inside `operational.dal_level: DAL_<X>` within `context.yaml`.
*   **FR2 (Governance):** During SpecWeaver `/design` scaffolding, Agents perform topological HARA analysis to propose a DAL; Human Architects must approve it via a HITL gate.
*   **FR3 (Resolution):** `ValidationRunner` uses Fractal Resolution to resolve the applicable DAL by walking up the directory tree on a per-file target basis.
*   **FR4 (Impact Matrix):** Projects can provide a `.specweaver/dal_definitions.yaml`. Pydantic must safely Deep-Merge this over standard Domain Profiles, allowing rules to be augmented or disabled (`Rule_X: null`).
*   **FR5 (FFI Isolation):** Dynamic cross-boundary Mixed Criticality isolation is outsourced via the Feature 3.19 `QARunner` orchestrator (e.g., executing `ArchUnit` / `Tach` against the target user project).

### Non-Functional Requirements
*   **NFR1:** LLMs are strictly forbidden from participating in the FFI Validation loop (Must remain strictly Deterministic).
*   **NFR2:** Deep merges must be schema-validated post-merge to prevent implicit rule corruption (Semantic Ambiguity).
*   **NFR3:** The Polyglot mandate dictates `dev_guides` must enforce native boundary linters for all newly supported languages.

## 3. Codebase Patterns (Where to Implement)

To prevent hallucinations, the implementation of Feature 3.20b must physically occur in the following established architectural layers:

*   **DAL Schema & Impact Matrix (SF-1):**
    *   `src/specweaver/validation/models.py`: Define `DALLevel(str, Enum)` and update validation schemas.
    *   `src/specweaver/config/settings.py`: Configure Pydantic's `SettingsConfigDict` to load and deep-merge the local `.specweaver/dal_definitions.yaml`.
*   **Fractal Resolution Engine (SF-2):**
    *   `src/specweaver/validation/pipeline.py`: Inside the `ValidationRunner`, implement the `O(1)` cached `resolve_dal()` directory-walker logic before applying rulesets.
*   **Validation Override Consolidation (SF-3):**
    *   `src/specweaver/config/database.py` and `config/_schema.py`: Delete legacy SQLite `validation_overrides` tables and finalize the DAL-centric matrix workflow.
*   **Generative HARA Governance (SF-4):**
    *   `src/specweaver/drafting/decomposition.py` (or prompt templates): Inject HARA heuristics (Topology + Data Sensitivity) into the prompt building cycle so the AI proposes optimal DAL strings during `/design` scaffoldings.
*   **Outsourced FFI Rules (SF-5):**
    *   `src/specweaver/loom/commons/qa_runner/{language}/runner.py`: Implement the stubs for `run_architecture_check` in Java (ArchUnit) and TypeScript (ESLint) to actively enforce boundaries dynamically loaded from `context.yaml` and DAL overrides.

## 4. External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| pydantic | 2.12 | `deep_merge=True` | Yes | Natively handles config merging and schema enforcement safely. |
| Native Linters | Any | `QARunner` Interface | Yes | ArchUnit (Java), ESLint (TS), Tach (Python) handles FFI constraints. |

## 4. Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | **Override vs Replace** | If a project configures `dal_definitions.yaml`, it MUST be Deep-Merged over the SpecWeaver defaults, rather than replacing them. This prevents inexperienced teams from accidentally deleting 14 critical safety checks by omission. | No |
| AD-2 | **Deterministic Rules vs LLMs** | Validation of DAL Freedom From Interference (FFI) MUST be 100% Traditional Deterministic (Tach, ArchUnit). Utilizing LLMs for validation disqualifies the pipeline from ISO 26262 / DO-178C compliance. | No |
| AD-3 | **Outsourcing Polyglot FFI** | SpecWeaver is an orchestrator, not an executor. Instead of building a massive polyglot AST parser, SpecWeaver translates `context.yaml` boundaries into the native linter configs (e.g. `ArchUnit`) and executes them via `QARunner`. | Yes — approved by user on 2026-04-04 |
| AD-4 | **Generative HARA Governance** | AI Agents propose the Module's DAL using HARA (data/topology heuristics) but Human Architects must approve via HITL before it is committed to `context.yaml`. | No |

## 5. Sub-Feature Decomposition

| SF ID | Name | Description | Status |
|:---|:---|:---|:---|
| **SF-1** | DAL Schema & Pydantic Impact Matrix Merge | Define the `DALLevel` enumerations and configure `pydantic-settings` to safely deep-merge `dal_definitions.yaml` over base profiles. | [x] Complete |
| **SF-2** | Fractal Resolution Engine | Implement `O(1)` cached directory-tree walking in `ValidationRunner` to map target files to their closest `context.yaml` DAL. | [x] Complete |
| **SF-3** | Validation Override Consolidation (Cleanup) | Strip the legacy SQLite `validation_overrides` tables and force all resolution exclusively through the DAL Impact matrices and rule sub-pipeline inheritance. | [x] Complete |
| **SF-4** | Generative HARA (AI Governance Proposal) | Update the `/design` scaffolding workflow so LLMs analyze topological edges/data to propose a DAL, requiring HITL approval. | [ ] Pending |
| **SF-5** | Polyglot Architecture Configs | The generic `run_architecture_check` interface was established in 3.20a. Here, we build out the concrete Polyglot adapters (`JavaRunner` -> ArchUnit, `TypeScriptRunner` -> ESLint) and dynamically generation their configuration payloads based on `context.yaml` constraints and the active DAL string. | [x] Complete |

## 6. Progress Tracker
- [x] Requirements Finalized
- [x] SF-1 Implementation Plan ✅
- [x] SF-1 Implementation
- [x] SF-2 Implementation Plan ✅
- [x] SF-2 Implementation ✅
- [x] SF-3 Implementation Plan ✅
- [x] SF-3 Implementation ✅ (Dev ✅, Pre-Commit ✅, Committed ✅)
- [x] SF-4 Implementation Plan ✅
- [x] SF-4 Implementation ✅ (Pre-Commit ✅, Committed ✅)
- [x] SF-5 Implementation Plan ✅
- [x] SF-5 Implementation ✅ (Dev ✅, Pre-Commit ✅, Committed ✅)

## 7. Session Handoff

**Current status**: SF-5 is complete and committed.
**Next step**: Proceed with SF-6 or wrap up Feature 3.20b.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there using the appropriate workflow.
