---
description: "Phase 0: Technical Research — two parallel tracks (deep codebase + external API docs) before planning. Fully autonomous, no HITL."
---

> [!IMPORTANT]
> **This phase is fully autonomous. No HITL.**
> Execute both tracks, then synthesize. Do not stop for confirmation.

// turbo-all

# Phase 0: Technical Research

This phase performs a deeper, more technical research than the design-phase research.
It targets the exact code, APIs, and patterns that the implementation plan will reference.

---

## Track A — Deep Codebase Dive (autonomous)

A.1. Read the Design Document in full (path from the impl plan header block).
     Re-read the sub-feature section to confirm the exact scope of THIS plan:
     scope, FRs subset, inputs, outputs, depends_on.

A.2. Identify every source file that will be created or modified by this sub-feature.
     Read each one in full. Record:
     - Exact class and function signatures (name, parameters, return types, decorators)
     - Pydantic model fields: required vs optional, field types, validators, aliases
     - Current DB schema: find the latest migration version in `_schema.py` and all mixins
     - Pipeline YAML conventions: field names, step types, gate types, loop targets
     - Factory patterns: how adapters, handlers, or atoms are registered and resolved
     - Any patterns (decorators, base classes, protocols) the new code must follow

A.3. Read all existing test files covering the modules to be modified.
     For each: what scenarios are covered? What is missing?

A.4. Read adjacent modules this sub-feature will consume or be consumed by.
     Understand their public interface (what can be called, what they expect as input).

---

## Track B — Technical External Research (autonomous)

B.1. For each tool in the design doc's External Dependencies table:
     - Find the specific documentation section for the exact API surface this SF needs.
       (Not the tool's home page — the specific class, function, or endpoint.)
     - Record the exact method signatures, parameters, and return types needed.
     - Search for migration guides if upgrading from the currently pinned version.
     - Search for known bugs, gotchas, or open issues at the target version.

B.2. Check `pyproject.toml` for transitive dependency conflicts that adding
     or upgrading this tool would introduce.

---

## Synthesis (sequential, after both tracks)

S.1. Append a `## Research Notes` section to the implementation plan being drafted.
     Include any finding that:
     - Changes or constrains a technical decision in the plan
     - Reveals an exact function signature or model field the plan must use
     - Flags a known bug or gotcha at the target version
     - Shows a conflict with existing code the plan must resolve

> [!IMPORTANT]
> **CHECKPOINT:** Phase 0 complete. Research Notes appended to the plan.
> Proceed to Phase 1 (Preparation).
