# C-VAL-03 SF-01 — DAL Schema & Pydantic Impact Matrix Merge

**Status**: APPROVED · COMPLETE, all pre-commit gates passed · **FRs owned**: FR-1, FR-4 (recorded
2026-08-17 under `specweaver-dev` §3.2c, from `INT-US-25-SF01-MIG`) · **Depends on**: none ·
Design: [C-VAL-03_design.md](C-VAL-03_design.md) §Sub-features → SF-01 · Feature ID 3.20b

## Goal

The configuration layer for Mixed Criticality: the DAL declaration in `context.yaml` and the
project's own impact matrix deep-merged over the packaged profiles.

- `DALLevel` enum (`DAL_A` through `DAL_E`) in `config/dal.py`.
- `DALImpactMatrix` schema mapping each level to config overrides (disable rules, tighten
  thresholds).
- Deep-merge `.specweaver/dal_definitions.yaml` over the internal profiles with `ruamel.yaml`, then
  Pydantic strict schema validation.

## Changes

1. **[NEW] `src/specweaver/config/dal.py`** — `class DALLevel(enum.StrEnum):`
   - `DAL_A = "DAL_A"` (Highest Risk / Aerospace-grade)
   - `DAL_B = "DAL_B"`
   - `DAL_C = "DAL_C"`
   - `DAL_D = "DAL_D"`
   - `DAL_E = "DAL_E"` (Lowest Risk / Startup Scripts)
2. **[MODIFY] `src/specweaver/config/settings.py`**
   - Add `from specweaver.core.config.dal import DALLevel`.
   - `class DALImpactMatrix(BaseModel):` — `dict[DALLevel, ValidationSettings]`.
   - `ValidationSettings` fields support `enabled: bool = True` explicitly, so a rule can be
     disabled (e.g. `Rule_X: {"enabled": False}`).
   - Module-level pure function `deep_merge_dict(base: dict, overlay: dict) -> dict`: updates
     primitive keys, recurses into nested dicts.
   - `load_settings()`: if `.specweaver/dal_definitions.yaml` exists, load it via `ruamel.yaml`;
     fetch the default DAL definitions (or an empty baseline); `deep_merge_dict()` the project file
     over it; hydrate the result into Pydantic models.

## Tests

`tests/unit/config/test_dal_merge.py`:

| Case | Asserts |
|---|---|
| `deep_merge_dict()` | overlay keys overwrite base keys; unmentioned base keys are preserved |
| mocked `.specweaver/dal_definitions.yaml` | `load_settings()` disables `S01` for `DAL_E`, keeps it enforced for `DAL_A` |
| invalid value (`warn_threshold: "apple"`) | Pydantic fails |

Gate: architecture validation passes with `config/settings.py` at `consumes: []` (no import from
Validation); `pytest -m unit` passes.

## Decisions (audit)

| # | Decision | Why |
|---|---|---|
| 1 | Deep merge by a custom `deep_merge_dict()` in `config/settings.py` + `ruamel.yaml`, then `ValidationSettings(**merged)` | Pydantic's `SettingsConfigDict` has no `deep_merge=True`; hacking internal settings sources is fragile |
| 2 | `DALLevel` lives in `config/dal.py`, not `validation/models.py` | No circular dependency: `config` sits below everything (`consumes: []`) |

## As built

`DALLevel` later moved to `src/specweaver/commons/enums/dal.py` (SF-05).
