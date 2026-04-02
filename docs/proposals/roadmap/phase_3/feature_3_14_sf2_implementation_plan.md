# Implementation Plan: Feature 3.12b [SF-2: CLI Routing Commands]
- **Feature ID**: feature_3_14
- **Sub-Feature**: SF-2 — CLI Routing Commands
- **Design Document**: docs/proposals/design/phase_3/feature_3_14_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_14_sf2_implementation_plan.md
- **Status**: COMPLETE

---

## Overview

SF-2 adds three CLI subcommands under `sw config routing` that allow users to
manage per-task-type LLM routing entries for the active project. This is the
user-facing surface for the routing engine built in SF-1.

The commands are:
- `sw config routing set <task_type> <profile_name>` — link a task type to a profile
- `sw config routing show` — display routing table
- `sw config routing clear [<task_type>]` — remove routing entries

**FR covered**: FR-4 (CLI surface).

**Dependencies**: SF-1 (complete) — provides `link_project_profile()`,
`unlink_project_profile()`, `get_project_routing_entries()`,
`get_llm_profile_by_name()` DB methods.

> [!IMPORTANT]
> **Non-interactive mandate**: All three commands are fully non-interactive. No
> `typer.confirm()` prompts, no "Are you sure?" gates. This is critical for
> CI/CD pipelines and autonomous agent workflows.

---

## Proposed Changes

### DB Layer

#### [MODIFY] [_db_llm_mixin.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/_db_llm_mixin.py)

Add one new method for orphan-safe bulk clearing:

```python
def clear_all_project_routing(self, project_name: str) -> int:
    """Delete ALL per-task routing entries for a project.

    Unlike iterating ``get_project_routing_entries()`` (which JOINs on
    ``llm_profiles`` and misses orphaned links), this directly deletes
    all rows whose role starts with ``"task:"``.

    Returns the number of rows deleted.
    """
    with self.connect() as conn:
        cursor = conn.execute(
            "DELETE FROM project_llm_links "
            "WHERE project_name = ? AND role LIKE 'task:%'",
            (project_name,),
        )
        return cursor.rowcount
```

> [!NOTE]
> This method exists because `get_project_routing_entries()` uses a JOIN
> on `llm_profiles`. If a profile is deleted while a `task:` link still exists,
> the JOIN misses the orphan. This method guarantees all `task:*` rows are
> cleared regardless of profile existence.

---

### CLI Layer

#### [MODIFY] [config.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli/config.py)

Add a `routing_app` Typer sub-application with three subcommands. Register it
on the existing `config_app` as `config_app.add_typer(routing_app, name="routing")`.

This follows the established pattern where `config_app` is itself a sub-app of
the root `app` (line 23: `_core.app.add_typer(config_app, name="config")`).

##### Shared: task type validation via `TaskType` enum

```python
from specweaver.llm.models import TaskType

# Derive valid values from the single source of truth (TaskType enum).
# Exclude UNKNOWN — it is not user-configurable.
_ROUTABLE_TASK_TYPES: frozenset[str] = frozenset(
    t.value for t in TaskType if t != TaskType.UNKNOWN
)
```

> [!NOTE]
> **Single source of truth** — valid task types are derived from the `TaskType`
> enum at import time, not hardcoded. If a new `TaskType` member is added,
> routing commands automatically accept it. The `cli/` module's `context.yaml`
> already declares `consumes: specweaver/llm`, so this import is
> architecturally valid.

##### Command: `routing set`

```python
routing_app = typer.Typer(
    name="routing",
    help="Manage per-task-type LLM model routing.",
    no_args_is_help=True,
)
config_app.add_typer(routing_app, name="routing")


@routing_app.command("set")
def routing_set(
    task_type: str = typer.Argument(
        help=f"Task type ({', '.join(sorted(_ROUTABLE_TASK_TYPES))}).",
    ),
    profile_name: str = typer.Argument(help="Name of an existing LLM profile."),
) -> None:
    """Link a task type to a specific LLM profile for routing."""
    name = _core._require_active_project()
    task_lower = task_type.lower()

    if task_lower not in _ROUTABLE_TASK_TYPES:
        _core.console.print(
            f"[red]Error:[/red] Invalid task type '{task_type}'. "
            f"Valid: {', '.join(sorted(_ROUTABLE_TASK_TYPES))}",
        )
        raise typer.Exit(code=1)

    db = _core.get_db()
    profile = db.get_llm_profile_by_name(profile_name)
    if profile is None:
        _core.console.print(
            f"[red]Error:[/red] Profile '{profile_name}' not found. "
            "Use 'sw config set-provider' to create one first.",
        )
        raise typer.Exit(code=1)

    try:
        db.link_project_profile(name, f"task:{task_lower}", profile["id"])
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _core.console.print(
        f"[green]✓[/green] Routing: [bold]{task_lower}[/bold] → "
        f"profile [bold]{profile_name}[/bold] "
        f"(provider={profile['provider']}, model={profile['model']}).",
    )
```

> [!WARNING]
> The `try/except ValueError` around `link_project_profile` handles the TOCTOU
> race between `_require_active_project()` and the actual DB write. Without it,
> a project deleted between the two calls would crash with an unhandled traceback.

##### Command: `routing show`

```python
@routing_app.command("show")
def routing_show() -> None:
    """Show the routing table for the active project."""
    name = _core._require_active_project()
    db = _core.get_db()
    entries = db.get_project_routing_entries(name)

    if not entries:
        _core.console.print(
            "[dim]No routing configured. All tasks use the default profile.[/dim]",
        )
        return

    table = Table(title=f"Model Routing ({name})")
    table.add_column("Task Type", style="cyan")
    table.add_column("Profile")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Temperature", justify="right")

    for entry in entries:
        profile = db.get_llm_profile(entry["profile_id"])
        if profile:
            table.add_row(
                str(entry["task_type"]),
                str(entry["profile_name"]),
                str(profile["provider"]),
                str(profile["model"]),
                str(profile["temperature"]),
            )
        else:
            # Orphaned link — profile was deleted but link remains
            table.add_row(
                str(entry["task_type"]),
                str(entry["profile_name"]),
                "[red][deleted][/red]",
                "[red][deleted][/red]",
                "[dim]—[/dim]",
            )
    _core.console.print(table)
```

> [!NOTE]
> When a linked profile no longer exists, the row is displayed with `[deleted]`
> markers instead of being silently dropped. This lets users discover stale
> entries and clean them up with `routing clear`.

##### Command: `routing clear`

```python
@routing_app.command("clear")
def routing_clear(
    task_type: str | None = typer.Argument(
        None, help="Task type to clear (omit to clear all).",
    ),
) -> None:
    """Clear routing entries for the active project."""
    name = _core._require_active_project()
    db = _core.get_db()

    if task_type is not None:
        task_lower = task_type.lower()
        if task_lower not in _ROUTABLE_TASK_TYPES:
            _core.console.print(
                f"[red]Error:[/red] Invalid task type '{task_type}'. "
                f"Valid: {', '.join(sorted(_ROUTABLE_TASK_TYPES))}",
            )
            raise typer.Exit(code=1)

        removed = db.unlink_project_profile(name, f"task:{task_lower}")
        if removed:
            _core.console.print(
                f"[green]✓[/green] Cleared routing for [bold]{task_lower}[/bold].",
            )
        else:
            _core.console.print(
                f"[dim]No routing entry for '{task_lower}' to clear.[/dim]",
            )
    else:
        # Use direct SQL delete — catches orphaned links that JOIN-based
        # get_project_routing_entries() would miss.
        count = db.clear_all_project_routing(name)
        if count:
            _core.console.print(
                f"[green]✓[/green] Cleared all {count} routing entries.",
            )
        else:
            _core.console.print("[dim]No routing entries to clear.[/dim]")
```

---

### Documentation

#### [MODIFY] [README.md](file:///c:/development/pitbula/specweaver/README.md)

Add a new "Model Routing" section after "LLM Telemetry" in the CLI Commands area:

```markdown
### Model Routing

| Command | Description |
|---|---|
| `sw config routing set <task_type> <profile>` | Route a task type to a specific LLM profile |
| `sw config routing show` | Show the routing table for the active project |
| `sw config routing clear [<task_type>]` | Clear routing entries (one or all) |
```

Also add a bullet to the Features section:
```markdown
- **Config-driven model routing** — Map task types (`implement`, `review`, etc.) to specific LLM profiles for per-task model/temperature control
```

---

### Test Plan

#### [NEW] [test_config_routing.py](file:///c:/development/pitbula/specweaver/tests/unit/cli/test_config_routing.py)

New test file following the established `test_cli_config.py` pattern:
`CliRunner` + mocked DB via `monkeypatch.setattr("specweaver.cli._core.get_db", ...)`.

#### [NEW] [test_db_clear_routing.py](file:///c:/development/pitbula/specweaver/tests/unit/config/test_db_clear_routing.py)

Unit test for the new `clear_all_project_routing()` DB method.

##### Test Cases

```python
# --- tests/unit/config/test_db_clear_routing.py ---

class TestClearAllProjectRouting:
    """Test Database.clear_all_project_routing()."""

    def test_clears_task_entries(self, tmp_db) -> None:
        """Deletes all task: routing entries, returns count."""

    def test_ignores_non_task_entries(self, tmp_db) -> None:
        """Non-task: role entries (e.g. 'draft') are not deleted."""

    def test_clears_orphaned_links(self, tmp_db) -> None:
        """Deletes task: links even when the profile has been deleted."""

    def test_returns_zero_when_empty(self, tmp_db) -> None:
        """Returns 0 when no routing entries exist."""


# --- tests/unit/cli/test_config_routing.py ---

class TestRoutingSet:
    """Test sw config routing set."""

    def test_set_happy_path(self, _mock_db) -> None:
        """routing set → links task type to profile, prints confirmation."""
        # Setup: create project, create a named profile
        # Act: invoke routing set implement <profile_name>
        # Assert: exit 0, confirmation in output, DB entry exists

    def test_set_invalid_task_type(self, _mock_db) -> None:
        """routing set with bad task type → exit 1."""
        # Act: invoke routing set "badtype" "some-profile"
        # Assert: exit 1, "Invalid task type" in output

    def test_set_unknown_profile(self, _mock_db) -> None:
        """routing set with nonexistent profile → exit 1."""
        # Act: invoke routing set implement "no-such-profile"
        # Assert: exit 1, "not found" in output

    def test_set_no_active_project(self, _mock_db) -> None:
        """routing set without active project → exit 1."""
        # Do NOT create a project
        # Assert: exit 1, "No active project" in output

    def test_set_overwrites_existing(self, _mock_db) -> None:
        """routing set twice for same task type → second profile wins."""
        # Set implement → profile-a, then implement → profile-b
        # Assert: routing show shows only profile-b for implement


class TestRoutingShow:
    """Test sw config routing show."""

    def test_show_empty(self, _mock_db) -> None:
        """routing show with no entries → default message."""
        # Assert: "No routing configured" in output

    def test_show_with_entries(self, _mock_db) -> None:
        """routing show after set → displays table."""
        # Set implement → profile
        # Assert: task type, profile name, provider, model in output

    def test_show_deleted_profile(self, _mock_db) -> None:
        """routing show with orphaned link → shows [deleted] markers."""
        # Set implement → profile, delete the profile from DB
        # Assert: "[deleted]" in output


class TestRoutingClear:
    """Test sw config routing clear."""

    def test_clear_specific_entry(self, _mock_db) -> None:
        """routing clear <task_type> → clears only that entry."""
        # Set implement + review, clear implement
        # Assert: implement cleared, review still exists

    def test_clear_specific_nonexistent(self, _mock_db) -> None:
        """routing clear <task_type> with no entry → info message."""
        # Assert: "No routing entry" in output

    def test_clear_all(self, _mock_db) -> None:
        """routing clear (no arg) → clears all entries."""
        # Set implement + review, clear all
        # Assert: both cleared

    def test_clear_all_empty(self, _mock_db) -> None:
        """routing clear (no arg) with no entries → info message."""
        # Assert: "No routing entries to clear" in output

    def test_clear_invalid_task_type(self, _mock_db) -> None:
        """routing clear with bad task type → exit 1."""
        # Assert: exit 1, "Invalid task type" in output
```

**Total: 17 test cases** (4 DB + 13 CLI) covering all commands with happy paths,
error paths, edge cases, orphan handling, and boundary conditions.

---

## Commit Boundaries

**Single commit boundary** — all CLI commands + DB method + tests + README:

```
feat(cli): add `sw config routing` commands (set/show/clear)
```

---

## Verification Plan

### Automated Tests
```bash
# Run only new test files
python -m pytest tests/unit/config/test_db_clear_routing.py tests/unit/cli/test_config_routing.py -q

# Run all CLI config tests together (no regressions)
python -m pytest tests/unit/cli/test_cli_config.py tests/unit/cli/test_config_routing.py -q

# Full hierarchical suite
python -m pytest tests/unit -q
python -m pytest tests/integration -q
python -m pytest tests/e2e -q
```

### Manual Verification
- `sw config routing --help` → shows set/show/clear subcommands
- `sw config routing set implement <profile>` → prints confirmation
- `sw config routing show` → displays table
- `sw config routing clear implement` → prints cleared message

### Linting
```bash
ruff check src/specweaver/cli/config.py src/specweaver/config/_db_llm_mixin.py
ruff check tests/unit/cli/test_config_routing.py tests/unit/config/test_db_clear_routing.py
ruff format --check src/ tests/
```

---

## Backlog

- **N+1 query in `routing show`**: Each entry calls `get_llm_profile(id)` separately.
  Acceptable for ≤7 task types on SQLite. If this ever becomes a bottleneck,
  replace with a single JOIN query that returns all columns directly.

---

## Research Notes

### Phase 0 Findings

1. **Typer sub-app nesting**: Typer 0.24.1 supports nested sub-applications
   via `parent_app.add_typer(child_app, name="routing")`. This is the same
   pattern used for `config_app` itself on `_core.app`. The resulting CLI
   structure is: `sw config routing set|show|clear`.

2. **DB methods available from SF-1**: All three DB methods needed are
   implemented and tested in `_db_llm_mixin.py`:
   - `link_project_profile(project, "task:<type>", profile_id)` — upserts
   - `unlink_project_profile(project, "task:<type>")` → bool
   - `get_project_routing_entries(project)` → list of dicts with `task_type`,
     `profile_id`, `profile_name`
   - `get_llm_profile_by_name(name)` → dict or None

3. **Existing CLI pattern**: All config commands follow the same structure:
   `_core._require_active_project()` → `_core.get_db()` → DB operation →
   Rich-formatted output. Tests use `CliRunner` with `monkeypatch.setattr`
   on `get_db`.

4. **No `context.yaml` update needed**: The `cli/` module's `consumes` list
   already includes `specweaver/config` (for DB calls) and `specweaver/llm`
   (for `TaskType` import). No new dependency is introduced.

5. **No schema migration**: SF-2 uses existing `project_llm_links` table
   with `"task:"` prefixed role keys. No DB changes needed.

6. **`TaskType` import is architecturally valid**: `cli/context.yaml` declares
   `consumes: specweaver/llm`. Importing `TaskType` from `llm/models.py`
   at module level preserves single source of truth for valid task types.
