# Design: Polyglot AST Skeleton Extractor & Context Ledger

- **Feature ID**: 3.22
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/proposals/roadmap/phase_3/feature_3_22/feature_3_22_design.md

## Feature Overview

Feature 3.22 solves the critical problem of LLM "Context Window Bloat" and API cost-explosion during long multi-turn agent sessions. Instead of returning a dangerous `[304 Not Modified]` that degrades the agent's attention span, the system provides an advanced, polyglot **CodeStructureTool**: providing `read_file_structure(file)` and `read_symbol(file, symbol)`. 

These intents utilize `tree-sitter` and a consolidated `loom/commons/language/` registry to extract just the signatures/docstrings of a file, or the specific implementation of a requested class/function. It completely offloads syntax parsing to language-specific `.scm` node queries running in the isolated `Loom` Engine Sandbox via Atoms. Furthermore, a follow-up feature (SF-2) introduces `write_symbol` to allow surgical AST body patching.

## Discarded Concepts (The "304" Problem)

**Original Idea:** The feature was initially proposed as a SQLite-backed "Context Ledger" that would track files an agent had already read during a session. If the agent requested the file again, it would intercept the read and return `[304 Not Modified]` to save API tokens and prevent bloated prompts.

**The Problem:** LLM transformers suffer from extreme attention degradation ("Lost in the Middle") in long contexts. Even though a file is technically loaded in the message history from 20 turns ago, the LLM physically "forgets" or loses attention to those weights. When an agent loop asks to reread a file, it is actually successfully attempting to **refresh its attention mechanism**. 

**Why it was discarded:** By returning `[304 Not Modified]` and blocking the reread, the system would maliciously force the agent to rely on fading memory, triggering catastrophic syntax hallucinations when generating code. The AST Skeleton pivot was chosen because sending only the interface safely refreshes the attention weights while permanently solving the token cost bloat problem.

## Research Findings

### Codebase Patterns
SpecWeaver's domain-driven architecture demands a strict separation between Pure Logic and I/O.
1. **Loom Commons Language Registry:** `src/specweaver/loom/commons/language/<lang>/` is the single source of truth for both QA testing binaries and AST C-binary parsing.
2. **Dependency Injection:** Pure logic layers (like `drift_detector`) must not run tree-sitter themselves. The `flow` orchestrator must use `AstAtom` to generate AST structures and pass them via Dependency Injection to pure logic nodes.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| `tree-sitter` | Latest | `Parser`, `Language`, `.scm` queries | Already in `pyproject.toml` |
| `tree-sitter-<lang>` | Latest | Pre-compiled language grammars | Already in `pyproject.toml` |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Skeleton Abstraction | CodeStructureTool | reads a file structure | The system SHALL detect the language, route to the correct parser, execute the Tree-Sitter tags query, and return ONLY the file's imports, class/method signatures, and docstrings. |
| FR-2 | Symbol Extraction | CodeStructureTool | reads a specific symbol | The system SHALL return the entire implementation payload of exclusively the requested symbol (class/function) from the target file. |
| FR-3 | Polyglot Registry | Flow Engine | centralizes language I/O | The system SHALL unify test-running (`runner.py`) and AST execution (`ast_parser.py`) exclusively within `loom/commons/language/<name>`. |
| FR-4 | Query Fallback | CodeStructureTool | encounters unsupported language | If the file's language has no registered extractor plugin, the system SHALL throw an explicit error reminding the LLM to use `read_file` instead. |
| FR-5 | Symbol Replacement | CodeStructureTool | writes into a specific symbol | *(SF-2)* The system SHALL safely replace the body of a specific AST symbol with new code logic without relying on regex or fragile byte matching. |
| FR-6 | Symbol Listing | CodeStructureTool | lists available symbols | The system SHALL return a flat array mapping of all targetable symbols within a file, filterable by a designated visibility constraint (e.g. `['public']`). |
| FR-7 | Symbol Body Extraction | CodeStructureTool | reads only the inner block | The system SHALL selectively return only the internal execution logic block (`{...}`) of a symbol without extracting its decorators or external class wrappers. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Latency | AST Extraction must occur locally via `tree-sitter` with a P95 latency of `<50ms` per file to prevent agent blocking. |
| NFR-2 | Reliability | The Tree-sitter abstraction MUST NOT fail the pipeline if a file contains minor syntax errors (Tree-sitter error-recovery must remain enabled). |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Dedicated CodeStructureTool | Prevents semantic overlap in the LLM's brain between raw filesystem operations and contextual code investigation. | No |
| AD-2 | Deprecate `[304 Not Modified]` | Resolves "Lost in the Middle" contextual bloat via Astro-Skeleton structure instead of dangerous caching. | No |
| AD-3 | Loom Commons Dependency Injection | Tree-sitter C-binding execution must live in `loom/commons/` and be Dependency-Injected into pure logic layers to satisfy Tach layer boundary constraints. | No |

## Sub-Feature Breakdown

### SF-1: Polyglot AST Extractor (CodeStructureTool: Read Side)
- **Scope**: Create the `loom/commons/language/` registry. Build the `AstAtom` component and provide `read_file_structure` and `read_symbol` intents via the agent-facing `CodeStructureTool`.
- **FRs**: [FR-1, FR-2, FR-3, FR-4]
- **Depends on**: none

### SF-2: AST Symbol Writer (CodeStructureTool: Write Side)
- **Scope**: Extend the AST integration to support surgically replacing symbol bodies (`write_symbol`) leveraging the parser established in SF-1.
- **FRs**: [FR-5]
- **Depends on**: SF-1

## Execution Order

1. SF-1
2. SF-2

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Polyglot AST Extractor (Read Side) | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | AST Symbol Writer (Write Side) | SF-1 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Implementation Plan for SF-2 COMPLETE and APPROVED.
**Next step**: Run `/dev` to build SF-2 according to `feature_3_22_sf2_implementation_plan.md`.
