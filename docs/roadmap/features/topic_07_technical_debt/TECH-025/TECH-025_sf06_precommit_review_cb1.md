# [Skill: specweaver-pre-commit] Phases 1–2 Combined Review — TECH-025 SF-06 CB-1

- **Boundary**: CB-1 — the two new invariants (`TECH-005 FR-4`, `FR-5`). Ledger deliberately RED.
- **Changed**: `tests/unit/test_table_naming_convention.py` (NEW, 9 tests). **No `src/` changes.**

## Phase 1 — Architecture

No source file touched, so layer placement, archetype and stability-direction rules are N/A.
`tach` ok. `complexipy` and `cycles` fail as always — `complexipy` scans `src/` only and nothing
under `src/` changed; `cycles` is `TECH-024`'s chronic 16. Recorded, not fixed, per §1.8.

**One placement judgement worth stating.** The two scanner helpers live in the test module rather
than `tests/fixtures/`. SF-05 CB-1's finding A2 moved a helper *out* of a test module — but that was
because **two** modules needed it, and importing a test module executes its collection-time code.
Only this module uses these, so keeping them local avoids an abstraction with one caller. If a
second consumer appears, A2's ruling applies and they move.

## Phase 2 — Test Gap Analysis

### Coverage matrix

| Behaviour | Covered by | Bucket |
|---|---|---|
| Bases register a non-empty table set | `test_the_declarative_bases_register_tables` | Guard |
| Every live table is prefixed (FR-4) | `test_every_model_table_carries_its_bounded_context` | Happy |
| No live raw SQL names a legacy table (FR-5) | `test_no_raw_sql_references_a_pre_rename_table_name` | Happy |
| Unprefixed name reported | `test_an_unprefixed_table_name_is_reported` | Hostile |
| Legacy name in SQL reported | `test_a_legacy_name_in_raw_sql_is_reported` | Hostile |
| `workspace_projects` **not** reported | `test_a_prefixed_name_containing_a_legacy_substring_is_not_reported` | Boundary |
| Prose/variable use not reported | `test_the_keyword_context_is_required` | Boundary |
| Unreadable module raises | `test_an_unreadable_module_raises_instead_of_being_skipped` | Degradation |
| Citation footprint | `test_this_module_carries_only_the_tokens_it_earns` | Invariant |

### Probed, not assumed

Both live invariants pass against a tree that is already correct, so neither had a natural red.
Mutation probes supply it:

```
plant `SELECT id FROM projects` into workspace/store.py   -> FR-5 test FAILS  (reverted)
inject an unrenamed `projects` into the workspace base    -> ['workspace: projects']
clean tree                                                -> []
```

### Gaps found

| # | Gap | Severity | Recommendation |
|---|---|---|---|
| **G1** ✅ | *Closed.* **Multi-line SQL is untested.** `_SQL_TABLE_CONTEXT` uses `\s+`, which spans newlines, so `FROM\n    projects` *should* match — but nothing proves it, and real query strings are frequently wrapped | MEDIUM | **Add a test.** This is the most likely real-world shape of a missed reference |
| **G2** ✅ | *Closed.* **Lowercase SQL is untested.** The regex sets `re.IGNORECASE`; both hostile tests use uppercase keywords. A future tightening of the pattern would silently stop matching `select … from projects` | MEDIUM | **Add a test** with lowercase keywords |
| **G3** | The `OSError` branch of the read is untested — only `UnicodeDecodeError` is | LOW | Low value: hard to provoke portably. Recommend leaving it and saying so |
| **G4** | `legacy_table_references` scans `src/` only. A legacy name in a **test** fixture would not be reported | LOW | Correct as scoped — FR-5 is about production queries. Noted so a reviewer does not re-raise it |

## Decisions needed

**G1 and G2** — both MEDIUM, both cheap, both about the regex this check depends on entirely.
Recommend adding them. G3 and G4: recommend recording and moving on.

## Resolution (user, 2026-08-12)

**G1 and G2 closed.** Two tests added: a reference split across lines with `FROM` on its own line,
and a fully lowercase statement.

Probed rather than assumed — tightening the pattern to `[ \t]+` and dropping `re.IGNORECASE` turns
**exactly those two** red and leaves the other nine green. Both were latent: every pre-existing
probe used uppercase keywords on one line, so the two properties the check depends on most were the
two nothing exercised.

**G3 and G4 recorded, not closed.** G3's `OSError` branch is hard to provoke portably and the
`UnicodeDecodeError` path already proves the raise-don't-skip behaviour. G4 is correct as scoped —
FR-5 is about production queries, so scanning `src/` only is the requirement, not a limitation.

11 tests. Unit tier 5604 passed / 1 failed (the deliberate `TECH-030` one). Ledger still RED as
CB-1 requires.
