# Walkthrough: TECH-025 SF-05 CB-2 — the ledger closes on citations that point at the right files

- **Feature ID**: TECH-025 / SF-05 (TECH-002 FR Ledger)
- **Date**: 2026-08-12
- **Boundary**: CB-2 of 2. CB-1 answered *is the claim true?*; this answers *is it linked?*

## Result

```
check_fr_coverage.py TECH-002   ->  exit 0
  6 FR(s) declared · 4 implementation plan(s) · 6 FR(s) cited by tests
```

The second of `TECH-025`'s three subject ledgers to close, after `TECH-001` in SF-04.

## What changed

| File | Change |
|---|---|
| `TECH-002_sf01..04_implementation_plan.md` | Requirement citations, under AD-4's waiver, with a dated note naming `TECH-025` as author |
| `test_sandbox_registry.py` | Per-class tags — `TestBaseTool` → FR-1, `TestToolRegistry` → FR-2, `TestBaseToolConformance` + `TestFacadeConformance` → FR-4 |
| `test_dispatcher_registry_delegation.py` | Module tag → FR-3 |
| `test_validation_hydrator.py` | Module tag → FR-5 (injection half) |
| `test_dispatcher_domain_conformance.py` | NFR-5 repair — registry ID removed from prose |
| `test_sandbox_registry.py` | NFR-5 repair — stale "TDD red-phase marker for SF-2" reworded |

Per-class rather than one module tag, matching `TECH-006`'s precedent in `test_base.py` (Q3, user).
Deleting a class now visibly drops its citation instead of leaving a module-level tag that still
claims it.

## The check that a count could not have made

The plan verified by exit code. CB-1's Red/Blue showed that cannot distinguish a real citation from
a borrowed one — TECH-002 going green *is* the goal, so both look identical. C4 replaced it with an
attribution check that reads the file list:

```
FR-1  OK  ['unit/sandbox/test_sandbox_registry.py']
FR-2  OK  ['unit/sandbox/test_sandbox_registry.py']
FR-3  OK  ['integration/sandbox/test_dispatcher_registry_delegation.py']
FR-4  OK  ['unit/sandbox/test_sandbox_registry.py']
FR-5  OK  ['unit/core/flow/test_validation_hydrator.py', 'unit/test_layer_import_isolation.py']
FR-6  OK  ['unit/test_layer_import_isolation.py']

every FR resolves to the file that proves it, none to test_architecture.py
```

FR-5 legitimately resolves to two files — the hydrator proves the injection half and CB-1's isolation
module proves the absence half, which is what that requirement claims.

## No credit leaked

Every target file was scanned before editing: none carried a pre-existing requirement token, and only
`test_dispatcher_domain_conformance.py` named a story — the NFR-5 violation this boundary removes.
It carried no token yet, so it had credited nothing; the plan's R6 called it correctly, and it is
fixed **before** it could pay out rather than after, unlike SF-04's `TECH-022` find.

Ledgers after, none moved but the intended one:

```
TECH-001 0 · TECH-002 0 (was 1) · TECH-005 1 · TECH-022 1 · TECH-025 1 · TECH-006 0
INT-US-21 0 · INT-US-24 0
```

`TECH-025`'s own ledger correctly stays red — SF-06 and SF-07 are outstanding.

## Gates

| Gate | Result |
|---|---|
| `check_fr_coverage.py TECH-002` | **exit 0** |
| Attribution by file list | 6/6 correct, none from `test_architecture.py` |
| The four touched test modules | 50 passed |
| `tests/unit` | 5593 passed, 1 failed |
| `tests/integration` | 578 passed, 13 failed |
| `tests/e2e` | 182 passed, 9 failed |
| `quality.py cb` | 10 passed; `complexipy` and `cycles` chronic (`TECH-023`/`TECH-024`) |

Run with `--all` rather than the default profile, which selects the unit tier only — this boundary
edits two files under `tests/integration/`, so the default would not have run the tier the change
lands in.

**Every one of the 23 failures is accounted for**: 18 are `TECH-029`'s `RLIMIT_NPROC` defect, 4 are
Cluster E tooling gaps, and 1 is `TECH-030`'s empty-grant divergence, left red on purpose. None is
this boundary's, and none moved.
