# Interfaces (CLI + API)

Thin delivery layer. Delegates ALL business logic to core modules. No domain logic here.

## Modules

- **cli/** — Typer CLI (`sw` command). Entry point: `specweaver.interfaces.cli.main:app`.
  - Uses Rich for terminal output. Typer for command routing.
  - Each bounded context registers its own CLI subcommands via its `interfaces/` subpackage.
- **api/** — FastAPI REST server. Optional dependency (`[serve]` extra).
  - Uvicorn for serving. Markdown + bleach for safe rendering.

## Conventions

- CLI commands are thin wrappers. They parse args, call a service, format output. Nothing else.
- All subcommands are registered from their respective domain modules (e.g., `core.flow.interfaces`).
- Error handling: user-friendly messages with Rich panels, full tracebacks only in `--verbose` mode.

## Test Commands

```bash
python -m pytest tests/unit/interfaces/ -v --tb=short
python -m pytest tests/integration/interfaces/ -v --tb=short
```

<!-- Last verified: 2026-07-12 -->
