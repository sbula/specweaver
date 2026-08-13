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
     - **Requirement–Surface Bindings** — the FRs that cross a module boundary, and the provider
       surface each one consumes
     - External dependencies and validated versions
     - Architectural decisions and HITL-approved switches
     - Sub-feature scope, inputs, and outputs
     - Other sub-features this one depends on

     > [!IMPORTANT]
     > **The bindings table tells you where the integration tests go.** Every binding row is a seam
     > this sub-feature owns (`ADR-003`) — there is no later integration story to write it. Draw the
     > commit boundaries so each binding is proven at the boundary where its interface first exists
     > and its behaviour does not yet, and where step *n*'s interface depends on step *n−1*'s output,
     > put the test **between** them.
     >
     > A binding row whose "Verified how" says "assumed" or "unresolved" is a **precondition
     > failure, not a note**: the design did not converge, and planning on it repeats `INT-US-21`,
     > whose three prerequisites were all marked `✅` and all three materially broken.

1.2. **Read the architecture documentation in full** — one document per thing you need:
     - `docs/architecture/03_system_topology/module_dependency_graph.md` — module map
     - `docs/architecture/03_system_topology/hard_dependency_rules.md` — dependency rules
       (`consumes`/`forbids`)
     - `docs/architecture/01_foundational_principles/archetypes.md` — archetypes
     - `docs/architecture/06_lessons_and_future/known_boundary_violations.md` — the live
       Known Boundary Violations ledger
     - `docs/architecture/06_lessons_and_future/anti_patterns.md` — anti-patterns
     `docs/architecture/README.md` is the hub, but it is only a module tree — it does not
     contain any of the above.

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
