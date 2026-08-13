# Design: Duplicated Code Is Found Only By Accident

- **Feature ID**: TECH-037
- **Epic**: Topic 07 (Technical Debt)
- **Status**: **DELIVERED 2026-08-13.** `scripts/check_duplication.py` + `scripts/baselines/duplication.json`,
  wired into `quality.py` at `cb`/`sf`/`feature`. Baseline frozen at **148 clones**. Both
  §Preconditions settled — see §Delivery. Not run through `specweaver-design`: the tool comparison
  and the baseline were already measured on the ticket.
- **Origin**: 2026-08-12. Raised by the user after `TECH-023` batch 7 and `TECH-035` each turned
  out to be duplication findings wearing a complexity or cohesion label.

## Problem Statement

**There is no duplicate-code check in this repo** — not in `scripts/`, not in any `quality.py`
gate, and not available from the linter already installed (see §Tool selection). Every duplication
fixed in the 2026-08-12 session was found **by accident**, while reading code for an unrelated
reason:

| Found | Size | Found while |
|---|---|---|
| `_is_symbol_valid` ×4 (three **byte-identical**) | ~22 lines each | resolving `TECH-035`'s LCOM4 |
| `log_artifact_event` tail ×7 | ~10 lines each | `TECH-016` §2 |
| `_build_run_context` ×2 | ~40 lines | `TECH-023` batch 7 |
| artifact-tag reading ×3 (one file) | ~7 lines each | `TECH-023` batch 7 |
| `_maybe_bootstrap_constitution`'s two branches | 4 statements | `TECH-023` batch 7 |
| `add_symbol` append-at-end ×3 | ~6 lines each | `TECH-035` |

Not one was reported by a gate. Two of them were **live defects**, not merely repetition: the
hand-rolled artifact-tag reader matched only hash-comment syntax, so `sw lineage tree spec.md`
silently resolved nothing; and `lint_fix.py`'s copy of the lineage tail was the one of seven
missing its `None` guard (`TECH-036`).

## Measured, 2026-08-12

`jscpd@4 --min-tokens 50 --format python` over `src/`, stable across three runs with a fresh
output directory:

```
150 clones   2168 / 54448 lines = 3.98%   20229 / 368629 tokens = 5.49%   333 files
```

Duplicated lines by package — the two clusters are not evenly spread:

```
629  workspace/ast        325  core/flow        194  infrastructure/llm
193  sandbox/language     168  interfaces/api   139  workflows/drafting
```

**The sharpest single example.** `_format_replacement` is **character-for-character identical**
across **six** parsers — `go`, `java`, `kotlin`, `python`, `rust`, `typescript`. Not "structurally
similar": the same six lines, constants included. `_format_body_injection` is identical across
four. These are the same `workspace/ast` cluster `TECH-034` left behind and `TECH-035` had to
exempt `Go` and `Sql` over, so clearing them is likely to close those two exemptions as a side
effect — exactly as hoisting `_is_symbol_valid` closed four.

## Candidate Approaches — tool selection, decided by measurement not preference

**`ruff` cannot do this.** Verified against its rule list: 115 Pylint rules are implemented and
`R0801` (duplicate-code) is **not** among them; the only name-match is `duplicate-bases`
(`PLE0241`), an unrelated check.

**`jscpd` + a content-key ratchet is the choice.** jscpd's JSON emits a `fragment` field — the
duplicated source text — so a ~25-line wrapper can key each clone on
`sorted(file pair) + sha1(fragment)`. That is **line-independent**, which is the property a ratchet
needs. Proven, not assumed:

| Probe | Result |
|---|---|
| Unchanged tree | 150 clones, none new — exit 0 |
| **12 comment lines inserted at the top of a clone's file** | 150 clones, **none new** — exit 0 |
| A 7th copy of the 6-way `_format_replacement` planted | **NEW clones (1)**, named with file pair and size — exit 1 |

> **A rejected alternative, recorded because the first recommendation was wrong.** A stdlib AST
> checker keyed on `file::qualname` was prototyped and initially preferred, on the reasoning that
> jscpd "can only ratchet an aggregate percentage". **That reasoning was wrong** — it compared
> jscpd's `--threshold` CLI flag against a purpose-built ratchet, without reading jscpd's JSON.
> The AST prototype also has a blind spot jscpd does not: it compares whole functions, so a block
> duplicated *inside* two differently-shaped functions is invisible to it. jscpd finds those
> (e.g. `rust/codestructure.py:143-168` ↔ `typescript/codestructure.py:150-175`, 25 lines).
>
> The aggregate `--threshold` is separately unusable: the planted regression moved the total by
> **5 lines / 0.01pp**, so any commit that also removes ≥5 duplicated lines masks it. Batch 7
> alone removed a 40-line duplicate.

**Cost accepted:** a Node dependency in a Python repo's gate chain. `node` v24 and `npm` are
present, and `npx --offline` succeeds once the package is cached — but the first fetch needs
network, which the design must account for before this becomes a commit-boundary gate.

## Preconditions the design must settle

1. **Pin the measurement anomaly.** One invocation reproducibly reported **714 clones / 5.39%** on
   the same tree where three fresh-output-directory runs reported 150 / 3.98%. The cause was not
   isolated. The direction is safe — with a content-key ratchet an inflated run surfaces ~560
   "new" clones and **blocks loudly** rather than passing silently — but a gate whose count can
   vary 4.7× is not shippable until the cause is known.
2. **`--min-tokens` is load-bearing.** At 50 it reports 150 clones. Tuning it down will surface
   per-language parser code where the differing **constants are the point**; an AST scan with
   constants erased reported 63 groups against 31 with them kept. A check that reports on correct
   code gets suppressed — the `R-OWNER` lesson.
3. **Gate scope.** `quality.py`'s existing scopes are `changed` / `module` / `all`. Duplication is
   inherently cross-file, so a `changed` scope cannot see a clone whose twin was not touched —
   the same defect that hid `check_class_health` for a whole session.

## Non-Goals

- **Not `TECH-023`'s complexity reduction.** Measured, and this is the reason this ticket does not
  block it: only **5 of 31** remaining complexity violations contain any duplicated code, and for
  `core/flow` — batch 8's target — it is **1 of 9** (`ReviewCodeHandler::execute`, 42 of 79 lines).
  A duplication gate would not have driven batch 8.
- **Not** fixing the 150 clones. This ticket ships the *detector and the ratchet*; reduction is
  separate work, sequenced by cluster.
- **Not** replacing `check_complexity` or `check_class_health`. They measure different things, and
  this session showed all three can point at the same code for different reasons.

## Verification the design must specify

- The ratchet is probed by **planting a clone**, not by reading the checker — every guardrail this
  repo added without that probe turned out inert (`R-OWNER`, `-p no:randomly`, `check_class_health`,
  and twice more in this session).
- The probe must fail for the **right reason**: two probes this session failed on a stale import
  and on a scope artefact rather than on the defect, and looked convincing both times.
- A clone whose file gains unrelated lines must **not** register as new (the §Tool selection test B).

## Execution Constraint

Its own commits, never bundled into a feature commit. Land the detector and ratchet first with the
baseline frozen at whatever the pinned measurement says; reduce afterwards, one cluster per commit.

> **All three preconditions are settled** — see §Delivery. Precondition 1's anomaly was a missing
> path argument in the measuring command, not a defect in the tool.

## Delivery, 2026-08-13

`scripts/check_duplication.py` — jscpd detects, we ratchet. Wired into `quality.py` as
`duplication`, scope **`all`** at `cb`, `sf` and `feature`; deliberately absent from `quick`
because it shells out to `npx` and the inner loop should stay fast. Runs in **1.9 s**.

Baseline: **148 clones** frozen in `scripts/baselines/duplication.json`.

### Precondition 1 — the anomaly was mine, not jscpd's

The ticket blocked on a run that reproducibly reported **714 clones / 5.39%** where three others
reported 150 / 3.98%. Cause found: the shell function used to take that measurement was **missing
its `src/` path argument**, so jscpd scanned the whole repository. Reproduced deliberately:

```
with src/     148 clones   2128 lines   3.89%   333 files
without       712 clones   9676 lines   5.36%   895 files
```

Not a defect in the tool, and not a reason to distrust it. The 148/150 difference between then and
now is `TECH-023`'s reduction work removing real duplication in between.

### Precondition 2 — `min-tokens` stays at 50, and says why

Documented on the constant rather than left as a flag: below 50, jscpd reports import blocks and
boilerplate signatures, and tuning it down surfaces per-language parser code where the differing
**constants are the point** — the false-positive class that gets a check suppressed rather than
acted on.

### Precondition 3 — scope is `all`, always

Duplication is cross-file by definition: a clone's twin may sit in a file the commit never touched,
so a `changed` scope would report "nothing in scope" while the clone it exists to catch went in.
That is exactly how `check_class_health` stayed invisible for a whole session, and the reasoning is
recorded on the matrix entry so it is not narrowed later for speed.

### The key, and why not jscpd's own threshold

Each clone is identified by **its text plus the pair of files it spans**, whitespace-normalised and
order-independent. jscpd's `--threshold` compares an aggregate percentage and was rejected on
measurement: the planted regression moved it by 5 lines in 2168 — **0.01 pp** — so any commit that
also removed five duplicated lines would mask it, and `TECH-023` batch 7 removed forty in one.

### Verified by planting, not by reading

| Probe | Result |
|---|---|
| Clean tree | 148 clones, none new — exit 0 |
| A 7th copy of the 6-way `_format_replacement` planted | **exit 1**, named with both files and size |
| **15 lines inserted above an existing clone** | 148 clones, **none new** — exit 0 |

The third is the one a line-keyed baseline could not pass, and it is why the key is content.

**It cannot fail open.** A detector that will not start, an unreadable report, or a missing
baseline all exit **2** with "could not run", matching `quality.py`'s existing `MISSING` grade —
rather than reporting "no new clones" over a measurement that never happened. Three tests pin it.

### Two things the commit gate caught that I had missed

- **`ruff format --check` is a separate gate from `ruff check`.** Fifteen files across this
  session's work were unformatted; `ruff check` had been clean throughout. The `format` check at
  `cb` is what surfaced it.
- **`R6`** rejected the new test class names (`TestTheRatchet`, …) for not naming the function
  under test. Renamed to `TestCloneKey` / `TestNewClones` / `TestMain` / `TestLoadReport`.

`test_quality_runner.py`'s `EXPECTED` map — which pins the exact check set per gate so one cannot
be added or dropped silently — was updated deliberately for all three gates.

`6576 passed, 11 skipped, 0 failed`; `quality.py cb` **0 failed of 13**.

## Next Step

Reduction. The detector and ratchet are in; the 148 clones are now bounded rather than growing.
Largest cluster is `workspace/ast` (629 duplicated lines), and `_format_replacement` is
**character-for-character identical across six parsers** — clearing it should also close the `Go`
and `Sql` cohesion exemptions `TECH-035` had to record.
