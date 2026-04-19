# Feature 3.32d Refactoring Design (Phase 3 Optimizations)

> **Status**: DRAFT
> **Goal**: Formalize the Tier 1 optimization implementations stemming from the Phase 3 retrospective. Further, resolve definitive implementation verdicts for Tier 2 opportunities.

## Tier 1: Approved Architecture Implementations

### 1.1 Context Condensation via AST Skeletons
- **Overview**: Reduce token over-spend by degrading specific `context_files` strictly into signatures and types (AST Skeletons) when generating large LLM prompt payloads.
- **Technical Design Constraints**:
  - Requires deep injection into `PromptBuilder.add_context_files()`.
  - Safely reuses `specweaver.loom.commons.language` AST parsing blocks.
  - Core implementation ensures the *actual target file being edited* remains completely unabridged. Skeletons apply solely to dependency/import hierarchies.
  - **Expected ROI**: Extreme reductions in token utilization.

### 1.2 Impact-Aware Test Limiting (Granular QA execution)
- **Overview**: Use the `TopologyGraph.stale_nodes` graph index to mathematically determine precisely which test boundaries are required instead of executing the global `pytest` suite.
- **Technical Design Constraints**:
  - Logic must be injected natively into the `PolyglotQARunner`.
  - Must cross-reference DAG hashes down to the parametrized test levels.
  - **Expected ROI**: Dramatic increase in single-loop speed and reduced cycle time without lowering the verification confidence bounds.

### 1.3 Automated CI/CD Risk Evaluation
- **Overview**: Lift the `Dynamic Assurance Layer (DAL)` out of the local developer flow entirely, enabling its execution as a unified headless command.
- **Technical Design Constraints**:
  - Exposes validation pipelines through a CLI arg (e.g., `sw scan --ci`).
  - Emits non-zero exit codes upon any DAL threshold breach.
  - **Expected ROI**: High. Establishes SpecWeaver natively as the organizational Policy Engine.

### 1.4 Project Standards Scaffolding
- **Overview**: Injects mature styling and domain conventions instantly into empty repositories upon `sw init`.
- **Technical Design Constraints**:
  - Maps domain settings sequentially from historical `context.db` states rather than inferring them anew.
  - Strict boundary compliance: Exceedingly avoids running LLM tools outright during workspace initiation (`workspace/project/context.yaml` explicitly forbids `loom` imports).
  - **Expected ROI**: Resolves the LLM "Blank Canvas Vacuum" problem cleanly.

---

## Tier 2: Deep Impact Analysis & Verdicts

### Dynamic Context Routing (Token/Limits Management)
- **Concept Deep Dive**: Should we monitor serialized Prompt Builder volumes, dynamically shifting LLM providers underneath the user? E.g., defaulting to Mistral for extreme velocity on simple tasks, but automatically re-routing massive (90K token) tasks to Gemini Pro 1.5 to avoid outright crash errors.
- **Verdict: APPROVED FOR PHASE 4**. 
  - *Reasoning*: Very low technical debt or architectural boundary risk. It resolves severe UX friction ("Context Window Exceeded") effortlessly by leveraging the unified `AdapterRegistry`. 

### Pre-Fetch Context Caching (Mention Scanners)
- **Concept Deep Dive**: Using parallel threads on CLI startup to preemptively trigger `FileSearch` and `Read_Skeleton` before the core `PromptBuilder` cycle initializes.
- **Verdict: REJECTED (DO NOT IMPLEMENT)**. 
  - *Reasoning*: The severe architectural risk of locking `SQLite context.db` databases between independent threads overrides the negligible sub-second UX speed improvement on start. Furthermore, attempting to execute `loom` processes transparently via UI/CLI logic breaches `Tach` separation barriers. 

---

## Progress Tracker

- [ ] 1.1 Context Condensation via AST Skeletons
- [ ] 1.2 Impact-Aware Test Limiting
- [ ] 1.3 Automated CI/CD Risk Evaluation
- [ ] 1.4 Project Standards Scaffolding
- [ ] 2.1 Dynamic Context Routing 
