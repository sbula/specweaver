# D-FLOW-03 SF-02 — CLI Routing Commands

**Status**: COMPLETE · Committed as `27b03522`. · **FRs owned**: FR-4 · **Depends on**: SF-01
(complete) — `link_project_profile()`, `unlink_project_profile()`,
`get_project_routing_entries()`, `get_llm_profile_by_name()` · Design: [D-FLOW-03_design.md](D-FLOW-03_design.md) §Sub-features → SF-02 · Feature
ID feature_3_14

## Goal

Three subcommands under `sw config routing` to manage per-task-type routing entries for the active
project — the user surface of SF-01's routing engine (Feature 3.12b):
- `sw config routing set <task_type> <profile_name>` — link a task type to a profile
- `sw config routing show` — display routing table
- `sw config routing clear [<task_type>]` — remove routing entries

**Non-interactive.** No `typer.confirm()` prompts, no "Are you sure?" gates — the commands run in
CI/CD pipelines and autonomous agent workflows.

## Where it plugs in

Since moved (2026-09-25): the command group lives in `core/config/interfaces/cli.py`; the DB methods
in `infrastructure/llm/store.py` (async). Paths below are as of the plan.

1. **Typer sub-app nesting**: Typer 0.24.1 nests via `parent_app.add_typer(child_app, name="routing")`
   — the same pattern that mounts `config_app` on `_core.app` (line 23:
   `_core.app.add_typer(config_app, name="config")`). Result: `sw config routing set|show|clear`.
2. **DB methods from SF-01**, in `_db_llm_mixin.py`:
   - `link_project_profile(project, "task:<type>", profile_id)` — upserts
   - `unlink_project_profile(project, "task:<type>")` → bool
   - `get_project_routing_entries(project)` → list of dicts with `task_type`, `profile_id`,
     `profile_name`
   - `get_llm_profile_by_name(name)` → dict or None
3. **CLI pattern**: `_core._require_active_project()` → `_core.get_db()` → DB operation →
   Rich-formatted output. Tests use `CliRunner` with `monkeypatch.setattr` on `get_db`.
4. **No `context.yaml` change**: `cli/context.yaml` already `consumes: specweaver/config` (DB) and
   `consumes: specweaver/llm` (`TaskType`). Importing `TaskType` from `llm/models.py` at module level keeps
   one source of truth for valid task types.
5. **No schema migration**: existing `project_llm_links` with `"task:"` role keys.

## Changes

### DB layer — [_db_llm_mixin.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/_db_llm_mixin.py) [MODIFY]

One method for orphan-safe bulk clearing:

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

`get_project_routing_entries()` JOINs on `llm_profiles`, so a `task:` link whose profile was
deleted is invisible to it. This method clears every `task:*` row regardless.

### CLI layer — [config.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli/config.py) [MODIFY]

A `routing_app` Typer sub-app with three subcommands, registered as
`config_app.add_typer(routing_app, name="routing")`.

**Valid task types come from the `TaskType` enum** at import time, not a hardcoded list; a new
`TaskType` member is accepted automatically. `UNKNOWN` is excluded — not user-configurable.

```python
from specweaver.infrastructure.llm.models import TaskType

# Derive valid values from the single source of truth (TaskType enum).
# Exclude UNKNOWN — it is not user-configurable.
_ROUTABLE_TASK_TYPES: frozenset[str] = frozenset(
    t.value for t in TaskType if t != TaskType.UNKNOWN
)
```

**`routing set`:**

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

The `try/except ValueError` around `link_project_profile` covers the TOCTOU race between
`_require_active_project()` and the write: a project deleted in between would otherwise crash with
a traceback.

**`routing show`:**

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

An orphaned link (profile deleted) shows `[deleted]` markers instead of vanishing, so users can
find and `routing clear` it.

**`routing clear`:**

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

### Documentation — [README.md](file:///c:/development/pitbula/specweaver/README.md)

A "Model Routing" section after "LLM Telemetry" in the CLI Commands area:

```markdown
### Model Routing

| Command | Description |
|---|---|
| `sw config routing set <task_type> <profile>` | Route a task type to a specific LLM profile |
| `sw config routing show` | Show the routing table for the active project |
| `sw config routing clear [<task_type>]` | Clear routing entries (one or all) |
```

And a Features bullet:
```markdown
- **Config-driven model routing** — Map task types (`implement`, `review`, etc.) to specific LLM profiles for per-task model/temperature control
```

## Tests

- [test_config_routing.py](file:///c:/development/pitbula/specweaver/tests/unit/cli/test_config_routing.py)
  [NEW] — `test_cli_config.py` pattern: `CliRunner` + mocked DB via
  `monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", ...)`.
- [test_db_clear_routing.py](file:///c:/development/pitbula/specweaver/tests/unit/config/test_db_clear_routing.py)
  [NEW] — `clear_all_project_routing()`.

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

**17 test cases** (4 DB + 13 CLI): happy paths, error paths, edge cases, orphan handling,
boundaries.

Commit boundary — one commit (CLI commands + DB method + tests + README):

```
feat(cli): add `sw config routing` commands (set/show/clear)
```

Verify:

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

Manual:
- `sw config routing --help` → shows set/show/clear subcommands
- `sw config routing set implement <profile>` → prints confirmation
- `sw config routing show` → displays table
- `sw config routing clear implement` → prints cleared message

Lint:
```bash
ruff check src/specweaver/cli/config.py src/specweaver/config/_db_llm_mixin.py
ruff check tests/unit/cli/test_config_routing.py tests/unit/config/test_db_clear_routing.py
ruff format --check src/ tests/
```

## Out of scope

- **N+1 query in `routing show`**: one `get_llm_profile(id)` per entry. Fine for ≤7 task types on
  SQLite; if it ever bottlenecks, use one JOIN returning all columns.
