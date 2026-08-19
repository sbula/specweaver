# Implementation Plan: TECH-067

- **Feature ID**: TECH-067
- **Status**: DELIVERED 2026-08-19
- **Commit boundaries**: one

## CB-1 — carry the DAL the last call, and let it decide

| Task | FR | Change |
|---|---|---|
| T1 | FR-2 | `_validation_output` takes `strict` and folds WARNs into the failure count |
| T2 | FR-1 | `ValidateCodeHandler.execute` reads `context.isolation.dal_level` and passes it on |
| T3 | FR-1 | `_run_validation` forwards `dal_level` to `execute_validation_flow` |
| T4 | FR-2 | The integration test: same module, `DAL_E` passes, `DAL_A` fails, findings identical |

**T1 before T2/T3 on purpose.** Forwarding first would have produced a green build with nothing to
observe, which is the shape the ticket was filed to avoid.

**Two fixture traps, both recorded because they made assertions pass for the wrong reason.** A local
pipeline named `validation_code_default` that `extends: validation_code_default` self-references and
raises inside the fallback meant to catch it — the step then ERRORs, and "not PASSED" is satisfied. A
spec named `spec.md` makes C02 look for `test_spec.py` and FAIL, and any FAIL fails the step whatever
the strictness.
