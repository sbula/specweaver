# B-VAL-02 SF-01 — CLI Command + Git Hook Deployment

**Status**: APPROVED · **FRs owned**: FR-3, FR-5, FR-6, FR-7 (recorded 2026-08-17 under
`specweaver-dev` §3.2c, from `INT-US-01-SF03-MIG`) · **Depends on**: none · Design:
[B-VAL-02_design.md](B-VAL-02_design.md) §Sub-features → SF-01

Owned FRs: reading the git index, extracting signatures from each staged file, locating its plan,
and judging the two against each other. **FR-5's `AstAtom` and `@trace` clauses are struck** — no
such class exists, and no trace extraction happens on this path. **FR-6 reads
`specs/*_plan.yaml`**, by path match and then by lineage uuid, not `Spec.md` traceability tags. See
the design's "How it matches today".

## Goal

Add the CLI entry points `sw hooks install` and `sw drift check-rot --staged`, and deploy a strict
git `pre-commit` hook that intercepts commits for spec-alignment checks.

## Decisions

- **Interpreter:** the hook uses `sys.executable`, captured at `sw hooks install` time, e.g.
  `/absolute/path/to/venv/bin/python -m specweaver.interfaces.cli.main drift check-rot --staged`.
  The hook fires regardless of virtualenv activation.
- **Fail closed:** the bash hook MUST `exit 1` if it cannot resolve the python binary.
- **Namespace:** hook deployment in `cli/hooks.py`; the check in `cli/drift.py`
  (`check-rot --staged`). In SF-01 `check-rot` only validates arguments and exits — a stable
  interface for SF-02 to wire the `PipelineRunner` into.

## Changes

1. **[NEW] `src/specweaver/cli/hooks.py`** — the `sw hooks` typer app; `install()`
   (`sw hooks install --pre-commit`) maps the interpreter via `sys.executable`, writes the
   `.git/hooks/pre-commit` bash script, and sets it executable (`chmod +x`).

   > [!IMPORTANT]
   > The generated bash script must hard-fail (`exit 1`) if the mapped python interpreter cannot be found or fails execution.
   > The generated bash script must execute: `"$PYTHON_EXEC" -m specweaver.interfaces.cli.main drift check-rot --staged`.

2. **[MODIFY] `src/specweaver/cli/main.py`** — imports `hooks` to register the `sw hooks` group.
3. **[MODIFY] `src/specweaver/cli/drift.py`** — adds
   `check_rot(staged: bool = typer.Option(False, "--staged"))` to the `drift` Typer app. In SF-01 it
   exits `exit 0`.

## Tests

| File | Case |
|---|---|
| `tests/cli/test_hooks.py` (new) | mocks `.git/hooks/`; `sw hooks install` writes exactly to the target path; the script contains the `sys.executable` path |
| `tests/cli/test_rot_cmd.py` (new) | bare CLI execution of `sw drift check-rot --staged` |

Run `pytest` on both; no regression in `drift.py`. Manual: `poetry run sw hooks install` (or
`uv run`), inspect `.git/hooks/pre-commit` for the python path.

## As built

**Since moved** (noted 2026-09-25): `cli/hooks.py` → `workspace/project/interfaces/cli_hooks.py`;
`cli/drift.py` → `assurance/validation/interfaces/cli_drift.py`; the tests →
`tests/unit/workspace/project/interfaces/test_cli_hooks.py` and
`tests/unit/interfaces/cli/test_rot_cmd.py`; the hook e2e is `tests/e2e/capabilities/core/test_hooks_e2e.py`.
