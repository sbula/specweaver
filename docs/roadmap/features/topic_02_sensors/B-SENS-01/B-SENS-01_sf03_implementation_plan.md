# B-SENS-01 SF-03 — Verification & CLI Tools

**Status**: APPROVED · **Feature ID**: 3.14 · **Phase**: 3 · **Depends on**: SF-01, SF-02 ·
Design: [B-SENS-01_design.md](B-SENS-01_design.md) §Sub-features → SF-03

**FRs owned: FR-4, FR-5, FR-6.** Tracing a file's history, failing CI on untracked source, and
adopting a manual edit. Recorded 2026-08-17 under `specweaver-dev` §3.2c, from
`INT-US-15-SF01-MIG`.

FR-4's declared invocation is `sw lineage <file>`; the shipped command is `sw lineage tree
<file>`. Same mechanism, same output, same data source — wording drift, not a descope.

## Goal

CLI commands to verify and trace lineage, and a `model_id` column so manual interventions are
recorded.

## Changes

All `[x]` done.

**Database**

1. src/specweaver/config/_schema.py — `SCHEMA_V12`:
   `ALTER TABLE artifact_events ADD COLUMN model_id TEXT NOT NULL DEFAULT 'unknown';`; add
   `SCHEMA_V12` to `__all__`.
2. src/specweaver/config/database.py — import `SCHEMA_V12` from `specweaver.core.config._schema`;
   append `(12, SCHEMA_V12, "model_id for artifact_events"),` to `_MIGRATIONS`.
3. src/specweaver/config/_db_lineage_mixin.py —
   `def log_artifact_event(self, artifact_id: str, parent_id: str | None, run_id: str, event_type: str, model_id: str) -> None:`
   with `INSERT INTO artifact_events (artifact_id, parent_id, run_id, event_type, model_id, timestamp) VALUES (?, ?, ?, ?, ?, ?)`.

**Command line interface**

4. `[NEW]` src/specweaver/cli/lineage.py — `typer.Typer(name="lineage")`:
   - `@lineage_app.command("tree")` (or the main callback for `sw lineage <file>`):
     - reads `<file>` and extracts the UUID:
      ```python
      for line in file.read_text().splitlines():
          if line.startswith("# sw-artifact: "):
              uuid = line.split(": ")[1].strip()
              break
      ```
     - `target` may be a UUID string or a filepath — detected;
     - `db.get_artifact_history(uuid)`, then `db.get_artifact_history(parent_id)` recursively up to
       the root, and `db.get_children(id)` recursively down;
     - shows parents and children with `rich.tree.Tree`.
   - `@lineage_app.command("tag")` — `<file>` and `author: str = typer.Option("human", "--author")`:
     - opens the target `.py` file; an existing `# sw-artifact` tag → log a new manual edit event;
     - no tag → insert `# sw-artifact: <new_uuid>\n` at the top of the file, or right after a shebang;
     - logs `event_type='manual_tag'` and `model_id=author`.
   - `check_lineage(src_dir: Path) -> list[str]`:
     - only the `src/` directory; `src_dir.rglob("*.py")`, skipping `.tmp`, `.venv`, `__pycache__`;
     - a file passes if `"# sw-artifact:" in file.read_text()`;
     - returns absolute paths of files without the tag.
5. src/specweaver/cli/__init__.py — `from specweaver.interfaces.cli import lineage`.
6. src/specweaver/cli/validation.py — `def check(...)` gains
   `lineage: bool = typer.Option(False, "--lineage", help="Run orphan lineage check instead of validation pipeline.")`.
   When set: skip the AST logic, call `specweaver.interfaces.cli.lineage.check_lineage(target/project_dir)`,
   print missing files in red and `raise typer.Exit(code=1)` if any; else print success, exit 0.

## Tests

- `check_lineage` unit tests in `tests/unit/cli/test_cli_lineage.py`, mocking `rglob` and file
  contents, flag missing tags.
- DB integration test: `model_id` persists after `SCHEMA_V12`.

**Since moved** (noted 2026-09-25): `check_lineage` → `graph/lineage/scanner.py`; the CLI →
`graph/interfaces/cli.py`; tests → `tests/unit/graph/interfaces/test_cli_lineage.py`.
