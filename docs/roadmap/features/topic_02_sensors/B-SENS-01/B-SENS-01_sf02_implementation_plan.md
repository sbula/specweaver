# B-SENS-01 SF-02 — Artifact Tagging Engine

**Status**: APPROVED · **Feature ID**: 3.14 · **Depends on**: SF-01 ·
Design: [B-SENS-01_design.md](B-SENS-01_design.md) §Sub-features → SF-02

**FRs owned: FR-2.** Tag injection into every generated artifact. Recorded 2026-08-17 under
`specweaver-dev` §3.2c, from `INT-US-15-SF01-MIG`. Its mutant fails 15 files across three
tiers — the widest in the migration, which is what "every generated file" ought to look like.

## Goal

Every artifact the system generates or reviews carries a `# sw-artifact: <uuid>` tag, so the CLI
can trace its origin (Spec -> Plan -> Code) independent of Git.

## Changes

1. **Tag helpers** (CB-1, done) · `src/specweaver/llm/lineage.py` — keeps regex out of the flow
   orchestrator:
   - `extract_artifact_uuid(content: str) -> str | None` — regex
     `(?i)sw-artifact:\s*([a-f0-9\-]{36})`.
   - `wrap_artifact_tag(artifact_id: str, language: str) -> str | None`, on `language.lower()`
     (upstream PromptBuilder passes uppercase strings like `'PYTHON'`):
     - `f"# sw-artifact: {artifact_id}"` for `python`, `yaml`, `toml`, `bash`, `ruby`;
     - `f"<!-- sw-artifact: {artifact_id} -->"` for `markdown`, `html`, `xml`;
     - `f"// sw-artifact: {artifact_id}"` for `javascript`, `typescript`, `java`, `go`, `rust`;
     - `None` for `json`, `text` or any unrecognised language — no in-file tag.

   Planned as `src/specweaver/loom/commons.py` (`loom.commons.lineage`); moved to `llm` because
   `llm/context.yaml` forbids importing the `loom/` DMZ.
2. **Step result** (CB-1, done) · `src/specweaver/flow/state.py` — `class StepResult(BaseModel)` gains
   `artifact_uuid: str | None = None` (backward compatible). Handlers hand their UUID to the
   `PipelineRunner` without it re-reading files from disk.
3. **Prompt** (CB-2, done) · `src/specweaver/llm/prompt_builder.py` —
   `add_artifact_tagging(artifact_id: str, language: str) -> PromptBuilder`: `tag = wrap_artifact_tag(artifact_id, language)`;
   `None` → return `self`; else `self.add_instructions(...)` at priority 0:
   `"You MUST include the exact string '{tag}' physically at the very top of your output file."`
   The LLM writes exact comment syntax — no JSON comments, no broken markdown headers.
4. **Code generation** · `src/specweaver/flow/_generation.py` — in `GenerateCodeHandler.execute`:
   1. **`parent_id`**: `extract_artifact_uuid()` on `context.spec_path.read_text()` if the file
      exists; if `None`, `parent_id = context.run_id`, so the edge stays attached to the session.
   2. **`artifact_uuid`**: reuse the UUID in the existing `output_path` file; else `str(uuid.uuid4())`.
   3. `config.prompt_builder.add_artifact_tagging(artifact_uuid, language)`.
   4. `context.db.log_artifact_event` with `artifact_uuid`, `parent_id`, `context.run_id`, `event_type`
      ("modified" or "created").
   5. Return `StepResult(..., artifact_uuid=artifact_uuid)`.
5. **Spec drafting** · `_draft.py` — `DraftSpecHandler.execute`: same extraction/minting, but
   `parent_id` is `None` (specs are the root); `config.prompt_builder.add_artifact_tagging(artifact_uuid, "markdown")`;
   `StepResult(..., artifact_uuid=artifact_uuid)`.
6. **Lint fix** · `_lint_fix.py` — `LintFixHandler` passes the existing UUID from the target code to
   `prompt_builder.add_artifact_tagging(artifact_uuid, language)` so refactoring keeps it; logs
   `event_type="lint_fixed"`.

## Tests

- `pytest tests/unit/loom/test_commons.py` — extraction and formatting rules, multi-line strings.
  (As built: 14 unit tests in `tests/unit/loom/commons/test_lineage.py`, moved with the module.)
- `pytest tests/unit/flow/test_handlers.py` — `StepResult(artifact_uuid=...)` without regressions.
- `sw check --lineage` (SF-03) confirms the tags.

**Since moved** (noted 2026-09-25): the helpers are in `commons/lineage.py`; the plan's import
`specweaver.core.loom.commons` is gone.
