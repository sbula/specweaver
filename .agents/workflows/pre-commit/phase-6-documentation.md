---
description: "Phase 6: Update documentation — test matrix, README, quickstart, roadmap, architecture reference."
---

# Phase 6: Documentation Updates

// turbo-all

6.1. Update `docs/test_coverage_matrix.md` with the corrected test count and
     any new entries for modules added or modified in this feature. Do not forget
     to update the story -> unit/integr/e2e/... matrices!

6.2. Review and update these documents if they are affected by the feature:
     - `README.md` — features list, CLI commands table, project structure
     - `docs/quickstart.md` — new workflows or commands
     - `docs/testing_guide.md` — new test patterns or quality gates
     - `docs/proposals/specweaver_roadmap.md` — feature completion status
     - `docs/proposals/roadmap/phase_3_feature_expansion.md` — milestone tracking
     - Any feature-specific implementation plan or design doc

6.3. **MANDATORY: Update the architecture reference** if this feature changed
     any module placement, dependency direction, layer boundaries, security
     patterns, or dispatch mechanisms:
     ```
     docs/architecture/architecture_reference.md
     ```
     Add new anti-patterns discovered during this feature. Update the sub-layer
     structure diagram if new modules were added or moved.

> [!IMPORTANT]
> Every bug, lint error, complexity violation, or oversized file MUST be fixed
> regardless of whether it is pre-existing or introduced by this feature.
> No inherited problems are acceptable!
