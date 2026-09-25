# B-SENS-03 SF-01 CB-1 — Walkthrough

**Commit boundary:** CB-1 of 3 · **DAL-B** · 2026-08-26 · **Serves**: `NFR-5`. No FR; **no file
under `src/`** changed · Plan: [sf01](B-SENS-03_sf01_implementation_plan.md)

## Delivered

A regression net capturing what all ten parsers returned before CB-2/CB-3 rewrote visibility.
Every test is **green on its first run** — a *must-not-change* claim is proved by capture, then
compare — so validity rests on **probes**: neutralise the behaviour, the net must object.

Wrong answers pinned as-is, each with its reason beside it (a net that corrects what it measures
cannot show a diff):

| Language | Pinned | Why it is wrong |
|---|---|---|
| Python | `Store.__mangled` **in the public set** | name-mangled so outsiders cannot reach it; this set writes the generated `context.yaml` `exposes:` list |
| Java | `Shape.area`, `Shape.name` **absent** | implicitly public by JLS |
| Rust | trait members absent; `Shape.area` missing from the **unfiltered** listing and `name` unscoped | SF-03 `FR-18` |
| TypeScript | `private` and `protected` members **in the public set** | never reads a member's modifier |
| C | **empty for every request** | `return visibility is None`; `visibility=[]` also reads as *a filter was requested* |
| SQL | `public`, `orders` as two symbols | SF-03 `FR-7` |

**C++ is the reference and already correct**, including failing *closed* on a nonsense level, with
`_get_symbol_visibility(name_node) -> str` and a `name_node is None` guard — independent
confirmation that the plan's `None` guard is required.

**Decorator half pinned too.** `_is_symbol_valid` answers visibility *and* `decorator_filter`, and
CB-3 deletes four copies. **C raises on purpose** (`c/codestructure.py:84`), **Go returns nothing on
purpose** (`go/codestructure.py:129`); twenty-one assertions and probes P6–P8 hold both.

## Proof

**Eight probes, eight kills** — one per place a filter lives (`_reading.py` covers four of ten):

| # | Neutralised | Objections | Named this net |
|---|---|---|---|
| P1 | `_reading.py` visibility branch | 52 | java · kotlin · rust · typescript |
| P2 | `python/codestructure.py` visibility branch | 53 | python **+ 3 integration tests** |
| P3 | `go/codestructure.py` visibility branch | 48 | go |
| P4 | `c/codestructure.py` `return visibility is None` | 52 | 5 tests |
| P5 | `cpp/codestructure.py` `actual_vis not in visibility` | 54 | 6 tests |
| P6 | Go's `return False  # Go does not have decorators` | 48 | 2 tests |
| P7 | C's `raise CodeStructureError(...)` | 48 | 1 test |
| P8 | `_reading.py` decorator match | 67 | 7 tests |

P1 names neither markdown nor SQL — neither hides anything. **P2 is load-bearing**: the only probe
reaching the integration test, so the seam into `context.yaml` is covered, not assumed.

`test_both_filters_together` asserts `list_symbols(visibility, decorator_filter)` against literals, not against `list_symbols(decorator_filter)` —
comparing the unit with itself passes whenever both halves break alike (pattern 7 in
`test-quality.md`).

| Check | Result |
|---|---|
| Full suite | **8,515 passed, 11 skipped** in 87 s |
| `tests.py cb B-SENS-03` | unit `scope=all` ok · integration `scope=module` ok |
| `quality.py cb` | 14 passed, 1 skipped |
| `quality.py doc` | 13/13 · `tach` ✅ · `mypy` clean on both new files |
| New tests | 118 unit + 5 integration |

No mutation campaign here: P1–P8 anchor on lines CB-3 deletes, so campaigns would read `STALE` two
boundaries later. Written at the end of CB-3 against the surviving filter.
