# Implementation Plan: Project Metadata Injection

- **Feature ID**: feature_3_15
- **Design Document**: docs/proposals/design/phase_3/feature_3_15_design.md
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_15_implementation_plan.md
- **Status**: COMPLETED

## Phase 4: Merge Findings (HITL Review)

> [!NOTE]
> All Phase 4 audit questions resolved securely via HITL approval.

### 1. Architecture (CRITICAL)
- **Decision**: **Option B**. Build the DTO inside `RunContext.__init__` so it's globally available to all execution contexts (pipelines and single-shot commands). (Note: A full refactor to push all commands through `PipelineRunner` will be handled in Feature 3.13a).

### 2. Data Model & Serialization (HIGH)
- **Decision**: **Option B**. Create a strictly typed `PromptSafeConfig` in `llm/models.py` rather than a brittle dynamic dictionary.

### 5. LLM Interaction & JSON Structure (HIGH)
- **Decision**: **Option B**. Have `PromptBuilder` render the Pydantic DTO natively as a multi-line YAML structure inside the XML tag instead of a raw JSON string dump.

*(Other categories: Default actions approved as documented in the Phase 2 audit).*

---

## Proposed Changes

### `src/specweaver/llm/models.py`
#### [MODIFY] 
- **Action**: Add `PromptSafeConfig` Pydantic model containing `llm_model`, `llm_provider`, `validation_rules`.
- **Action**: Add `ProjectMetadata` Pydantic model containing `project_name`, `archetype`, `language_target`, `date_iso`, and `safe_config: PromptSafeConfig`.

### `src/specweaver/llm/prompt_builder.py`
#### [MODIFY] 
- **Action**: Add `add_project_metadata(self, metadata: ProjectMetadata | None) -> PromptBuilder`.
- **Logic**: Construct a YAML representation of the metadata and insert it securely inside `<project_metadata>` tags. Add it as a `_ContentBlock` with `priority=1`.
- **Handoff Directive 1**: Serialize visually as YAML using simple `f-string` concatenation or `json.dumps(dict, indent=2)` masquerading as YAML. Do NOT use external libraries like `PyYAML` or `ruamel.yaml` to avoid stream I/O buffer compatibility issues.

### `src/specweaver/flow/_base.py`
#### [MODIFY] Update `RunContext`
- **Action**: Update `RunContext.__init__` to automatically synthesize the `ProjectMetadata` DTO during creation. Use `platform.platform()` and `sys.version` wrapped in a `try/except` block to gracefully degrade if unavailable. Pass the configured subset from `SpecWeaverSettings` to `PromptSafeConfig`.
- **Handoff Directive 2**: Extract `archetype` securely by calling `specweaver.project.scaffold.load_context_yaml(project_path).archetype` if the file exists, with a safe fallback to `'generic'`.
- **Handoff Directive 3**: `language_target` must strictly default to the literal string `'Unknown Environment'` if `sys` or `platform` modules raise exceptions (do NOT use `None` as it violates the Pydantic schema).
- **Action**: Make `project_metadata: ProjectMetadata` an accessible property of `RunContext`.

### `src/specweaver/flow/*` (Handlers)
#### [MODIFY] `_review.py`, `_generation.py`, `_draft.py`, `constitution.py`, `planner.py`
- **Action**: Wherever `PromptBuilder` is instantiated, call `builder.add_project_metadata(context.project_metadata)` to inject the gathered context into the LLM.

## Verification
- Unit test coverage for the safe subset mapping (ensuring `api_key` can never be serialized).
- Execute `sw pipeline run` and verify DB traces contain the well-formed YAML inside the `<project_metadata>` block.
