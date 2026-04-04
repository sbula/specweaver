# Implementation Plan: Feature 3.14 [SF-2: Artifact Tagging Engine]
- **Feature ID**: 3.14
- **Sub-Feature**: SF-2 — Artifact Tagging Engine
- **Design Document**: docs/proposals/roadmap/phase_3/feature_3_17/feature_3_17_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_17/feature_3_17_sf2_implementation_plan.md
- **Status**: APPROVED

## Goal Description
Implement SF-2 to orchestrate the injection of `# sw-artifact: <uuid>` lineage trackers into any artifact generated or reviewed by the system. This allows the CLI to track origin (Spec -> Plan -> Code) independent of Git.

## User Review Required
> [!CAUTION]
> This is a hardened, explicit plan designed for a zero-context agent handoff. There are zero unhandled assumptions or implicit module boundaries.

## Proposed Changes

---

### 1. `src/specweaver/loom/commons.py` [✅ COMPLETED IN CB-1]
> **Deviation Note**: Discovered and fixed a critical formatting edge case where upstream PromptBuilder uppercase language strings (e.g. `'PYTHON'`) would bypass formatting and swallow the UUID entirely. Applied `language.lower()` during extraction. 14 explicit Unit tests implemented across `tests/unit/loom/commons/test_lineage.py`.

To avoid regex bleed into the flow orchestrator, introduce a safe utility matching standard parsing methods.

#### [NEW] `commons.py`
- **Function**: `extract_artifact_uuid(content: str) -> str | None`
  - Uses regex `(?i)sw-artifact:\s*([a-f0-9\-]{36})` to find and extract the artifact ID.
- **Function**: `wrap_artifact_tag(artifact_id: str, language: str) -> str | None`
  - Returns `f"# sw-artifact: {artifact_id}"` for `python`, `yaml`, `toml`, `bash`, `ruby`.
  - Returns `f"<!-- sw-artifact: {artifact_id} -->"` for `markdown`, `html`, `xml`.
  - Returns `f"// sw-artifact: {artifact_id}"` for `javascript`, `typescript`, `java`, `go`, `rust`.
  - Returns `None` for `json`, `text`, or any unrecognised language (meaning no in-file tagging should occur).

#### [NEW] `tests/unit/loom/test_commons.py`
- Test the extraction and formatting rules.

---

### 2. `src/specweaver/flow/state.py` [✅ COMPLETED IN CB-1]
Allows upstream handler tasks to safely hand their UUIDs to the `PipelineRunner` without forcing the runner to re-read files from disk.

#### [MODIFY] `state.py`
- Locate `class StepResult(BaseModel)`.
- Add field: `artifact_uuid: str | None = None`. (Must use `| None = None` to stay strictly backward compatible).

---

### 3. `src/specweaver/llm/prompt_builder.py` [✅ COMPLETED IN CB-2]
> **Deviation Note**: The original plan mandated `llm/prompt_builder.py` import `wrap_artifact_tag` from `loom.commons.lineage`. However, `llm/context.yaml` explicitly forbids importing from the `loom/` DMZ. To resolve this architecture boundary violation, `lineage.py` and its tests were natively migrated to `src/specweaver/llm/lineage.py`.

Ensuring the LLM writes exact syntax without hallucinating JSON comments or breaking markdown headers.

#### [MODIFY] `prompt_builder.py`
- **Function**: `add_artifact_tagging(artifact_id: str, language: str) -> PromptBuilder`
  - Import `wrap_artifact_tag` from `specweaver.loom.commons`.
  - Let `tag = wrap_artifact_tag(artifact_id, language)`.
  - If `tag` is `None`, do nothing (return `self`).
  - If `tag` is present, `self.add_instructions(...)` with priority 0: `"You MUST include the exact string '{tag}' physically at the very top of your output file."`

---

### 4. `src/specweaver/flow/_generation.py` & `_draft.py`
Orchestrating the UUID extraction, parent linkage, minting, and logging logic during file creation.

#### [MODIFY] `_generation.py`
- Inside `GenerateCodeHandler.execute`:
  1. **Find `parent_id`**: Load `context.spec_path.read_text()` if the file exists, and run `extract_artifact_uuid()`. If it returns `None`, fallback to `parent_id = context.run_id` to ensure graph edges maintain connectivity to the active session.
  2. **Mint/Find `artifact_uuid`**: Load the target string `output_path` (if the file exists) and `extract_artifact_uuid()`. If present, reuse it. If missing, generate `str(uuid.uuid4())`.
  3. **Inject Prompt**: Call `config.prompt_builder.add_artifact_tagging(artifact_uuid, language)`.
  4. **Log Lineage Db**: Call `context.db.log_artifact_event` with `artifact_uuid`, `parent_id`, `context.run_id`, and `event_type` ("modified" or "created"). 
  5. **Propagate Status**: Ensure `StepResult(..., artifact_uuid=artifact_uuid)` is constructed.

#### [MODIFY] `_draft.py`
- Inside `DraftSpecHandler.execute`:
  - Follow the identical UUID extraction/minting logic as Code generation, but `parent_id` is simply `None` (specs are the root of the lineage tree).
  - Inject using `config.prompt_builder.add_artifact_tagging(artifact_uuid, "markdown")`.
  - Construct `StepResult(..., artifact_uuid=artifact_uuid)`.

#### [MODIFY] `_lint_fix.py`
For `LintFixHandler`:
- Extract any existing UUID from target code and inject it into `prompt_builder.add_artifact_tagging(artifact_uuid, language)` to ensure the LLM doesn't strip the UUID during structural refactoring.
- Log event with `event_type="lint_fixed"`.

## Verification Plan
1. **Automated Unit Tests**:
   - Run `pytest tests/unit/loom/test_commons.py` to assert regex behaves correctly across multi-line strings.
   - Run `pytest tests/unit/flow/test_handlers.py` to ensure `StepResult(artifact_uuid=...)` handles construction strictly without regressions.
2. **Architecture**:
   - `sw check --lineage` (in SF-3) will confirm these tags.
