# D-INTL-05 SF-01 — Project Metadata Injection

**Status**: COMPLETED · **FRs owned**: FR-1, FR-2, FR-3 · **Depends on**: none · Design:
[D-INTL-05_design.md](D-INTL-05_design.md) · Feature ID feature_3_15

## Goal

Every LLM prompt carries a `<project_metadata>` block built from one `ProjectMetadata` DTO per run,
with an allowlisted config that can never contain `api_key`.

## Changes

1. **`src/specweaver/llm/models.py`** [MODIFY]
   - `PromptSafeConfig` Pydantic model: `llm_model`, `llm_provider`, `validation_rules`.
   - `ProjectMetadata` Pydantic model: `project_name`, `archetype`, `language_target`, `date_iso`,
     `safe_config: PromptSafeConfig`.
2. **`src/specweaver/llm/prompt_builder.py`** [MODIFY] —
   `add_project_metadata(self, metadata: ProjectMetadata | None) -> PromptBuilder`: renders the
   metadata as YAML inside `<project_metadata>` tags, as a `_ContentBlock` with `priority=1`.
   - Handoff Directive 1: serialize as YAML with plain `f-string` concatenation or
     `json.dumps(dict, indent=2)` masquerading as YAML. Do NOT use `PyYAML` or `ruamel.yaml` (stream
     I/O buffer compatibility issues).
3. **`src/specweaver/flow/_base.py`** [MODIFY] `RunContext`
   - `RunContext.__init__` builds the `ProjectMetadata` DTO at creation: `platform.platform()` and
     `sys.version` inside `try/except` so it degrades if unavailable; the configured subset of
     `SpecWeaverSettings` goes into `PromptSafeConfig`.
   - Handoff Directive 2: `archetype` =
     `specweaver.workspace.project.scaffold.load_context_yaml(project_path).archetype` if the file
     exists, else `'generic'`.
   - Handoff Directive 3: `language_target` defaults to the literal `'Unknown Environment'` if `sys`
     or `platform` raise (never `None` — it violates the Pydantic schema).
   - `project_metadata: ProjectMetadata` is a property of `RunContext`.
4. **`src/specweaver/flow/*` (handlers)** [MODIFY] `_review.py`, `_generation.py`, `_draft.py`,
   `constitution.py`, `planner.py` — wherever `PromptBuilder` is built, call
   `builder.add_project_metadata(context.project_metadata)`.

## Tests

- Unit: the safe subset mapping — `api_key` can never be serialized.
- `sw pipeline run`: DB traces contain well-formed YAML inside the `<project_metadata>` block.

## Decisions (audit, HITL)

All audit questions resolved via HITL; other categories took the default actions of the audit.

| # | Area | Chosen | Why |
|---|---|---|---|
| 1 | Architecture (CRITICAL) | **Option B** — build the DTO in `RunContext.__init__` | Available to all execution contexts, pipelines and single-shot commands. Pushing all commands through `PipelineRunner` is Feature 3.13a. |
| 2 | Data model & serialization (HIGH) | **Option B** — typed `PromptSafeConfig` in `llm/models.py` | A dynamic dictionary is brittle |
| 5 | LLM interaction & JSON structure (HIGH) | **Option B** — `PromptBuilder` renders the DTO as multi-line YAML inside the XML tag | Not a raw JSON string dump |
