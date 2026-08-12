# Design: Unified Artifact Writer & Serialization Format Enforcement

- **Feature ID**: TECH-016
- **Epic**: Topic 07 (Technical Debt)
- **Status**: PARTIAL 2026-08-12 — **§1 DELIVERED** (`f10ec587`): both writers now dump in
  `mode="json"`, and `tests/unit/test_architecture.py::unsafe_model_dumps` makes bypassing it fail
  the build. **§2 re-scoped** against the code — the stub's fix shape fits 2 of its 6 sites; see
  §Correction. Not run through `specweaver-design`: §1 needed no design, and §2's decision space
  was settled by measurement.
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

## Correction, 2026-08-12 — measured against the code before implementing

§1 was accurate in substance and is delivered. **§2 was not**, and building it as written would
have forced four unlike call sites through a signature that does not fit them.

### What the stub got wrong

1. **Wrong handler named.** `scenario.py:96 — ConvertScenarioHandler` is in fact
   **`GenerateScenarioHandler`** (class at `:22`; `ConvertScenarioHandler` is a different handler
   at `:120` in the same file). Both exist, so the citation misleads rather than merely slipping.
   Line numbers also drifted by one: the real sites are `generation.py:397`, `scenario.py:97`.
2. **The sixth site already landed.** "INT-US-21 SF-02 adds a sixth" is written in the future
   tense; `decomposition_artifacts.py::persist_decomposition` + `log_decomposition_lineage` are in
   the tree. It is **six**, not five.
3. **`scenario.py` is a §1 site but not a §2 site.** It has no uuid, no tag and no lineage event —
   a bare model → YAML → write. The "two problems, one fix" framing conceals that the two problem
   sets do not overlap the way it implies.

### The six sites are not one sequence

| Site | payload | tag language | uuid | lineage |
|---|---|---|---|---|
| `draft.py` ×2 | markdown, **already written to disk** by the drafter | `markdown` | read back; tag injected **only if absent** | yes |
| `generation.py` | Pydantic model → YAML | `yaml` | read back if the file exists, else mint | yes, separately at `:480` |
| `decomposition_artifacts.py` | **dict**, already dumped by the caller | `yaml` | read back if exists, else mint | yes, in a separate never-raises function |
| `lint_fix.py` ×2 | **LLM-returned string** | `python` | extracted from the input file; **never minted** | only when a uuid was present |
| `scenario.py` | model → YAML | — | — | — |

Candidate Approach 1's signature — `(path, model, language, event_type, context)` performing
`model_dump(mode="json") → YAML → tag → write → lineage` — **fits `generation.py` and (with a dict)
`decomposition_artifacts.py`. That is all.** `draft.py` has no model in hand and the file is
already on disk; `lint_fix.py` carries a *pre-existing* uuid through an LLM round-trip (it even
injects a prompt instruction telling the model to reproduce the tag) and minting one there would be
a defect, not a refactor.

**The stub also contradicts itself**: its Non-Goals say *"only the shared uuid-tag/lineage tail is
in scope for unification"*, while Candidate Approach 1 starts from a model. Those are two different
designs, and the Non-Goals are the one the code supports.

### Corrected scope for §2

The shared thing is the **tail**, not the write:

- `ensure_artifact_tag(path, language) -> uuid` — read back an existing uuid, mint one only when
  asked to, inject the tag when absent. Covers all six.
- the `log_artifact_event` call, which is already near-identical at five sites.

The **head** — render a model, a dict, or an LLM string to bytes — genuinely differs per site and
should stay where it is. Unifying it is what the Non-Goals already ruled out.

### Adjacent defect found while measuring — filed as `TECH-036`

`lint_fix.py:333` opens `async with context.db.async_session_scope()` with **no `if context.db`
guard**, unlike all four other lineage sites (`draft.py:204`, `decomposition_artifacts.py:137`,
`generation.py`). A truthy `artifact_uuid` with `context.db is None` raises `AttributeError` from
inside the lineage tail — telemetry taking down a step that had already succeeded, which is exactly
the failure mode `log_decomposition_lineage`'s never-raises contract was written to prevent. Not
folded in here, per the scope rules in `specweaver-ticket` — filed as
**[`TECH-036`](../TECH-036/TECH-036_design.md)**, which sequences after §2 so the two do not build
competing tail helpers.

## Next Step

§2, at the corrected scope above. No `specweaver-design` run needed — the decision space is the
table above, and it is measured.
