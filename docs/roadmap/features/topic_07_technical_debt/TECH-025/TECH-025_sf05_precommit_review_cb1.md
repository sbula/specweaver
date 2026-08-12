# [Skill: specweaver-pre-commit] Phases 1–2 Combined Review — TECH-025 SF-05 CB-1

- **Boundary**: CB-1 — the two absence invariants. Ledger deliberately still RED.
- **Changed**: `tests/unit/test_layer_import_isolation.py` (NEW, 11 tests) ·
  `tests/unit/test_architecture.py` (scanner generalised)
- **`src/` touched**: none. Layer-placement, archetype and stability-direction rules are N/A.

---

## Phase 1 — Architecture Findings

### A1 — Repo-wide import cycles (PRE-EXISTING, owned by `TECH-024`)

`check_coupling.py --cycles-only` exits 1, reporting cycles including
`specweaver.interfaces.api.v1.ws`. **Verified pre-existing**: `git stash -u` to a clean HEAD
produces the identical report, so this change neither introduces nor worsens it.

Already registered as `TECH-024` (Repo-Wide Dependency Cycles), which the roadmap sequences at #6
*after* `TECH-020` and `TECH-015` reshape the import graph. Per §1.8 this is **recorded, not fixed**
— fixing it here would take a measurement `TECH-024` owns and make it unattributable.

**Recommendation: no action.**

### A2 — This change imports a *test module*, where precedent is a *fixtures helper* ⚠️ MINE

`test_layer_import_isolation.py` does:

```python
from tests.unit.test_architecture import SRC_ROOT, import_offenders
```

Every other cross-file test import in the repo points at a **fixtures helper**, not a test module:

```
tests/unit/core/flow/engine/test_router_integration.py:20   from tests.fixtures.db_utils import ...
tests/unit/interfaces/api/v1/test_pipelines.py:17           from tests.fixtures.db_utils import ...
tests/unit/core/config/test_settings_db.py:13               from tests.fixtures.db_utils import ...
tests/unit/core/config/test_dal_merge.py:6                  from tests.fixtures.db_utils import ...
```

`tests/fixtures/` exists, has an `__init__.py`, and is exactly this: the home for logic shared
between test modules. Importing a test module instead has two costs beyond style — it executes that
module's collection-time code as a side effect of the import, and it couples two suites so that
renaming `test_architecture.py` breaks a file that has nothing to do with it.

The Red/Blue review chose "scanner stays in `test_architecture.py` and is imported" while solving a
different problem (keeping the story name out of this file). **Moving the scanner to
`tests/fixtures/` satisfies that constraint equally well** — a fixtures module names no story — and
also follows precedent.

> **Options for the gate:**
> **(a) Move `import_offenders` to `tests/fixtures/arch_scanners.py`.** Both test modules import it.
> Follows precedent, removes the test-module coupling. Cost: one more file, and
> `test_architecture.py` gains an import.
> **(b) Keep as-is.** Justify in the docstring that the scanner is architecture-test infrastructure
> and belongs beside the other scanners. Cost: the only test-module import in the repo.
>
> **Recommend (a).** The precedent is unanimous (4 of 4) and the cost is one file.

---

## Phase 2 — Test Gap Analysis

### Coverage matrix — `import_offenders(root, prefixes, *, recursive)`

| Behaviour | Covered by | Bucket |
|---|---|---|
| Clean tree reports `[]` | `test_an_unrelated_import_is_not_reported` | Happy |
| Live: validation layer clean | `test_validation_layer_does_not_import_the_sandbox` | Happy |
| Live: interfaces layer clean | `test_interfaces_layer_does_not_import_the_sandbox` | Happy |
| `from x import y` detected | `test_a_planted_import_is_detected` | Hostile |
| `import x` detected (different AST node) | `test_a_plain_import_statement_is_detected_too` | Hostile |
| Deferred import inside a function detected | `test_a_deferred_import_inside_a_function_is_still_an_offender` | Hostile |
| `recursive=True` finds nested offender | `test_recursion_finds_an_offender_in_a_nested_package` | Boundary |
| `recursive=False` does **not** | same test, second assertion | Boundary |
| Non-recursive caller unchanged | `test_config_submodule_packages_are_out_of_scope` (FR-7, untouched) | Regression |
| Unparseable module raises, names the file | `test_an_unparseable_module_raises_instead_of_being_skipped` | Degradation |
| Missing root reports clean (the trap) | `test_a_nonexistent_root_reports_clean_...` | Degradation |
| Roots actually exist and hold modules | `test_the_scanned_roots_exist_and_contain_modules` | Guard |
| This file's citation footprint | `test_this_module_carries_only_the_tokens_it_earns` | Guard |

**Probed, not assumed.** Mutating the scanner to `glob("*.py")` (dropping recursion) turns the
suite red — 2 failures — so the recursion assertions are load-bearing rather than decorative.

**The self-guard proved itself twice during development**, which is the strongest evidence it works:
the first version spelled its two expected ids out in the assertion and failed reporting four tokens;
the second failed again on a comment that quoted them while explaining the first failure. Both were
real instances of the defect the guard exists to catch, caught by the guard.

### Gaps found

| # | Gap | Severity | Recommendation |
|---|---|---|---|
| **G1** | `prefixes` is never exercised with **more than one** entry. Both live callers pass a 1-tuple; `DOMAIN_PREFIXES` has 6, but that path is only covered indirectly by FR-7's probes, which predate the refactor | MEDIUM | **Add a test.** The parameter became a real degree of freedom in this change and nothing pins its multi-value behaviour |
| **G2** | An **empty** `prefixes` tuple. `str.startswith(())` is always `False`, so the scanner would report clean for every file — a silent vacuous pass if a caller ever computes prefixes dynamically | MEDIUM | **Add a test** asserting the empty tuple finds nothing, so the behaviour is chosen rather than inherited from `str.startswith` |
| **G3** | A **relative** import (`from . import x`) sets `node.module` to `None` → `""`. Handled by the `or ""`, but untested | LOW | **Add a test.** Cheap, and the docstring makes a claim about relative imports that nothing verifies |
| **G4** | A **non-UTF-8** module raises `UnicodeDecodeError`, not `SyntaxError`. The docstring promises the path is named on failure; that promise holds only for parse errors | LOW | Either widen the handler or narrow the docstring. Prefer narrowing — a non-UTF-8 source file is a different problem |
| G5 | The two live invariants assert `== []` but do not assert the scan *saw* files. Deliberate — that is the guard test's job, kept in one place per `test-quality.md` pattern 8 | — | No action. Noted so a reviewer does not re-raise it |

### Test tier

Unit tier is correct here: `TECH-025` is a `tooling`-kind TECH ticket, not an `INT-US-NN`
integration contract, so `TECH-017`'s tier-ratio rule does not apply. The two live invariants read
the real `src/` tree, which is what makes them meaningful; everything else is synthetic and touches
`tmp_path` only.

---

## Decisions needed at this gate

1. **A2** — move the scanner to `tests/fixtures/arch_scanners.py` (recommended), or keep the
   test-module import with a justification?
2. **G1–G4** — which gaps to close before the commit? Recommend **G1 and G2** (both MEDIUM, both
   about a parameter this change introduced) and **G3** (three lines). **G4** is a docstring edit.
