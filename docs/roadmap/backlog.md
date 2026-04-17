# SpecWeaver Central Backlog

> **Purpose:** This document centrally tracks all deferred Backlog and Technical Debt items generated during `/implementation-plan` workflows. Instead of losing tasks inside closed Implementation Plan markdown files, all backlog items must be recorded here to ensure they are picked up during future architectural passes.

## Phase 3 Features

### Feature 3.29: Archetype-Based Rule Sets
- **Markdown AST Mutators (SF-3):** Formally implement `extract_symbols()` and `rewrite_symbol_body()` on the newly established `MarkdownCodeStructure` module (`src/specweaver/core/loom/commons/language/markdown/`). Treat Markdown headings (e.g. `## Intent`) natively as code block symbols. This enables surgical LLM refactoring of documentation to completely eliminate the blind-overwrite truncation risk for large Spec documents.

### Feature 3.25: Router-Based Flow Control
- **Postponed Items:** (Refer to `feature_3_25_implementation_plan.md` for specific deferred router mapping capabilities).

### Feature 3.19: Polyglot QA Runner
- **Deferred Support:** (Refer to `feature_3_19_sf1_implementation_plan.md`).

### Feature 3.18: AST Drift Detection
- **Deferred Analysis Limits:** (Refer to `feature_3_18_sf1_implementation_plan.md`).

### Feature 3.14: Static Model Routing
- **Telemetry Enhancements:** (Refer to `feature_3_14_sf1/sf2_implementation_plan.md`).

### Feature 3.12: Token & Cost Telemetry
- **Streaming Telemetry Accuracy:** `generate_stream` currently estimates tokens from concatenated text. Exact token counts require adapter-level streaming support.
- **Adapter-level Duration:** Execution wall-clock timing includes tool execution. Native API-only timing from the provider is deferred.

### Feature 3.11: Auto Spec-Mention Detection
- **CLI Output:** Add mention summaries to the `sw review` Rich console output in a future polish pass.

### Feature 3.20a: Internal Layer Enforcement
- **Deferred Items:** (Refer to `feature_3_20a_sf5_implementation_plan.md` and `sf6`).

### Feature 3.05: Auto-discover Standards
- **Multi-stage Reviews:** Configurable multi-stage reviews and forcing re-evaluation of previous HITL decisions.

### Feature 3.27: Multi-Spec Pipeline Fan-Out
- **Deferred Enhancements:** (Refer to `feature_3.27_sf1_implementation_plan.md` and `sf2`).

---
*(Note: As we proceed, agents should explicitly append explicitly bounded Tech Debt into this document).*
