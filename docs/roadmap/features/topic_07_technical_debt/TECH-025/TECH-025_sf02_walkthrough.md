# Walkthrough: TECH-025 SF-02 — Test Naming Closure

- **FRs**: FR-6 (renames + references), FR-7 (widen R5, delete the allowlist)
- **Commit boundaries**: 2

---

## CB-1 — widen R5, delete the allowlist (2026-08-08)

### What changed and why

`check_conventions.py` R5 already forbade registry IDs in test filenames, and already carried an
allowlist of six e2e files with a note saying every one of them *should* be renamed but could not be
without "a ticket that decides both halves together". Two limits kept three further offenders
invisible: the rule inspected paths under `tests/e2e/` only, and its pattern had no `_sf<N>`
alternative. So two integration files and one unit file were never candidates.

| File | Change |
|---|---|
| `scripts/check_conventions.py` | `check_e2e_naming` → `check_registry_ids_in_names(path, repo_root=…)`; covers all of `tests/`; `_sf_?\d` added; class and function names checked via `ast`; `_snake()` added; `LEGACY_E2E_NAMES` deleted; R5 documented in the module docstring for the first time |
| `tests/unit/scripts/test_check_conventions.py` | `TestE2ENaming` → `TestRegistryIdsInNames`; three assertions inverted or retired; 14 tests added |

### The two constraints that shape the rule

- **Names only — never docstrings or comments.** A single trailing `Proves: TECH-NNN FR-N` tag is
  the one sanctioned place a registry ID may appear in a test, and `check_fr_coverage.py` reads it.
  Scanning docstrings would set the two gates against each other and make the citation convention
  impossible to satisfy. Pinned by `test_a_registry_id_in_a_docstring_is_not_flagged`.
- **Validation rule IDs are not registry IDs.** `c05` names a shipped module
  (`c05_import_direction.py`), so `test_c05_architecture_integration.py` *is* named for its subject.
  Ten files depend on this. A looser `[a-z]\d{2}` pattern flags all ten, and the reflex fix is a
  fresh allowlist — which is precisely how the allowlist this commit deletes came to exist. Pinned
  at filename level and, after U1, at class level too.

### Three assertions changed, not two

The plan predicted two. There were three:

| Test | Was | Now |
|---|---|---|
| `test_the_rule_does_not_reach_outside_e2e` | alembic file **not** flagged | flagged — renamed for what it now proves |
| `test_a_legacy_name_is_not_flagged` | legacy name **not** flagged | flagged |
| `test_the_legacy_list_covers_exactly_todays_offenders` | allowlist matched the offenders | **retired** — nothing left to keep in step with. Its replacement, the whole tree as the assertion, lands in CB-2 because it cannot pass until the renames do |

### A precedent deliberately overruled

`test_the_rule_does_not_reach_outside_e2e` carried the justification *"The alembic migration test
names a revision, which IS its subject."* The repo held that a revision hash was a legitimate name.
Q6 overrules it: a hash is as meaningless to a future reader as a ticket id, the migration is still
loaded by that id inside the test, and it is the only file in `tests/unit/alembic/`. Recorded rather
than silently flipped.

### Results

| | |
|---|---|
| `tests/unit/scripts/` | **368 passed** |
| Boundary gate | `tests.py cb TECH-025 --kind tooling` — ok, DAL-C |
| Full suite | **6283 passed, 19 skipped** |
| Quality gate | 9 of 12 pass |

**`conventions` is red by design — that is CB-1's deliverable.** 11 violations across 1019 files:
the 9 files in the rename table (one each) and `test_exclusions.py` twice for its two `_sf4`
function names. Zero false positives: the 10 rule-ID files pass, and so do all 954 unit-test classes
despite CamelCase normalisation. CB-2 turns it green.

`complexipy` and `cycles` remain chronic; neither offender list contains a file this boundary
touched. Both belong to TECH-023 and TECH-024.

### Probes (mandatory) — three run, all restored, zero residue

| Probe | Expected red | Actual |
|---|---|---|
| Bypass `_snake()` | class-name test only | exactly that, 53 green |
| Narrow the rule back to `tests/e2e/` | the 5 tier-widening and symbol tests | exactly those, 49 green |
| Drop `_snake()`'s letter→digit split | the 4 non-trivial `_snake` cases + class-name test | exactly those; idempotence and empty correctly unaffected |

The second matters most: it proves the widened scope is load-bearing rather than incidental.

### HITL gates

| Gate | Decision |
|---|---|
| Plan Phase 4 | Nine names approved as written; Q2–Q7 proposals accepted |
| Plan Phase 5 | Approved; two boundaries kept, CB-1's red intended |
| Dev Phase 2 | Option **A** — commit CB-1 with a red `conventions` check |
| Pre-commit Phase 2 | U1 approved after challenging *why the test and not the filenames* — answered: `c05` names a shipped module, so those ten files are already named for their subject |

### Open for the reviewer

1. **One commit lands with a red `conventions` check.** Deliberate and approved; CB-2 clears it.
2. `complexipy` / `cycles` chronic, owned by TECH-023 / TECH-024.
