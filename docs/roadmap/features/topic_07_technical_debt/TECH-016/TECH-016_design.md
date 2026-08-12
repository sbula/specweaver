# Design: Unified Artifact Writer & Serialization Format Enforcement

- **Feature ID**: TECH-016
- **Epic**: Topic 07 (Technical Debt)
- **Status**: **DELIVERED 2026-08-12.** §1 (`f10ec587`): both writers dump in `mode="json"`, and
  `tests/unit/test_architecture.py::unsafe_model_dumps` makes bypassing it fail the build. §2:
  `handlers/artifact_lineage.py` unifies **both** halves of the tail — identity (4 sites) and
  events (**7** sites) — leaving exactly one `log_artifact_event` call in the repo. Not run through
  `specweaver-design`: §1 needed no design, and §2's decision space was settled by measurement.

  > **Two status corrections, same day, kept because the failure mode is specific.**
  > This was recorded DELIVERED after §1, then again after only the identity half of §2. Both
  > times the §2 scope had been re-measured *correctly* — the six write sites really do not fit
  > one model-shaped helper — and both times that true finding was used to shrink the deliverable
  > rather than to re-plan it. **"The head differs per site" does not license skipping the tail.**
  > `TECH-036` owns the missing `None` guard; it never owned the unification.
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

## Delivery of §2, 2026-08-12

`src/specweaver/core/flow/handlers/artifact_identity.py` — three primitives, not one writer:

| | contract | callers |
|---|---|---|
| `derive_artifact_uuid(path)` | the uuid on disk, or a fresh one | `generation.py`, `decomposition_artifacts.py` |
| `tag_content(content, uuid, language)` | tag on the first line, no-op if already tagged | those two, plus `lint_fix.py`'s safety fallback |
| `ensure_file_tagged(path, language)` | tag a file already written; returns its uuid | `draft.py` ×2 |

**The head stays where it is**, per the correction above: rendering a model, a dict, or an LLM's
reply to bytes is genuinely different work at each site.

**Two behaviours had to be reconciled, so both are now pinned by a test.** `draft.py`'s inline copy
guarded on `.exists()` and its `_ensure_artifact_tag` twin did not — unifying them forced a choice.
`ensure_file_tagged` mints an identity for a missing file but **does not create it**
(`test_a_missing_file_is_not_created`). Likewise `tag_content` leaves content carrying a
*different* uuid alone, because two tags in one file is a lineage fork and the identity already on
disk wins.

`derive_artifact_uuid` swallows `OSError`. Lineage is telemetry and must never be why a write
fails — the same reasoning as `log_decomposition_lineage`'s never-raises contract, and the reason
`TECH-036` exists.

**A `TECH-023` violation fell out**: `LintFixHandler::_llm_fix` **18 → under threshold**, resolved
rather than relocated. Baseline re-frozen at **40**; the diff is a single deletion with no
additions. This is the sequencing argument from the session plan paying off — four of `TECH-023`'s
eight `core/flow/handlers/` violations sit in files this ticket restructures, which is why the
handler complexity cluster is measured *after* this and not before.

`6504 passed, 11 skipped, 0 failed`. `ruff`, `mypy` (335 files), `tach` clean; cycles 0 across 335
modules; class-health and suppression ratchets unmoved.

## Delivery of §2's event half, 2026-08-12

The remainder. `log_artifact_lineage(context, uuid, event_type, *, parent_id, model_id)` replaces
**seven** hand-rolled sites — not the five first counted; `generation.py` has three, not one.

| site | event | had a guard? |
|---|---|---|
| `draft.py` | `drafted_spec` | guard only |
| `draft.py::_log_lineage` | `drafted_feature_spec` | guard only |
| `generation.py` ×3 | `generated_code` / `_tests` / `_plan` | guard only |
| `decomposition_artifacts.py` | `generated_decomposition` | guard **and** `try` |
| `lint_fix.py` | `lint_fixed` | **neither** — `TECH-036` |

`grep log_artifact_event src/specweaver/core/flow/` now returns **one** hit, inside the helper.

**The never-raises contract had no test at all.** It lived in `log_decomposition_lineage`'s
docstring, written after a real CB-1 failure against a non-bootstrapped database (2026-07-26), and
nothing exercised it — one of the seven sites honoured it and six did not. It is now the shared
default, with tests for a repository failure, a session-open failure, and a `context.db` that is
not a database at all.

**This resolves `TECH-036`** as a consequence: a shared helper cannot ship a known defect, so the
guard had to come with it. Verified to `TECH-036`'s own stated bar — a handler-level test that
*plants* `context.db = None` and asserts `PASSED` with the fix on disk — and the probe was checked
against the pre-fix code:

```
'NoneType' object has no attribute 'async_session_scope'
assert <StepStatus.ERROR> == <StepStatus.PASSED>
```

The first probe attempt was **invalid** and worth recording: reverting the whole file to `HEAD`
also reverted the module rename, so it failed on `ModuleNotFoundError` rather than on the defect.
Reverting *only* the lineage tail produced the failure above. Same trap as `TECH-035`'s first
class-health probe — a probe that fails for the wrong reason proves nothing.

Why it was reachable at all: `_make_context` in `test_lint_fix_handler.py` supplied a mock database
unconditionally, so **every** test in that file took the branch that works. `db` is now a
parameter.

The module is `artifact_lineage.py`, renamed from `artifact_identity.py` one commit after it was
created — identity plus events is one contract ("an artifact's lineage"), and the old name stopped
describing it.

`6519 passed, 11 skipped, 0 failed`. `ruff`, `mypy` (335 files), `tach` clean; 0 cycles; complexity
ratchet **40**, suppressions **227**, class-health unmoved.

## Next Step

None — the ticket is closed. `TECH-036` closes with it, resolved by this work rather than on its
own.
