---
description: "Phase 1: Preparation — read the Design Document, architecture reference, and the plan; cross-reference against the codebase."
---

# Phase 1: Preparation

> [!IMPORTANT]
> **This phase is fully autonomous. No HITL.**
> Load all context before any auditing begins.

1.1. **Read the Design Document in full** (path from the impl plan header block).
     This is the primary authoritative source. It defines:
     - FRs and NFRs for this sub-feature
     - External dependencies and validated versions
     - Architectural decisions and HITL-approved switches
     - Sub-feature scope, inputs, and outputs
     - Other sub-features this one depends on

1.2. **Read the architecture reference in full**:
     `docs/architecture/architecture_reference.md`
     Pay special attention to: module map, dependency rules (`consumes`/`forbids`),
     archetypes, Known Boundary Violations, and Anti-Patterns.

1.3. **Read the implementation plan file** at the provided path in its entirety.
     If any link or reference document is mentioned, read those too.

1.4. **Cross-reference the plan against**:
     - The existing codebase architecture (`context.yaml` files, `flow/models.py`, `flow/handlers.py`)
     - The existing pipeline YAMLs (`pipelines/*.yaml`)
     - Existing Developer and User Guides (`docs/dev_guides/`, `docs/user_guides/`)
     - Patterns established by completed features (check adjacent impl plans in the same phase dir)
     - The Capability Matrix (`docs/roadmap/capability_matrix.md`) and User Stories (`docs/roadmap/master_story_roadmap.md`) for downstream feature dependencies
     - The pre-commit quality gate skill (`.agents/skills/specweaver-pre-commit/SKILL.md`)

> [!IMPORTANT]
> **CHECKPOINT:** Phase 1 complete. All context loaded.
> Proceed to Phase 2 (Audit & Analysis).
