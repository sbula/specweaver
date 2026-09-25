# C-EXEC-01 SF-01 — Initialization & Base Layer Isolation

**Status**: APPROVED · **FRs owned**: FR-1 · **Feature ID**: 3.20a · Design:
[C-EXEC-01_design.md](C-EXEC-01_design.md) §Sub-features → SF-01

FR-1 recorded 2026-08-17 under `specweaver-dev` §3.2c, from `INT-US-01-SF02-MIG`. Mutant: a
declared module path pointing at a namespace that does not exist.

## Goal

Install `Tach` and declare the bottom-most layer: `config`, `standards` and `logging.py` stay
stateless, with no upward dependency.

## Changes

1. **`pyproject.toml`** — add `"tach"` to the `[project.optional-dependencies] dev` array.
2. **`.agents/workflows/pre-commit/phase-2-code-quality.md`** — a mandatory step runs `tach check`
   alongside `ruff` and `mypy`. Enforcement sits in the internal workflow gate, not in developer
   git-hooks.
3. **`tach.toml` (NEW; or `tach.yml`)** — root layer graph; three independent base modules
   (`src.specweaver.core.config`, `src.specweaver.assurance.standards`, logging). Exact syntax, so
   no configuration key is invented:

```toml
[modules]
[[modules.path]]
path = "src.specweaver.logging"
depends_on = []
strict = true

[[modules.path]]
path = "src.specweaver.core.config"
depends_on = [
    { path = "src.specweaver.logging" }
]
strict = true

[[modules.path]]
path = "src.specweaver.assurance.standards"
depends_on = [
    { path = "src.specweaver.logging" }
]
strict = true
```

4. **Delete** `src/specweaver/config/__init__.py` and `src/specweaver/standards/__init__.py` — the
   manual `__all__ = [...]` exports go as each layer moves into Tach, so two boundary systems never
   coexist.

> [!CAUTION]
> If `tach check` reports `config` or `standards` referencing a domain model from
> `src/specweaver/validation` or `src/specweaver/flow`, **the workflow must fail**. Cut that
> reference and pass the value as an argument.

## Tests

1. `pip install -e ".[dev]"` — `tach` installs via `pyproject.toml`.
2. `tach sync`, or author the `tach.toml` root constraints by hand.
3. `tach check` from the project root — zero exit code.
4. `/pre-commit` — the new Phase 2 gate enforces `tach check`.
