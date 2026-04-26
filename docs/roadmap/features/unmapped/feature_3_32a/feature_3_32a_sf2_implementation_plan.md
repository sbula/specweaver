# Implementation Plan: Context Condensation Skeletons (SF-2)

> **Status:** ✅ Completed

## Goal Description

Implement AST Skeletons for `PromptBuilder` to vastly reduce token costs when injecting context dependencies into the context window. This achieves maximum performance optimization without sacrificing accuracy or structural context.

This will be accomplished by integrating the `workspace.parsers` AST extractors directly into `PromptBuilder` as a fallback mechanism. We will add a `skeleton: bool` option to both `add_file` and `add_mentioned_files` (which will default to `True` for mentioned files, as they act purely as contextual boundaries rather than direct editing targets).

## User Review Required

> [!NOTE]
> The design leverages lazy imports within `PromptBuilder` to dynamically resolve language-specific AST tools (`workspace.parsers`). If any file has invalid syntax or tree-sitter failures, it safely catches `CodeStructureError` or `Exception` and gracefully falls back to appending the raw contiguous file contents, guaranteeing no data loss during generation.

## Proposed Changes

### Tooling & Extractors

#### [MODIFY] [prompt_builder.py](file:///c:/development/pitbula/specweaver/src/specweaver/infrastructure/llm/prompt_builder.py)
- **Signature Updates**:
  - Add `skeleton: bool = False` to `add_file()`.
  - Add `skeleton: bool = True` to `add_mentioned_files()`.
- **Skeleton Condensation**: Add a private `_extract_skeleton(path: Path, content: str) -> str` method which acts as a pure logic boundary resolver.
  - Matches extensions to instantiating `PythonCodeStructure`, `TypeScriptCodeStructure`, `JavaCodeStructure`, `KotlinCodeStructure`, and `RustCodeStructure`.
  - Executes `.extract_skeleton(content)` and safely catches any exceptions to fallback to full text.
- **Integration**: Apply `self._extract_skeleton(path, content)` during read processes if `skeleton` is evaluated as `True`.

### Verification & Testing

#### [MODIFY] [test_prompt_builder.py](file:///c:/development/pitbula/specweaver/tests/unit/infrastructure/llm/test_prompt_builder.py)
- **Skeleton Truncation Support**: Add unit tests verifying `PromptBuilder.add_file(..., skeleton=True)` successfully calls the underlying parser and returns condensed output containing `" ... "` bounds instead of full implementations.
- **Mentioned File Defaulting**: Verify that `add_mentioned_files()` properly defaults to AST compression for external files without affecting priority truncation models.

## Open Questions

None at this time. The plan provides the exact performance ROI mapped out in the feature description while strictly complying with `tach` architectural bounds (as `workspace.parsers` is `pure-logic`).

> **Implementation Deviation (Refactoring)**: During the final code quality phase of `/pre-commit`, `_extract_skeleton` was migrated out of `prompt_builder.py` and into the isolated `_skeleton.py` module to physically comply with Ruff bounds restricting Class size > 600 lines. The equivalent testing chunks were similarly relocated to independent modules.

## Verification Plan

### Automated Tests
- Run `pytest tests/unit/infrastructure/llm/ -v` to ensure skeleton logic respects `PromptBuilder` state.
- Will execute a full `/pre-commit` to guarantee no downstream models or CLI implementations break due to missing API signatures or broken boundaries.

### Architectural Validation
- Validate using `tach check` to ensure no `loom` boundary leaks when the LLM builder references AST parsers directly.
