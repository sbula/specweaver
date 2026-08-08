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

---

## CB-2 — renames and references (2026-08-08)

### What changed

Nine files renamed with `git mv` (history preserved), three test functions renamed, and 92
references moved across 36 files.

| Old | New | Distinguished by |
|---|---|---|
| `test_int_us_09_isolation_e2e.py` | `test_step_worktree_isolation_e2e.py` | ONE bash step bounded to a worktree |
| `test_c_exec_06_session_isolation_e2e.py` | `test_session_worktree_isolation_e2e.py` | MULTI-step run sharing one worktree |
| `test_int_us_03_isolation_e2e.py` | `test_implement_loop_worktree_isolation_e2e.py` | implement loop, DAL auto-escalation |
| `test_int_us_02_drafter_e2e.py` | `test_drafter_loop_e2e.py` | |
| `test_int_us_21_decomposition_e2e.py` | `test_feature_decomposition_e2e.py` | |
| `test_int_us_24_scenario_e2e.py` | `test_scenario_verification_e2e.py` | |
| `test_dispatcher_sf2_integration.py` | `test_dispatcher_domain_conformance.py` | |
| `test_dispatcher_sf3_integration.py` | `test_dispatcher_registry_delegation.py` | |
| `test_af60fd3509a2_tech_005_rename_tables.py` | `test_table_prefix_migration.py` | |

Functions: `..._ignores_sf4` → `test_scaffolded_ignore_file_contains_analyzer_default_dirs`;
`..._hidden_binary_sf4` → `test_compiled_spec_matches_analyzer_binary_patterns`;
`..._for_int_us_ticket` → `test_story_block_unaffected_for_a_multi_segment_id`.

### The sweep over-reached — and no gate caught it

A blind basename replace also rewrote **this ticket's own rename record**. The plan's
`Current | Proposed` table came out with both columns identical, and Research Notes R1/R3/R5 —
which exist to explain why the OLD names were invisible to the OLD rule — were rewritten into
nonsense.

Every test still passed. Every reference still resolved. The conventions gate was green. **It was
caught by reading the diff.** Both files were restored from `c34fefaa`, and only the two genuinely
live pointers in the design — where a proof actually lives — were re-applied by hand.

The distinction a future sweep must make: a reference that must **resolve** moves with the file; a
reference that **describes the state before the rename** must not. 33 old-name occurrences remain
inside TECH-025's own documents deliberately; a repo-wide search confirms **zero** anywhere else.

### `.claude/` and the positive control

`grep -r` returns zero inside the `.claude/` junction even when matches exist, so a clean result
there is meaningless on its own. The sweep walked it explicitly and searched for a string known to
be present: **6 files matched**, proving the walk reached the junction before any clean result was
believed.

### Results

| | |
|---|---|
| Boundary gate | `tests.py cb TECH-025 --kind tooling --all` — ok across unit, integration, e2e |
| Full suite | **6284 passed, 19 skipped** (6283 + T10; renames changed no behaviour) |
| `conventions` | **GREEN** — CB-1's deliberate red cleared |
| Quality gate | 10 of 12; `complexipy` and `cycles` chronic |

### T10 — the invariant that could only land now

`test_no_test_anywhere_in_the_tree_carries_a_registry_id` runs the rule over every file under
`tests/` and asserts an empty offender list, reporting path and reason on failure. It replaces the
retired allowlist-parity test: with no list to keep in step with, the tree itself is the assertion.
A new offender must now fail here rather than be absorbed into an exemption — which is exactly how
the allowlist this sub-feature deleted came to exist.
