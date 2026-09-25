# C-VAL-03 SF-02 — Fractal Resolution Engine

**Status**: APPROVED · COMPLETE · **FRs owned**: FR-3 (recorded 2026-08-17 under `specweaver-dev`
§3.2c, from `INT-US-25-SF01-MIG`) · Design:
[C-VAL-03_design.md](C-VAL-03_design.md) · Feature ID 3.20b

## Goal

Resolve the DAL of any target file: the nearest tier declared at or above it. O(1) cached walk up
from the file's directory to the nearest `context.yaml` with `operational.dal_level`.

No tier found → fall back to a DB-backed project default, seeded to the maximum (`DAL_A`) at setup.

## Changes

1. **`specweaver/config/_schema.py`** — DB migration `SCHEMA_V13`: table `projects` gains
   `default_dal VARCHAR NOT NULL DEFAULT 'DAL_A'`.
2. **`specweaver/config/_db_config_mixin.py` & `database.py`** — `get_default_dal(project_name)`,
   `set_default_dal(project_name, dal)`; register `SCHEMA_V13` in the migrations list of
   `database.py`.
3. **`specweaver/config/dal_resolver.py`** — `DALResolver`:
   - constructed with `project_root: Path`; cache `self._cache: dict[Path, DALLevel | None]`.
   - `resolve(target_path: Path) -> DALLevel | None`: walk `target_path.parents`, parsing
     `context.yaml` in order; return `None` once outside `project_root`.
   - A `dal_level` string not in `DALLevel` → `ValueError` at once (fail-secure).
   - Malformed YAML does not abort the walk (added during Task 2).
4. **`specweaver/flow/_validation.py`** — `ValidateSpecHandler.execute` and
   `ValidateCodeHandler.execute`:
   1. `DALResolver(context.project_path)`; `dal = dal_resolver.resolve(target)`.
   2. `if not dal:` → `dal = context.db.get_default_dal()`.
   3. `dal_settings = context.settings.dal_matrix.matrix.get(dal)`.
   4. If set, deep-merge it (plain dict merge) over `context.settings.validation` and rebuild a
      `ValidationSettings`.
   5. `apply_settings_to_pipeline(pipeline, merged_settings)`.
5. **`specweaver/config/context.yaml`** — add `DALResolver` to `exposes:`.

All five are done.

## Tests

| File | Covers |
|---|---|
| `tests/unit/config/test_dal_resolver.py` | valid / invalid / missing `.yaml`; memoization (against patches); the `project_root` cutoff |
| `tests/unit/config/test_database.py` | `SCHEMA_V13` migration on fresh and upgraded DBs |

Mutant: stopping the walk at the target's own directory leaves the resolver working and strips
inheritance from most of the tree — 17 fail.

Gate: `/pre-commit` (10-test validation battery, `tree-sitter` drift checks, type checks, style).

## Decisions (audit)

| # | Decision | Why |
|---|---|---|
| 1 | Resolver (`dal_resolver.py`) lives in `specweaver/config/` | A leaf node `flow` can call without a boundary cycle |
| 2 | `ValidateSpecHandler` / `ValidateCodeHandler` (`flow/_validation.py`) look up the DAL, apply the default, and map the matrix into `apply_settings_to_pipeline()` | The handlers already own pipeline setup |
| 3 | The walk halts at `project_root` and returns `None` | Never scan outside the project |
| 4 | `None` → the DB's `default_dal`, seeded `DAL_A` (Flight-Critical) at project init | Strictest governance for new and legacy projects on onboarding |
| 5 | Feature 3.5's Validation DB Overrides cleanup is kept to **SF-03** | Limits regression risk; keeps SF-02 testable |
