---
description: "Phase 6: Update documentation — test matrix, README, quickstart, roadmap, architecture reference."
---
// turbo-all

> [!IMPORTANT]
> **All test, lint, mypy, architecture, complexity, file size, e2e, and integration commands MUST be executed autonomously.**
> Set `SafeToAutoRun: true` for ALL of these commands.
> **NO SHELL COMPOUNDING**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`). The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call.
> NEVER prompt the user for confirmation to run checks. Just run them.



# Phase 6: Documentation Updates

// turbo-all

6.1. Update `docs/test_coverage_matrix.md` with the corrected test count and
     any new entries for modules added or modified in this feature. Do not forget
     to update the story -> unit/integr/e2e/... matrices!

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

> [!IMPORTANT]
> Every bug, lint error, complexity violation, or oversized file MUST be fixed
> regardless of whether it is pre-existing or introduced by this feature.
> No inherited problems are acceptable!