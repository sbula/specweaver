# E-UI-01 SF-01 — Project Scaffold + CLI Shell

**Status**: COMPLETED · **FRs owned**: FR-1..FR-7 · Design: [E-UI-01_design.md](E-UI-01_design.md)

## Changes

- [x] `pyproject.toml` (uv, PEP 621, core deps)
- [x] `src/specweaver/__init__.py` + `cli.py` (Typer app with stubs)
- [ ] `src/specweaver/config/settings.py` (path resolution)
- [x] `src/specweaver/project/discovery.py` + `scaffold.py` (`sw init`)
- [x] Tests: CLI dispatch, settings, scaffold

Nothing copied from FM. Runnable: `sw --help`, `sw init --project ./test-project`.

> [!NOTE]
> CLI uses level-oriented commands: `sw check --level=component spec.md` replaces the earlier
> `sw validate spec`. MVP supports `--level=component` (spec) and `--level=code` only. Future:
> `--level=feature`, `--level=class`, `--level=function`, and language-specific code rules.

**Since moved** (checked 2026-09-25): `cli.py` → `src/specweaver/interfaces/cli/`; `project/` →
`src/specweaver/workspace/project/`; settings live in `src/specweaver/core/config/settings.py`.
`--level=feature` now exists.
