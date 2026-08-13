# Design: The Code-Level DAL Override Is Unproven End to End (Needs a Scripted LLM)

- **Feature ID**: TECH-041
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Found 2026-08-13 while fixing `TECH-017`'s vacuous-assertion findings. The test that
  claimed this coverage — `test_e2e_sw_implement_pipeline_dal_strictness` — had never executed
  `sw implement` at all. Filed rather than left in a docstring.

## Problem Statement

`C-VAL-03` (Dynamic Risk Rulesets) claims that a module's DAL injects stricter constraints into
validation. At **spec** level that is proven. At **code** level it is not, and the test that
appeared to prove it proved nothing.

### What the old test actually did

```python
result = runner.invoke(app, ["implement", "specs/test.md", "--project", str(cwd)])
assert result.exit_code in (0, 1)
```

The path was relative while the project lived in `tmp_path`, so the CLI exited 1 on
`Error: Spec not found: specs/test.md` — and `in (0, 1)` accepted it. The implement pipeline was
never entered, let alone a DAL decision reached. Its docstring read *"Implement CLI triggers strict
code handler DAL overrides successfully failing."*

### What IS proven today — measured, so the gap is not overstated

| Link | Proof |
|---|---|
| A DAL declaration resolves up the tree | `test_dal_resolver.py`, `test_dal_merge.py` (unit) |
| The runner injects `dal_level` into `context.isolation` | `test_runner_dal_injection.py` — 3 integration tests asserting `DAL_A`/`DAL_D` and `is_strict` |
| `dal_level` is forwarded to the hydrator | `test_validation_hydrator.py::test_dal_level_forwarded_to_hydrator` (unit, mock-asserted) |
| Strictness changes the verdict at **spec** level | `test_validation_dal_enforcement.py` (2 e2e) and `test_dal_e2e_pipeline.py` (4 e2e, rewritten 2026-08-13) |

### The gap

**No test drives generated code through `execute_validation_flow(..., dal_level=...)` and shows the
verdict change.** Every link in the chain is tested in isolation and the chain itself is not — the
unit forwards, the integration injects, the e2e proves the *other* (spec) path. This is
`TECH-017`'s thesis restated: the units prove the units, and the seam is where nobody looked.

It cannot be closed the cheap way. `sw implement` reaches the LLM before any code-level enforcement
can run, so proving it needs a **scripted adapter** — the shape `test_feature_decomposition_e2e.py`
already builds (`ScriptedLLM`, with `ModelRouter.get_for_task` patched to `None` so the router
cannot construct a live provider around the factory patch).

## Candidate Approaches (not yet designed)

1. **Scripted-LLM e2e, mirroring the spec-level proof.** One generated module, two runs: under a
   lenient DAL it passes with warnings, under `DAL_A` the identical code fails. The **lenient
   control is the load-bearing half** — without it a regression that failed all generated code
   under any `context.yaml` would look correct. This is exactly how the spec-level proof was
   rebuilt on 2026-08-13, and the DAL_E control there is what makes it mean *strictness* rather
   than *bound*.
2. **Integration-tier test on the handler**, calling the code-validation handler directly with a
   fixed source file and each DAL. Cheaper and needs no LLM, but it skips the `sw implement`
   journey the claim is about — and shipping that instead of (1) would repeat the substitution
   this ticket exists to correct.
3. **Both**, with (2) as the fast guard and (1) as the contract proof.

`ScriptedLLM` is currently private to one e2e module. If (1) is chosen, decide whether to lift it
into a shared fixture — a second copy is what `TECH-037`'s duplication ratchet exists to prevent.

## Non-Goals (proposed, pending design)

- The spec-level DAL path — proven, twice.
- Making `sw implement` runnable without an LLM.
- The relative-path behaviour of `--project` (`spec_path = Path(spec)` resolves against cwd, not
  the project). That is what made the old test hollow, but whether it is a defect or the intended
  CLI convention is a separate question and must not ride along here.
- `TECH-017`'s wider audit.

## Adjacent, recorded because it will otherwise be rediscovered

The spec-level DAL claim now has **two** proofs: `test_validation_dal_enforcement.py` (pre-existing,
2 tests) and `test_dal_e2e_pipeline.py` (rewritten 2026-08-13, 4 tests). The overlap is real but
harmless, and consolidating it is not this ticket's job — noted so a future reader does not read
the duplication as an accident.

## Next Step

Run the `specweaver-design` skill against this stub before any implementation.
