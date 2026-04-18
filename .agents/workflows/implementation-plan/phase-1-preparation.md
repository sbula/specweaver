---
description: "Phase 1: Preparation — read the Design Document, architecture reference, and the plan; cross-reference against the codebase."
---

> [!CAUTION]
> **NO SHELL COMPOUNDING & NO PIPES**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`) or using inline scripts like `python -c`. The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call or write a `.py` script and run it.

> [!IMPORTANT]
> **This phase is fully autonomous. No HITL.**
> Load all context before any auditing begins.

// turbo-all

# Phase 1: Preparation

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
     - The roadmap (`phase_3_feature_expansion.md`) for downstream feature dependencies
     - The pre-commit quality gate workflow (`.agents/workflows/pre-commit.md`)

> [!IMPORTANT]
> **CHECKPOINT:** Phase 1 complete. All context loaded.
> Proceed to Phase 2 (Audit & Analysis).
