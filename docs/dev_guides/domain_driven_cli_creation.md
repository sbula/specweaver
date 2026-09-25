# Domain-Driven CLI Creation

Use when: you add a CLI command to SpecWeaver.

Since **TECH-001 (Domain-Driven Design Unification)** there is no monolithic `interfaces/cli/`
layer. Each command belongs to its domain (Hexagonal Architecture); `interfaces/cli/main.py` only
mounts the domain apps.

## Steps

1. **Place it** at the domain boundary, in the domain's `interfaces` module:

```text
src/specweaver/
├── your_domain/
│   ├── core/                  # Pure domain logic (no CLI or Web dependencies)
│   ├── infrastructure/        # Repositories and external APIs
│   └── interfaces/
│       └── cli.py             # Your CLI entrypoint
```

2. **Create the domain app** in `cli.py`: a dedicated `typer.Typer` instance. Do **not** import the
   global `app` from `main.py`; the domain stays decoupled and testable alone.

```python
# src/specweaver/your_domain/interfaces/cli.py
import typer
from rich.console import Console

# 1. Create your domain-specific Typer instance
your_domain_app = typer.Typer(
    name="your-domain", 
    help="Commands for interacting with Your Domain.",
    no_args_is_help=True
)

console = Console()

# 2. Register your commands
@your_domain_app.command("run-task")
def run_task(
    target: str = typer.Argument(..., help="The target entity"),
    force: bool = typer.Option(False, "--force", "-f", help="Force execution")
) -> None:
    """Execute a specific task in your domain."""
    from specweaver.interfaces.cli._core import get_db, _require_active_project
    from specweaver.your_domain.core.service import MyDomainService

    # Always lazy load heavy dependencies and core services inside the function
    # to prevent CLI startup latency and cyclic imports.
    active_project = _require_active_project()
    db = get_db()
    
    console.print(f"Running task for [cyan]{target}[/cyan]")
    
    service = MyDomainService(db)
    service.execute(active_project, target, force=force)
    
    console.print("[green]Task complete.[/green]")
```

3. **Register it** on the root app in `src/specweaver/interfaces/cli/main.py`, wrapped in
   `try/except ImportError`:

```python
# src/specweaver/interfaces/cli/main.py

# ... existing imports ...

# 1. Safely import your domain CLI
try:
    from specweaver.your_domain.interfaces.cli import your_domain_app
    app.add_typer(your_domain_app, name="your-domain")
except ImportError as e:
    logger.error(f"Failed to load your_domain plugin: {e}")
    console.print(f"[yellow]Warning:[/yellow] your_domain plugin disabled due to error.")
```

4. **Test it** (below).

## Rules for `cli.py`

- **No heavy global imports.** Import core services, SQLAlchemy or heavy ML libraries *inside* the
  command function. Typer parses all CLI scripts at boot; a heavy global import slows every `sw`
  command and invites cyclic imports.
- **Shared CLI state comes from `_core.py`.** Import `get_db` and `_require_active_project` from
  `specweaver.interfaces.cli._core`, never from `main.py` (circular imports).
- **Pure adapter.** Parse arguments, call an Orchestrator/Service in `core/`, print the result.
  **Never** business logic or SQL queries.
- **Registration is isolated.** The `try/except ImportError` enforces **NFR-4 (Native Healer
  Isolation)**: if your plugin breaks on a bad dependency, the rest of the CLI (like `sw edit`) still
  boots so the agent can fix it.

## Testing

- **Import the root `app` locally** inside the test function, to avoid state leakage and module
  reloading issues from other tests.
- Use the `_mock_db` fixture for database isolation.

```python
# tests/integration/your_domain/interfaces/cli/test_cli.py
from pathlib import Path
from unittest.mock import patch
import pytest
from typer.testing import CliRunner

runner = CliRunner()

@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Patch get_db() to use an isolated temp DB."""
    from specweaver.core.config.cli_db_utils import bootstrap_database
    from specweaver.core.config.database import Database

    data_dir = tmp_path / ".specweaver-test"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))
    db_path = str(data_dir / "specweaver.db")
    bootstrap_database(db_path)
    db = Database(db_path)
    monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", lambda: db)
    return db

def test_run_task_success():
    # 1. Local import prevents module state pollution!
    from specweaver.interfaces.cli.main import app
    
    # 2. Set up test state
    with patch("specweaver.interfaces.cli._core._require_active_project", return_value="test_proj"):
        # 3. Invoke
        result = runner.invoke(app, ["your-domain", "run-task", "my_target"])
        
    # 4. Assert
    assert result.exit_code == 0
    assert "Task complete" in result.output
```
