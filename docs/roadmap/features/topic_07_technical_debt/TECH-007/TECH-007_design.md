# Design: PromptBuilder Input Escaping & Pluggable Context Architecture

- **Feature ID**: TECH-007
- **Phase**: 1
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-007/TECH-007_design.md

## Feature Overview

Feature TECH-007 adds a pluggable context loading architecture and an injection-safe prompt escaping engine to the PromptBuilder. It solves the vulnerability to XML/HTML injection and the tight compile-time coupling between domain layers and the LLM infrastructure by introducing structured, duck-typed protocols (PromptContentSource) and systematic escaping strategies (XML entities, CDATA breakout mitigation, JSON). It interacts with PromptBuilder and LLM rendering layers, and does not touch core LLM orchestration or adapter runtime clients. Key constraints: zero tach/context.yaml architectural violations and maintaining 70%-90% test coverage.

## Research Findings

### Codebase Patterns
- Currently, `PromptBuilder` accepts strings and formats them directly using raw f-strings in `_prompt_render.py`. This is vulnerable to XML tag breakouts if untrusted content is passed.
- `assurance/graph/context.yaml` forbids `specweaver/llm`. Thus, domain models like `TopologyContext` cannot directly import a `PromptContentSource` interface if it is defined inside `specweaver.infrastructure.llm`.
- Python's `Protocol` is duck-typed, which means domain models can implement the required methods (e.g. returning string values for slot names or contents) without importing any classes or enums from `specweaver.infrastructure.llm`, ensuring zero `tach check` violation.
- Standard CDATA breakout sequence is `]]>`. Escaping replaces `]]>` with `]]]]><![CDATA[>`.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| standard library | Python 3.12 | xml.sax.saxutils, json | Stdlib |

### Blueprint References
- None.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Escaping Strategies | PromptBuilder | Support four escaping strategies: Raw, XML, CDATA (with split mitigation), and JSON. | Content blocks are sanitized against XML tag breakout. |
| FR-2 | Attribute Escaping | Render Engine | Escape all XML attributes (e.g., path, role, label) during prompt assembly. | Attributes cannot contain quotes or tag boundaries to break out of XML tag syntax. |
| FR-3 | Structural Protocol | PromptBuilder | Define a duck-typed structural protocol `PromptContentSource` with `get_prompt_content()` and `get_prompt_label()`. | Decouples domain layer models from LLM package imports. |
| FR-4 | Pluggable Context | PromptBuilder | Accept any object conforming to `PromptContentSource` and map it dynamically to content blocks. | Custom domain components can inject structured context without code duplication. |
| FR-5 | Backward Compatibility | PromptBuilder | Retain existing string-based helper methods (`add_file`, `add_topology`, `add_project_metadata`, etc.). | Pre-existing callers continue to function exactly as before. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Security | Untrusted input sources must be escaped before being rendered. |
| NFR-2 | Performance | Prompt compilation overhead must be < 1ms. |
| NFR-3 | Compatibility | Full backward compatibility for string-based calls. |
| NFR-4 | Architecture | Zero violations of `context.yaml` and `tach check` constraints. |
| NFR-5 | Testing | Maintain 70% to 90% test coverage of modified/added code files. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Python | 3.12 | stdlib (json, xml) | Yes | Part of base system. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Structural Protocol | Domain models in `assurance/` cannot import `llm` due to context bounds. Duck-typed Python Protocols enable typing without imports. | No |
| AD-2 | Block-Time Escaping | Escaping inputs when they are added ensures that token budget estimators calculate token counts on the actual escaped text. | No |
| AD-3 | XML Attribute Escaping | Tag breakouts can occur through attribute strings if they contain unescaped quotes. Systematic attribute escaping is mandatory. | No |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Pluggable Contexts | Guide on how to write custom context providers for LLM prompts | ✅ Written |

## Sub-Feature Breakdown

### SF-1: Injection-Safe Escaping Engine & XML Attribute Escaping
- **Scope**: Implement the four escaping strategies (Raw, XML, CDATA with split mitigation, JSON) and XML attribute escaping.
- **FRs**: [FR-1, FR-2]
- **Inputs**: Raw input text strings, attribute keys/values.
- **Outputs**: Safe escaped strings.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-007/TECH-007_sf1_implementation_plan.md

### SF-2: Pluggable Context Architecture (Structural Protocol)
- **Scope**: Define the `PromptContentSource` protocol and support adding arbitrary sources to `PromptBuilder`.
- **FRs**: [FR-3, FR-4, FR-5]
- **Inputs**: Any object structurally conforming to `PromptContentSource`.
- **Outputs**: Adapted blocks inside `PromptBuilder`.
- **Depends on**: SF-1
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-007/TECH-007_sf2_implementation_plan.md

## Execution Order

1. SF-1: Escaping engine and attribute escaping (fundamental parser safety).
2. SF-2: Pluggable Context and adapter integration.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Escaping Engine | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Pluggable Contexts | SF-1 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: Both SF-1 and SF-2 are fully implemented, verified, and committed. All quality gates (linting, types, 88%+ test coverage, zero new tach violations) have passed.
**Next step**: Proceed with topic-level technical debt cleanup or feature tasks.
