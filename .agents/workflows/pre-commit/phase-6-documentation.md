---
description: "Phase 6: Update documentation — test matrix, README, quickstart, roadmap, architecture reference."
---

> [!CAUTION]
> **NO SHELL COMPOUNDING & NO PIPES**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`) or using inline scripts like `python -c`. The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call or write a `.py` script and run it.

// turbo-all

> [!IMPORTANT]
> **All test, lint, mypy, architecture, complexity, file size, e2e, and integration commands MUST be executed autonomously.**
> Set `SafeToAutoRun: true` for ALL of these commands.
> **NO SHELL COMPOUNDING**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`). The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call.
> NEVER prompt the user for confirmation to run checks. Just run them.



# Phase 6: Documentation Updates

// turbo-all

6.2. **MANDATORY**: You MUST explicitly open, read, and update ALL of the following documents if they exist. DO NOT skip any of them under the assumption that they don't need updates:
     - `README.md` — updating features list, CLI commands table, project structure, test counts
     - `docs/quickstart.md` — new workflows or commands
     - `docs/testing_guide.md` — new test patterns or quality gates
     - `docs/proposals/specweaver_roadmap.md` — updating the feature's completion status and timeline
     - `docs/developer_guide.html` - add diagrams and short descriptions for new/updated feature
     - `docs/proposals/roadmap/phase_3_feature_expansion.md` — mark milestone tracking and tables
     - `docs/proposals/roadmap/.../<feature_implementation_plan>.md` — The specific plan for this feature MUST be updated to reflect what was actually implemented (e.g. check off boxes, add notes on deviations).

6.3. **MANDATORY: Update the architecture reference and developer guide** if this feature
     changed any module placement, dependency direction, layer boundaries, security
     patterns, or dispatch mechanisms. You MUST explicitly open, read, and update these:
     - `docs/architecture/architecture_reference.md`
     - `docs/developer_guide.html`
     
     Add new anti-patterns discovered during this feature. Update the sub-layer
     structure diagram if new modules were added or moved.

6.4. **MANDATORY: Keep Developer Guides Up to Date (`docs/dev_guides/`)**:
     - Review the existing guides in `docs/dev_guides/` (e.g., `pipeline_engine_guide.md`, `adding_tools_and_atoms.md`, etc.).
     - If this feature modified the systems or processes described in those guides, you MUST update them to reflect the current truth.
     - **SPECIAL PATTERNS**: If this feature invents a new non-standard workaround, unique architecture pattern, or custom adaptation, you MUST append it to `docs/dev_guides/special_patterns_and_adaptations.md`.
     - **CREATING NEW GUIDES**: Evaluate if this feature introduced a significant new topic or extension point (e.g., a new subsystem) that needs its own guide. If so, create one.

> [!IMPORTANT]
> Every bug, lint error, complexity violation, or oversized file MUST be fixed
> regardless of whether it is pre-existing or introduced by this feature.
> No inherited problems are acceptable!