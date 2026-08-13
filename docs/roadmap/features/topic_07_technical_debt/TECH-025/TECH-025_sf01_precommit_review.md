# [Skill: specweaver-pre-commit] Phases 1–2 Combined Review — TECH-025 SF-01 CB-1

Comment inline under any row. Nothing proceeds to Phase 3 until you reply.

---

## Part 1 — Architecture Findings (deferred from Phase 1)

**No violations found.** Evidence rather than assertion:

| Check | Result | Evidence |
|---|---|---|
| Layer placement | N/A | Zero files under `src/specweaver/` changed. `git status` shows only `scripts/` and `tests/unit/scripts/` |
| `consumes` / `forbids` | N/A | `scripts/` has no `context.yaml`; it is build tooling, not a bounded context |
| Archetype compliance | N/A | Same reason |
| Dependency direction | Clean | `tach check` → `All modules validated!` |
| Circular imports | Clean | No `import` statement added. `is_fixture_data` uses stdlib `str.splitlines` only |
| Architecture invariants | Pass | `tests/unit/test_architecture.py` — 4 passed |
| Parallel mechanisms (1.4 zoom-out) | Follows precedent | A per-file tooling marker is an existing idiom here (`# mypy: ignore-errors`, `# ruff:` pragmas at file top). The alternatives in this repo are an allowlist (`check_conventions.LEGACY_E2E_NAMES`) or a count ratchet (`scripts/baselines/suppressions.json`); neither expresses "this file's data is not a claim". No duplication |
| Stability direction | N/A | No module dependency added |

> Comment:

---

## Part 2 — Coverage Matrix

**Module: `scripts/check_fr_coverage.py`**

| Class / Function | Unit | Integration | E2E |
|---|---|---|---|
| `FIXTURE_DATA_MARKER` (constant text) | ✅ | — | — |
| `is_fixture_data()` | 🟡 | — | — |
| `cited_frs_in_tests()` (new skip branch) | ✅ | 🟡 | — |

**Module: `scripts/tests.py`**

| Class / Function | Unit | Integration | E2E |
|---|---|---|---|
| `_src_relative()` | 🟡 | — | — |
| `paths_for()` (module + touched scopes) | ✅ | — | — |

**Module: `tests/unit/scripts/test_check_fr_coverage.py`** *(marker applied — the change is one line of data, matrix required regardless)*

| Change | Unit | Integration | E2E |
|---|---|---|---|
| Fixture-data marker present and effective on the real file | ❌ | 🟡 | — |

> Comment:

### Why the 🟡 / ❌ cells are what they are

- **`is_fixture_data()` 🟡** — seven unit tests cover recognised / unrecognised / empty / in-window /
  past-window / prefix-collision. Two branches of the `line.strip()` behaviour are unexercised
  (stories U1, U2).
- **`cited_frs_in_tests()` integration 🟡** — proven against `tmp_path` trees, never against the real
  `tests/` tree. The end-to-end claim ("INT-US-21 still closes, counts drop") was verified **by
  hand** this session, not by a test. Per the design that permanent guard is SF-07's manifest, so
  this is a *scheduled* gap, not an unowned one. Story I1 closes the cheap half now.
- **`_src_relative()` 🟡** — the three new cases are covered, but a nested `scripts/<pkg>/x.py` has undefined-by-test behaviour (story U3).
- **Marker-applied ❌** — nothing asserts the marker is actually present on
  `test_check_fr_coverage.py`. Delete that one line and every test in this boundary still passes;
  only the manual ledger check would notice. This is the weakest point in the change (story I1).

### Vacuous-proof check (§2.5b)

Executable half: `quality.py cb --only useless_asserts,test_basenames` → **2 passed, repo-wide.**

Manual half — every test relied on was read, not name-matched:

| Pattern | Verdict |
|---|---|
| 1 Ambiguous exit code | Absent. Assertions are on returned dicts, not process codes |
| 2 Stubbed-away subject | Absent. `cited_frs_in_tests` runs for real against real files on disk |
| 3 Never executed | Absent. All 12 ran (10 failed before implementation, confirming they execute) |
| 4 Inert fixture input | **Checked explicitly** — the `_fr()` helper runs at test time, so files written to `tmp_path` contain real `FR-2` text. Confirmed by the probe: the assertions moved when the source branch was disabled, which is only possible if the fixture reaches the code |
| 5 Escaped mock | N/A — no mocks, no network |
| 6 Assertion weaker than the name | Absent. `test_marker_skips_only_the_marked_file` asserts the whole returned dict by equality, not just membership |
| 7 Self-referential expectation | **Live risk, handled.** Tests build fixtures from `mod.FIXTURE_DATA_MARKER`. `test_the_marker_constant_matches_the_documented_text` pins the literal text separately, so renaming the marker is a visible decision rather than a silently-passing refactor |

**Probe (mandatory, performed):** replaced the skip with `if False`. Exactly
`test_marked_file_contributes_no_citations` and `test_marker_skips_only_the_marked_file` went red;
the other 10 stayed green — including the control, which is the point. Restored; residue check for
`PROBE` / `if False` returns clean; 345 tests pass in `tests/unit/scripts/`.

> Comment:

---

## Part 3 — Proposed Test Stories

### Unit

| # | Story | Target | Source Line |
|---|---|---|---|
| U1 | [Boundary] An indented marker — decide and pin whether column 0 is required | `is_fixture_data()` | `check_fr_coverage.py:114` |
| U2 | [Hostile] The marker quoted inside a module docstring within the window must not exempt the file | `is_fixture_data()` | `check_fr_coverage.py:114` |
| U3 | [Boundary] A nested `scripts/<pkg>/x.py` resolves predictably (mirror absent ⇒ selects nothing ⇒ gate blocks) | `_src_relative()` | `tests.py:387` |

### Integration

| # | Story | Target Seam | Source Lines |
|---|---|---|---|
| I1 | [Happy Path] The checker's own test file is fixture data **on the real tree** — reads the actual file and asserts the predicate is True, plus a sibling in the same directory asserting False | file on disk → `is_fixture_data` | `check_fr_coverage.py:108-117` |

### E2E
None proposed. There is no user-facing workflow here; `check_fr_coverage.py` is invoked by the
`specweaver-feature` closure gate, and the real-tree behaviour is covered by I1 now and SF-07's
manifest guard permanently.

### §2.5a Mandatory challenge — is this set sufficient?

**U1 and U2 are one decision, not two tests.** `line.strip() == MARKER` currently accepts an
indented marker. That is what makes U2 possible: a module docstring in the first 10 lines that
*quotes* the marker would silently exclude a genuine proof file — the precise failure mode the
marker's own comment warns about, and one that fails **silently**, the worst kind here. Requiring
column 0 (`line.rstrip() == MARKER`, no leading space) kills U2 outright and makes U1's answer
explicit.

**I1 is the one I care most about.** Without it, the marker line on `test_check_fr_coverage.py` is
unprotected: deleting it breaks nothing any test can see. Everything else in this boundary would
still be green while the defect quietly returned. It is ~8 lines and needs no story ID.

**U3 is cheap and I'd take it**, but it pins behaviour rather than fixing a risk.

**Deliberately not proposed:** a test asserting INT-US-21's ledger stays closed. It cannot be
written without naming that story alongside an `FR-N` token, which would re-credit it — the defect
under repair. That belongs in SF-07's manifest, where the story ids live in data instead of source.
Recorded here so the absence is a decision, not an oversight.

> Comment:

---

## My recommendation

Implement **U1+U2 (as the single column-0 change), I1, and U3** in Phase 3. Total ≈ 25 lines of test
plus a one-token source change. I1 is the only one closing a real hole; the rest harden a predicate
that is about to be trusted by three more sub-features.

> Comment:
