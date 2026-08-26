# Walkthrough: `B-SENS-03` SF-01 CB-1 — the net, before anything moves

- **Story**: `B-SENS-03` SF-01, commit boundary 1 of 3 · **DAL-B** · 2026-08-26
- **Serves**: `NFR-5` (backward compatibility). No FR is claimed here — this boundary changes no
  behaviour and touches **no file under `src/`**

## What this boundary is for

CB-2 and CB-3 rewrite how ten parsers decide whether a symbol is visible. `NFR-5` says the
`["public"]` set may not move except where the user agreed it should. The only way to prove a
*must-not-change* claim is to capture the answer first and compare afterwards, so this boundary
captures it.

## Why there is no red, and what stands in for one

Every test here is **green on its first run**. That is the requirement's shape, not a shortcut: a
test written to fail would be testing a different claim. So the usual protection is unavailable and
this file's validity rests on **probes** — the behaviour is neutralised and the net must object.

**Eight probes, eight kills.** One per place a filter actually lives, because `_reading.py` covers
only four of the ten parsers:

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

**P1 names neither markdown nor SQL, and that is correct**: neither hides anything, so the shared
branch cannot change their answer. There is no behaviour there to protect.

**P2 is the load-bearing one.** It is the only probe that reaches the integration test, which is
what proves the seam into `context.yaml` is genuinely covered rather than assumed.

## What the capture found

Six wrong answers, all pinned as-is. A net that quietly corrects what it measures cannot show a
diff, so each carries its reason beside it:

| Language | Pinned | Why it is wrong |
|---|---|---|
| Python | `Store.__mangled` **is in the public set** | name-mangled specifically so outsiders cannot reach it. This set writes the generated `context.yaml` `exposes:` list |
| Java | `Shape.area`, `Shape.name` **absent** | implicitly public by JLS. "No modifier" is right for a class and wrong for an interface |
| Rust | trait members absent | same cause. Separately, `Shape.area` is missing from the **unfiltered** listing too and `name` arrives unscoped — SF-03 `FR-18` |
| TypeScript | `private` and `protected` members **in the public set** | only checks whether an ancestor is exported; never reads a member's modifier |
| C | **empty for every request** | `return visibility is None` — any filter answers with silence |
| SQL | `public`, `orders` as two symbols | qualified names torn in half — SF-03 `FR-7` |

**C++ is the reference and already correct**, including failing *closed* on a nonsense level. It has
carried `_get_symbol_visibility(name_node) -> str` and a `name_node is None` guard all along —
which is the exact shape CB-2 promotes to the base, and independent confirmation that the plan's
`None` guard is required rather than defensive.

## The gap the plan did not have

`_is_symbol_valid` answers **two** questions — visibility *and* `decorator_filter` — and CB-3
deletes four copies of it. The decorator half was pinned nowhere.

Measured before adding anything: **C raises on purpose** (`c/codestructure.py:84`) and **Go returns
nothing on purpose** (`go/codestructure.py:129`). Both are deliberate, both undocumented elsewhere,
and both sat inside functions the next boundary removes. Twenty-one assertions and probes P6–P8
now hold them.

Found by the pre-commit Phase 2 gap analysis. The plan did not have it.

## Two of my own mistakes, caught by the process rather than by me

1. **A guess in a characterization test.** The first draft predicted C would treat `visibility=[]`
   like the other eight. It does not — `visibility is None` reads an empty list as *a filter was
   requested* and drops everything. The test failed on its first run and the measured value replaced
   the guess. Three behaviours from one input, which is itself an argument for one shared filter.
2. **Comparing the unit with itself.** `test_both_filters_together` asserted that
   `list_symbols(visibility, decorator_filter)` equals `list_symbols(decorator_filter)` — which
   passes whenever both halves break the same way. That is pattern 7 in `test-quality.md`, and the
   Phase 7.5 review of this file found it. Now asserted against literals.

## Results

| Check | Result |
|---|---|
| Full suite | **8,515 passed, 11 skipped** in 87 s |
| `tests.py cb B-SENS-03` | unit `scope=all` ok · integration `scope=module` ok |
| `quality.py cb` | 14 passed, 1 skipped |
| `quality.py doc` | 13/13 · `tach` ✅ · `mypy` clean on both new files |
| New tests | 118 unit + 5 integration |

**`ruff format` fired twice**, both times on a test file, exactly as the dev skill warns. `ruff
check` was clean while `ruff format --check` was not — they are separate gates.

**R6 test-class naming fired once.** Five classes named for behaviour rather than for
`list_symbols`; the ratchet caught the rise from 9 to 12 and they were renamed.

## Not done here, and named

- No `src/` file changed. `FR-1`–`FR-4` are CB-2 and CB-3
- The six wrong answers stay wrong until CB-3, and four of them are the deltas already agreed
- Rust's lost trait names and SQL's torn ones are **SF-03**, not this sub-feature

## Why no mutation campaign was written here

The pre-commit skill says a boundary that calls a claim proven writes it into the durable corpus.
Not this one, deliberately: **P1–P8 anchor on lines CB-3 deletes.** Eight campaigns pinned now
would report `STALE` two boundaries later, and a corpus that rots on schedule teaches people to
ignore drift reports. The claims are real and the campaign is owed — it is written when the shape
is final, at the end of CB-3, against the one filter that survives.
