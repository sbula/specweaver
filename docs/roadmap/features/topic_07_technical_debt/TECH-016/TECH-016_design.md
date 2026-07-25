# Design: Unified Artifact Writer & Serialization Format Enforcement

- **Feature ID**: TECH-016
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: INT-US-21 SF-02 implementation-plan Phase 0 (2026-07-25).

## Problem Statement

Two independent problems, one fix.

### 1. The serialization format is correct by coincidence, not by construction

Two handlers dump a Pydantic model straight to YAML:

| Call site | Model | Safe today? |
|---|---|---|
| `core/flow/handlers/generation.py:398` — `PlanSpecHandler` | `PlanArtifact` | ✅ **only because it has no enum fields** |
| `core/flow/handlers/scenario.py:96` — `ConvertScenarioHandler` | `ScenarioSet` | ✅ **only because it has no enum fields** (verified 2026-07-25) |

Both call `yaml.dump(x.model_dump(), buf)`. `model_dump()` returns *Python* objects, so any enum
field reaches `ruamel` as an enum and it **raises**:

```
RepresenterError: cannot represent an object: <DALLevel.DAL_B: 'DAL_B'>
```

Measured on `DecompositionPlan`, whose `components[].proposed_dal: DALLevel` is **required**, so the
failure rate would be 100% of real plans — not an edge case. `model_dump(mode="json")` coerces
enums to `str` (and tuples to lists) and dumps cleanly.

**Add one enum field to `PlanArtifact` or `ScenarioSet` and both existing writers break**, with no
test to catch it. INT-US-21 SF-02 writes `mode="json"` inline because it needs correct behaviour
immediately; this ticket generalises that so nobody has to remember it again.

### 2. The write sequence is duplicated five times

`derive path → extract-or-generate uuid → wrap_artifact_tag → write → log_artifact_event` is
hand-rolled at:

- `core/flow/handlers/draft.py` (×2 — `DraftSpecHandler`, `DraftFeatureHandler`)
- `core/flow/handlers/generation.py` (`PlanSpecHandler`)
- `core/flow/handlers/lint_fix.py` (×2)

Each copy is a place the format can drift. INT-US-21 SF-02 adds a sixth.

## Goal

One artifact-writing helper that owns the whole sequence, plus a check that makes bypassing it fail
the build. The helper alone is only *available*; the check is what makes it *required*.

## Candidate Approaches (not yet designed)

1. **Shared writer helper + architecture assertion (recommended starting point).** One function
   taking `(path, model, language, event_type, context)` performing
   `model_dump(mode="json")` → YAML → uuid tag → write → lineage. Then extend the existing
   `tests/unit/test_architecture.py` (which already makes mechanical repo-wide assertions) with:
   *no source file may pass a bare `.model_dump()` into `yaml.dump(`.* Greppable and unambiguous.
2. **Model-level enforcement** — `model_config = ConfigDict(use_enum_values=True)` or a
   `@field_serializer` on every artifact model. **Rejected as the primary fix:** it is a convention
   someone must remember on each new model, and `use_enum_values` changes the *in-memory* type
   repo-wide — a large semantic change to solve a serialization problem.
3. **Do nothing; document the rule.** The status quo baseline. This repo has repeatedly found that
   a rule nobody is forced to follow decays (see `TECH-015`).

## Non-Goals (proposed, pending design)

- Changing the artifact *schemas* themselves. This is about how they are written, not what is in
  them. INT-US-21 AD-4 freezes the decomposition artifact schema as a seam for `C-FLOW-12`.
- The Markdown artifact writers (`draft.py`, `lint_fix.py`) may keep their own rendering; only the
  shared uuid-tag/lineage tail is in scope for unification.
- Retrofitting every historical artifact on disk.

## Execution Constraint

Land as its own commits, **never bundled into a feature commit** — the diff must stay reviewable as
"moved, not changed". Full suite green at each step.

## Next Step

Run the `specweaver-design` skill against this stub before any implementation.
