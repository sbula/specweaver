# B-INTL-01 SF-01 — Injection & Orchestrator

**Status**: APPROVED. Implemented. · **FRs owned**: FR-1 · **Depends on**: none · Design:
[B-INTL-01_design.md](B-INTL-01_design.md) §Sub-features → SF-01

## Goal

The `flow` handlers read the target component's `archetype`, load the matching validation YAML, and
inject the AST payload into the validation layer without breaking its `forbids: loom/*` boundary.

## Where it plugs in

| Fact | Where |
|---|---|
| `ValidateSpecHandler`, `ValidateCodeHandler` — `_resolve_merged_settings`, `_run_validation` | `src/specweaver/core/flow/_validation.py` |
| `DALResolver` — the model for the new resolver | `core/config` |
| `CodeStructureAtom` returns a plain Python `dict`, no OS/C-pointer memory locks leaking | `loom/atoms` |

## Changes

1. **[NEW] `src/specweaver/core/config/archetype_resolver.py`** — `ArchetypeResolver`, modeled on
   `DALResolver`: walks upward from the target path to the nearest `context.yaml` and returns its
   `archetype` string (e.g. `spring-boot`, `vue`).

   ```python
   class ArchetypeResolver:
       def __init__(self, workspace_root: Path):
           ...
       def resolve(self, target_path: Path) -> str | None:
           ...
   ```

2. **[MODIFY] `src/specweaver/core/flow/_validation.py`**:
   1. Instantiate `ArchetypeResolver` during `_resolve_merged_settings` (or before `_run_validation`).
   2. `ValidateCodeHandler._run_validation`:
      - Run `CodeStructureAtom(cwd).run({"intent": "extract_skeleton", "path": code_path})` to get the AST dict.
      - Load `pipeline_name = f"validation_code_{archetype}"`; fall back to `"validation_code_default"`.
      - Inject by parameter (Option B approved): for each of `pipeline.steps`, set
        `step.params["ast_payload"] = payload` so the rules instantiate with it.
   3. `ValidateSpecHandler._run_validation`: same archetype fallback, loading
      `validation_spec_{archetype}.yaml`.

`flow` is the side-effect broker: it extracts the AST via Loom and passes a plain dict to
`assurance/`, which removes the layer violation. Injecting through `step.params["ast_payload"]`
keeps the `Rule.check(spec_text)` signature for every rule.

## Tests

| Tier | File / Case |
|---|---|
| Unit | `tests/unit/core/config/test_archetype_resolver.py` — upward search finds the nearest `archetype`; missing and malformed YAML |
| Integration | `ValidateCodeHandler` run: `CodeStructureAtom` reads the file and the resulting `dict` lands in `step.params` without failing execution |

All unit, integration and E2E tests green.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | How does the payload reach the rules? | **Option B** — parameter injection into `step.params`. Option A (typed `Rule.check()` argument) deferred, see below |

Deferred (Option A): unify DI across the engine — refactor `Rule.check()` across the 30+ validation
rules to take an explicitly typed `injected_payload: dict[str, Any] | None = None`. Needs its own
ticket.

## As built

- `CodeStructureAtom` needs `cwd` passed explicitly (like `QARunnerAtom`). The atom builds its own
  `FileExecutor`, so `flow/` takes no domain dependency.
- **Since moved** (checked 2026-09-25): the handlers now live in
  `src/specweaver/core/flow/handlers/validation.py`; the extract intent is `read_file_structure`.
