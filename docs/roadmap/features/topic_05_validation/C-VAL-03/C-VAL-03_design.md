# Feature 3.20b: Dynamic Risk-Based Rulesets (DAL) 

- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_05_validation/C-VAL-03/C-VAL-03_design.md
SpecWeaver must be able to support "Mixed Criticality" software systems where some modules require
aerospace-grade validation (DAL A) while others run basic startup scripts (DAL E). Feature 3.20b
implements a DO-178C / ISO 26262 compliant risk-based testing framework. It utilizes "Fractal
Resolution" to evaluate risk independently per-file and employs Pydantic Deep-Merge to override
execution profiles based on a standard corporate safety matrix. Furthermore, it explicitly
outsources "Freedom from Interference" boundary checks to native linters (e.g., Tach, ArchUnit,
ESLint).

## 2. Requirements & Constraints
### Functional Requirements

Rewritten into the ledger's table form 2026-08-17 under `specweaver-dev` §3.2c, from
`INT-US-25-SF01-MIG`. **The five requirements were always here — as prose bullets (`**FR1 …**`), which
`check_fr_coverage.py` and `check_fr_sweep.py` both read as no requirements at all**, since both match
`| FR-N |` table rows. A capability with five FRs and five committed sub-features counted as declaring
nothing. Second instance in this migration, after `C-EXEC-01`; wording preserved in both.

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Assignment | Module | Declares `operational.dal_level: DAL_<X>` in its `context.yaml` | A module's risk tier lives next to the module, in the file that already describes it |
| FR-2 | Governance | Agent, then Architect | Proposes a DAL per component during decomposition, for a human to approve | A criticality rating is always *proposed explicitly* and never arrived at by omission |
| FR-3 | Resolution | `ValidationRunner` | Resolves the applicable DAL by walking up the directory tree per target file | A tier declared once at a boundary governs everything beneath it — nobody annotates every file |
| FR-4 | Impact Matrix | Project | Supplies `.specweaver/dal_definitions.yaml`, deep-merged over the standard domain profiles | Rules can be augmented or disabled (`Rule_X: null`) without forking the packaged matrix |
| FR-5 | FFI Isolation | `QARunner` | Runs the native boundary linter against the target project and merges its findings with per-file `forbids` | Cross-boundary isolation is outsourced to tools that already do it, and both sources are reported as one |

**FR-2 survived its first mutant, and the survivor was the dangerous kind.** The requirement's teeth are
the *required* `proposed_dal` field on `ComponentChange` — that is what forces a proposal to exist for a
human to approve. Giving it `default=DALLevel.DAL_E` passed the entire suite.

`DAL_E` is the **lowest** criticality. An agent that simply omitted the field would have had every
component rated least-critical: a safety downgrade arriving as a missing key, with no architect ever
shown a proposal to approve. `test_a_component_without_a_proposed_dal_is_rejected` closes it. **A default
is not a neutral act when the field it fills is a risk tier.**

FR-1 and FR-3 each fail 17 files; FR-5 fails 15; FR-4 fails 1. FR-3's mutant is worth reading — stopping
the walk at the target's own directory leaves the resolver running and correct for any directory that
declares its own tier, and silently strips inheritance from everything below, which is most of the tree.

FR-4's single test is thin for a requirement that lets a project **disable** rules inside a safety-tier
matrix, and the count is recorded as thin rather than dressed up.

### Non-Functional Requirements
*   **NFR1:** LLMs are strictly forbidden from participating in the FFI Validation loop (Must remain strictly Deterministic).
*   **NFR2:** Deep merges must be schema-validated post-merge to prevent implicit rule corruption (Semantic Ambiguity).
*   **NFR3:** The Polyglot mandate dictates `dev_guides` must enforce native boundary linters for all newly supported languages.

## 3. Codebase Patterns (Where to Implement)

To prevent hallucinations, the implementation of Feature 3.20b must physically occur in the following established architectural layers:

*   **DAL Schema & Impact Matrix (SF-01):**
    *   `src/specweaver/validation/models.py`: Define `DALLevel(str, Enum)` and update validation schemas.
    *   `src/specweaver/config/settings.py`: Configure Pydantic's `SettingsConfigDict` to load and deep-merge the local `.specweaver/dal_definitions.yaml`.
*   **Fractal Resolution Engine (SF-02):**
    *   `src/specweaver/validation/pipeline.py`: Inside the `ValidationRunner`, implement the `O(1)` cached `resolve_dal()` directory-walker logic before applying rulesets.
*   **Validation Override Consolidation (SF-03):**
    *   `src/specweaver/config/database.py` and `config/_schema.py`: Delete legacy SQLite `validation_overrides` tables and finalize the DAL-centric matrix workflow.
*   **Generative HARA Governance (SF-04):**
    *   `src/specweaver/drafting/decomposition.py` (or prompt templates): Inject HARA heuristics
        (Topology + Data Sensitivity) into the prompt building cycle so the AI proposes optimal DAL
        strings during `/design` scaffoldings.
*   **Outsourced FFI Rules (SF-05):**
    *   `src/specweaver/loom/commons/qa_runner/{language}/runner.py`: Implement the stubs for
        `run_architecture_check` in Java (ArchUnit) and TypeScript (ESLint) to actively enforce
        boundaries dynamically loaded from `context.yaml` and DAL overrides.

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
| **SF-01** | DAL Schema & Pydantic Impact Matrix Merge | Define the `DALLevel` enumerations and configure `pydantic-settings` to safely deep-merge `dal_definitions.yaml` over base profiles. | [x] Complete |
| **SF-02** | Fractal Resolution Engine | Implement `O(1)` cached directory-tree walking in `ValidationRunner` to map target files to their closest `context.yaml` DAL. | [x] Complete |
| **SF-03** | Validation Override Consolidation (Cleanup) | Strip the legacy SQLite `validation_overrides` tables and force all resolution exclusively through the DAL Impact matrices and rule sub-pipeline inheritance. | [x] Complete |
| **SF-04** | Generative HARA (AI Governance Proposal) | Update the `/design` scaffolding workflow so LLMs analyze topological edges/data to propose a DAL, requiring HITL approval. | [ ] Pending |
| **SF-05** | Polyglot Architecture Configs | The generic `run_architecture_check` interface was established in 3.20a. Here, we build out the concrete Polyglot adapters (`JavaRunner` -> ArchUnit, `TypeScriptRunner` -> ESLint) and dynamically generation their configuration payloads based on `context.yaml` constraints and the active DAL string. | [x] Complete |

## 6. Progress Tracker
- [x] Requirements Finalized
- [x] SF-01 Implementation Plan ✅
- [x] SF-01 Implementation
- [x] SF-02 Implementation Plan ✅
- [x] SF-02 Implementation ✅
- [x] SF-03 Implementation Plan ✅
- [x] SF-03 Implementation ✅ (Dev ✅, Pre-Commit ✅, Committed ✅)
- [x] SF-04 Implementation Plan ✅
- [x] SF-04 Implementation ✅ (Pre-Commit ✅, Committed ✅)
- [x] SF-05 Implementation Plan ✅
- [x] SF-05 Implementation ✅ (Dev ✅, Pre-Commit ✅, Committed ✅)

## 7. Session Handoff

**Current status**: SF-05 is complete and committed.
**Next step**: Proceed with SF-06 or wrap up Feature 3.20b.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there using the appropriate workflow.
