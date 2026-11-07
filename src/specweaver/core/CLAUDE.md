# Core Domain (config + flow)

Pure domain logic. NO I/O, NO external calls. All I/O is delegated via ports/adapters.

## Modules

- **config/** — Pydantic settings and paths. No I/O: files are opened by `infrastructure/database/`,
  and `config/bootstrap/` holds `specweaver.db`'s schema steps.
  - Depends on: `core.flow`, `infrastructure.llm`, `workspace`, `workspace.memory`
- **flow/** — Pipeline engine: models, runners, gates, handlers, handover persistence.
  - Depends on: `graph`, `workflows.*`, `sandbox`, `infrastructure.llm`, `core.config`, `assurance.*`, `workspace.*`

## Conventions

- All configuration models use Pydantic v2 with strict mode.
- Flow engine uses a handler-based dispatch pattern. New pipeline stages = new handlers.
- SQLite files open only through `infrastructure/database/` (WAL, foreign keys, lock wait).

## Test Commands

```bash
python -m pytest tests/unit/core/ -v --tb=short
python -m pytest tests/integration/core/ -v --tb=short
```

## Boundary Rules

Check `tach.toml` for exact dependency allowlists. Run `tach check` after any import changes.

<!-- Last verified: 2026-11-07 -->
