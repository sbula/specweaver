# Implementation Plan: PromptBuilder Input Escaping & Pluggable Context Architecture [SF-1: Injection-Safe Escaping Engine & XML Attribute Escaping]
- **Feature ID**: TECH-007
- **Sub-Feature**: SF-1 — Injection-Safe Escaping Engine & XML Attribute Escaping
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-007/TECH-007_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-007/TECH-007_sf1_implementation_plan.md
- **Status**: APPROVED

---

## 1. Goal & Overview
Implement systematic, injection-safe escaping strategies in `PromptBuilder` to sanitize untrusted input context (files, external data) and prevent XML/HTML tag breakouts.
Additionally, implement robust XML attribute escaping for all generated block metadata (such as path, role, label) in `_prompt_render.py` to prevent quotes/tags breakouts in attribute values.

---

## 2. Proposed Changes

### [Component: LLM Infrastructure]

#### [NEW] [escaping.py](file:///c:/development/pitbula/specweaver/src/specweaver/infrastructure/llm/escaping.py)
Create a dedicated escaping module containing escaping strategies and helper functions.

- Define `EscapingStrategy` enum (RAW, XML, CDATA, JSON).
- Implement `escape_xml_text(text: str) -> str` (escapes `&`, `<`, `>`).
- Implement `escape_xml_attribute(value: str) -> str` (escapes `&`, `<`, `>`, `"`, `'`).
- Implement `escape_cdata(text: str) -> str` (replaces `]]>` with `]]]]><![CDATA[>` and wraps in `<![CDATA[` and `]]>`).
- Implement `escape_json(text: str) -> str` (serializes text via `json.dumps`).
- Implement a dispatch function `apply_escaping(text: str, strategy: EscapingStrategy) -> str`.

#### [MODIFY] [prompt_builder.py](file:///c:/development/pitbula/specweaver/src/specweaver/infrastructure/llm/prompt_builder.py)
- Import `EscapingStrategy` and escaping utilities from `escaping.py`.
- Add an optional `escaping` parameter (type `EscapingStrategy | str | None`) to all content adding methods:
  - `add_file` (defaults to `EscapingStrategy.CDATA` or `XML` - to be confirmed in Phase 4).
  - `add_context` (defaults to `EscapingStrategy.CDATA`).
  - `add_instructions` (defaults to `EscapingStrategy.RAW`).
  - `add_reminder` (defaults to `EscapingStrategy.RAW`).
  - `add_constitution` (defaults to `EscapingStrategy.RAW`).
  - `add_standards` (defaults to `EscapingStrategy.RAW`).
  - `add_plan` (defaults to `EscapingStrategy.RAW`).
- Modify `_ContentBlock` to store the applied `escaping` strategy.
- Modify the truncation logic: Ensure that truncation occurs on the raw text *before* escaping is applied, so that the truncation marker `[truncated]` is safely encapsulated.

#### [MODIFY] [_prompt_render.py](file:///c:/development/pitbula/specweaver/src/specweaver/infrastructure/llm/_prompt_render.py)
- Import `escape_xml_attribute` and `apply_escaping`.
- Update all block rendering functions (`render_files`, `_render_mentioned`, `_render_contexts`, etc.) to:
  1. Escape all XML attribute values (e.g., `path`, `language`, `role`, `label`) before embedding them in output strings.
  2. Apply the block's chosen escaping strategy on its text payload.

---

## 3. Mechanism vs. Constraint Matrix

| Proposed File | I/O & State | Execution | LLM/AI | Dependencies | Domain Cohesion | Verdict |
|---------------|-------------|-----------|--------|--------------|-----------------|---------|
| `escaping.py` | None | None | None | Standard library `enum`, `json` | LLM utilities | COMPLIANT |
| `prompt_builder.py` | None | None | None | `escaping.py` | LLM prompt building | COMPLIANT |
| `_prompt_render.py` | None | None | None | `escaping.py` | LLM prompt rendering | COMPLIANT |

---

## 4. Verification Plan

### Automated Tests
1. **Unit tests for `escaping.py`**:
   - Verify `escape_xml_text` properly translates `&`, `<`, `>`.
   - Verify `escape_xml_attribute` properly translates `&`, `<`, `>`, `"`, `'`.
   - Verify `escape_cdata` wraps content and handles the `]]>` breakout pattern correctly.
   - Verify `escape_json` outputs valid JSON strings via `json.loads` round-trip.
2. **Unit tests for `PromptBuilder`**:
   - Verify that adding blocks with different escaping strategies renders them in the expected escaped format.
   - Verify that default strategies are applied if no parameter is passed.
   - Verify that attribute escaping works on invalid attributes (e.g. quotes or tags in `path` or `label`).
   - Verify that truncation of CDATA blocks wraps the truncated text and the truncation marker within the CDATA block.
3. **Run existing and new test suites**:
   - `pytest tests/unit/infrastructure/llm/` to ensure no regressions are introduced.

### Manual Verification
- Compile test prompts using `PromptBuilder` and print them to verify correct XML nesting and entity translation under extreme input values.

---

## 5. Red/Blue Team Architectural & Security Analysis

During design auditing, the following key threats and mitigation patterns were analyzed and factored into the plan:

### 5.1 Threat: CDATA Nesting & Breakout Injection (Security)
*   **Attack Vector**: An input source containing `]]>` sequence closes the CDATA block early and allows custom XML instructions injection.
*   **Mitigation**: The `escape_cdata` function replaces all `]]>` with `]]]]><![CDATA[>`.

### 5.2 Threat: Escaped Text Truncation Corruption (Syntax & Structural Integrity)
*   **Attack Vector**: Slicing the final formatted CDATA or JSON string in `_apply_truncation()` strips the trailing tags/quotes.
*   **Mitigation**: Perform truncation on the raw text payload, append `\n[truncated]` to the raw string if needed, and apply escaping afterwards. This guarantees that CDATA blocks and JSON quotes are always well-formed.

### 5.3 Threat: XML Attribute Injection (Security)
*   **Attack Vector**: File paths or labels containing double quotes break early out of attribute quotes.
*   **Mitigation**: All XML attributes rendered in `_prompt_render.py` must pass through `escape_xml_attribute` to encode quotes and tag boundaries.

### 5.4 Threat: Module Decoupling (Hexagonal Architecture)
*   **Attack Vector**: Exposing infrastructure enum `EscapingStrategy` to domain layers violates layer isolation.
*   **Mitigation**: Domain layers will pass simple primitive strings (`"cdata"`, `"xml"`) to API signatures, completely decoupling the domain layers from `llm` infrastructure.

