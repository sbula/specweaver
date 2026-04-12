# Implementation Plan: Spec-to-Code Traceability [SF-3: Verification & CLI Tools]
- **Feature ID**: 3.14
- **Phase**: 3
- **Sub-Feature**: SF-3 — Verification & CLI Tools
- **Design Document**: docs/roadmap/phase_3/feature_3_17/feature_3_17_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-3
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_17/feature_3_17_sf3_implementation_plan.md
- **Status**: APPROVED

This plan completes the "Spec-to-Code Traceability" feature by adding CLI commands to verify and build lineage trees, and establishing DB schemas for tracking manual interventions (`model_id`).

## Proposed Changes

### Database Updates

#### [x] [MODIFY] src/specweaver/config/_schema.py
- Add `SCHEMA_V12` adding `ALTER TABLE artifact_events ADD COLUMN model_id TEXT NOT NULL DEFAULT 'unknown';`.
- Add `SCHEMA_V12` to `__all__` export list.

#### [x] [MODIFY] src/specweaver/config/database.py
- Import `SCHEMA_V12` from `specweaver.core.config._schema`.
- Append `(12, SCHEMA_V12, "model_id for artifact_events"),` to the `_MIGRATIONS` list.

#### [x] [MODIFY] src/specweaver/config/_db_lineage_mixin.py
- Update `log_artifact_event` function signature: `def log_artifact_event(self, artifact_id: str, parent_id: str | None, run_id: str, event_type: str, model_id: str) -> None:`
- Update the SQL `INSERT INTO artifact_events (artifact_id, parent_id, run_id, event_type, model_id, timestamp) VALUES (?, ?, ?, ?, ?, ?)` and its parameters tuple.

---

### Command Line Interace

#### [x] [NEW] src/specweaver/cli/lineage.py
- Create a new `typer.Typer(name="lineage")` app instance.
- Implement `@lineage_app.command("tree")` (or main callback for `sw lineage <file>` without subcommand):
    - Reads the `<file>` and extracts the UUID using:
      ```python
      for line in file.read_text().splitlines():
          if line.startswith("# sw-artifact: "):
              uuid = line.split(": ")[1].strip()
              break
      ```
    - The `target` argument can intelligently detect if it's already a UUID string vs a filepath.
    - Queries `db.get_artifact_history(uuid)`.
    - Recursively queries `db.get_artifact_history(parent_id)` to resolve ancestors up to the root.
    - Recursively queries `db.get_children(id)` to resolve descendent lineage branches.
    - Uses `rich.tree.Tree` to display the upward (parents) and downward (children) lineage interactively.
- Implement `@lineage_app.command("tag")`:
    - Takes `<file>` arg and `author: str = typer.Option("human", "--author")`.
    - Opens the target `.py` file. If there's an existing `# sw-artifact` tag, update the DB with a new manual edit event.
    - If no tag exists, inserts `# sw-artifact: <new_uuid>\n` either at the absolute top of the file, or immediately after a shebang if present.
    - Logs event to DB with `event_type='manual_tag'` and `model_id=author`.
- Implement a helper `check_lineage(src_dir: Path) -> list[str]`:
    - Operates strictly on the `src/` directory.
    - Uses `src_dir.rglob("*.py")` skipping `.tmp`, `.venv`, `__pycache__` to scan source files.
    - Checks if `"# sw-artifact:" in file.read_text()` for each file.
    - Returns a list of absolute filepaths that lack the tag string.

#### [x] [MODIFY] src/specweaver/cli/__init__.py
- Import `from specweaver.interfaces.cli import lineage`.

#### [x] [MODIFY] src/specweaver/cli/validation.py
- Add `lineage: bool = typer.Option(False, "--lineage", help="Run orphan lineage check instead of validation pipeline.")` to `def check(...)`.
- If `lineage` is true:
    - Ignore normal AST logic.
    - Call `specweaver.interfaces.cli.lineage.check_lineage(target/project_dir)`.
    - Print all files missing lineage tags in red. If there are any, `raise typer.Exit(code=1)`. Else print success and exit 0.

## Open Questions
- None. Phase 4 HITL Gate completed and all decisions merged.

## Verification Plan

### Automated Tests
- Unit tests for `check_lineage` helper in `tests/unit/cli/test_cli_lineage.py` Mocking `rglob` and file contents to assure missing tags are flagged.
- DB integration test verifying `model_id` correctly persists after `SCHEMA_V12`.
