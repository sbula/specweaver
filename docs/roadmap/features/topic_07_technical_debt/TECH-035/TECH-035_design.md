# Design: Chronically Failing Class-Health Gate

- **Feature ID**: TECH-035
- **Epic**: Topic 07 (Technical Debt)
- **Status**: **DELIVERED 2026-08-12.** Ratchet shipped, checker corrected, baseline re-frozen
  **19 incohesive + 1 oversized → 9 incohesive + 0 oversized**. Every one of the 9 has a stated
  reason below: **7 are `TECH-034`'s recorded residue and this ticket's explicit non-goal**, and
  **2 are reviewed exemptions**. See §Where the 19 went.
- **Origin**: Found 2026-08-12 during `TECH-023` batch 2. The gate fired for the first time in the
  session because that commit finally *changed* a file it covers — see "Why nobody had seen this".

## Problem Statement

`check_class_health.py` fails on a **clean tree**: **23 classes out of 397** when filed — 1
oversized and 22 incohesive; **20 of 400 after `TECH-034`**. Reproducible with:

```
python scripts/check_class_health.py src
```

Confirmed unrelated to any work in flight by running it against a stashed tree: identical output
with or without the changes applied.

### Why nobody had seen this

The gate's scope is `{"cb": "changed", "sf": "module", "feature": "all"}`. At a commit boundary it
only inspects files the commit touched, so **it is skipped entirely whenever a commit happens not
to touch one of the 23**. It had been reporting `skip class_health changed 0.0s nothing in scope`
for the whole session while 23 classes were failing.

That is the same shape as two other defects found this week — `R-OWNER` shipping inert, and
`-p no:randomly` being a silent no-op for a plugin that was never installed. **A check that
silently does not run is indistinguishable from a check that passes**, and all three were found by
accident rather than by the gate.

Whatever else this ticket does, that property deserves its own answer: a scope-gated check should
be able to say "I inspected nothing" loudly enough that a reader notices.

## The debt is mostly ONE design repeated, not 23 unrelated classes

| Group | Count | Classes |
|---|---|---|
| **AST parsers** | **11** | `BaseTreeSitterParser` (LCOM4=6), `TypeScript` (6), `Java` (5), `Kotlin` (5), `Cpp`/`Go`/`Markdown`/`Python`/`Rust`/`Sql` (4), `C` (3) |
| **Standards analyzers** | **3** | `PythonStandardsAnalyzer` (6), `JSStandardsAnalyzer` (5), `TSStandardsAnalyzer` (3) |
| Protocol parsers | 2 | `AsyncAPIParser`, `GRPCParser` — both split identically into `extract_endpoints` / `extract_messages` |
| Sandbox atoms | 3 | `FileSystemAtom`, `GitAtom`, `QARunnerAtom` — each splits its `_intent_*` handlers from `run` |
| Other | 4 | `TopologyGraph`, `RichPipelineDisplay`, `MCPExplorerTool`, `Task` (16 attributes — the oversized one) |

**11 of 23 are the AST parsers.** The remaining groups also cluster: two protocol parsers with an
identical split, and three atoms that each separate intent-dispatch from execution. So this is not
23 independent refactors — it is roughly **five** decisions.

> **Correction, 2026-08-12.** This section first claimed *"14 of 23 are one class per language — the
> AST parsers and the standards analyzers are the same pathology in two different packages"*, and
> put the 3 analyzers in this ticket's scope. **Both halves were wrong**, found while researching
> `TECH-034`:
>
> - The analyzers **already have the tier** this ticket would have proposed:
>   `StandardsAnalyzer` (ABC, contract = `extract_all`) → `TreeSitterAnalyzer` (88 lines) →
>   `JSStandardsAnalyzer` → `TSStandardsAnalyzer`. They arrived there independently and earlier
>   than the parsers did.
> - `PythonStandardsAnalyzer` sits outside that tier on **stdlib `ast`**, and should stay there.
>   `ast` ships with the language and tracks its grammar exactly; its regex use is only
>   `^[A-Z][a-zA-Z0-9]*$`-style naming-convention matching on identifier strings, which is the
>   correct use of a regex rather than parsing. Moving it onto tree-sitter would trade precision
>   for symmetry.
>
> The principle already in force there is the right one — **one contract, best parser per
> language** — so their `LCOM4` is a question about *those three classes*, not about a repeated
> design. **Do not refactor them toward uniformity on that reading.**

## Relationship to other tickets — read before starting

- **`TECH-034` took the 11 AST parsers — DELIVERED 2026-08-12.** Its paradigm split targeted
  exactly the incoherence `LCOM4` measures here, and the before/after is the evidence: language
  parsers flagged **10 → 7**, every remaining one at `LCOM4=2` (was 3–6), and C++/Python/C off the
  list entirely. **Do not refactor the language parsers here.** What it left behind is the base —
  see below.
- **The 3 standards analyzers are NOT the parsers' problem repeated** — see the correction above.
  They already have their own tier and a sound contract, so whatever is left in their `LCOM4` is a
  question about those three classes alone.
- **`BaseTreeSitterParser` is now the most incohesive class in the repo (`LCOM4=8`, was 6).**
  `TECH-034` concentrated the parsers' shared mechanics into it — a deliberate trade, since fixing
  one base beats fixing ten parsers. Its components are four distinct jobs (query, walk, edit,
  format). **This is the single highest-value target in this ticket**, and it also clears three of
  `TECH-023`'s remaining violations.
- **`TECH-023`** is complexity, not cohesion. They correlate but are not the same measure — a class
  can be perfectly cohesive and still have one enormous method.

## Candidate Approaches (not yet designed)

- **Ratchet it, as `TECH-023` did for complexity.** A frozen per-class baseline turns a
  permanently-red, scope-skipped gate into one that blocks a *new* incohesive class immediately.
  Cheapest thing that stops the bleeding, and it is the established pattern here
  (`check_suppressions`, R6, R7, `check_complexity`).
- **Fix the groups, not the classes.** Roughly five decisions rather than 23 refactors. `TECH-034`
  has since taken the parsers, so the largest remaining group is **one class** —
  `BaseTreeSitterParser` — not eleven.
- ~~**Decide what `LCOM4` should mean for a dispatcher.**~~ **SETTLED 2026-08-12 — see
  §The dispatcher question, answered.** The answer is neither an exemption nor a split: the three
  atoms are a **measurement defect** in `check_class_health.py`, and the same defect accounts for
  **11 of the 19** frozen classes.

## Non-Goals (proposed, pending design)

- **Not** the AST parsers — `TECH-034` owns them.
- **Not** behaviour change of any kind; this is cohesion restructuring.
- **Not** raising or relaxing the `LCOM4` threshold to make the number go away. If a specific
  shape is legitimately exempt (see the dispatcher question), that is an explicit, reviewed
  exemption — not a moved goalpost.

## Verification the design must specify

- The full suite passes untouched at every boundary — this is structural.
- Whatever mechanism is chosen, a **new** incohesive class must fail the gate, verified by planting
  one rather than by reading the checker. Every guardrail added this week that was *not* probed
  that way turned out to be inert.
- The scope-gating problem is separately verifiable: a run that inspects nothing should be
  distinguishable, in its output, from a run that inspected everything and found nothing.

## Next Step

None — the ticket is closed. Two findings it surfaced but deliberately did **not** absorb need
tickets of their own: the **7 language parsers**, now unowned since `TECH-034` closed (a shared
`_is_symbol_valid` on the class-based tier clears four of them), and `TopologyGraph._stale_nodes`
being **assigned from outside the class**.

## Delivery of the ratchet, 2026-08-12

`scripts/_class_health_baseline.py`, wired into `check_class_health.py`. **`quality.py cb` reports
0 failed of 12** — the gate enforces again instead of being ignored.

Both measures are frozen, cohesion and attribute count. Freezing only cohesion left `Task` (one
attribute over the limit) keeping the gate red, which would have preserved the exact condition this
ticket exists to end: a check nobody can act on.

**Verified by planting both regression kinds**, not by reading the code — a new two-component class
in `commons` (exit 1) and `Task` grown 16 → 17 attributes (exit 1), with a clean tree at 0.

### The first probe was wrong, and that mattered

The initial "getting worse" probe added a field the checker does not count, so it reported exit 0
and looked like a gap in the ratchet. It was a bad probe, not a bad guard — but the two are
indistinguishable from the outside, which is the whole subject of this ticket. Re-probed with a
real `mapped_column` and it blocked correctly.

### A real bug the tests caught

`_repo_relative` raised `ValueError` for any path **outside** the repo — which is exactly what a
test scanning `tmp_path` produces. `test_a_god_object_blocks` went from failing loudly to the check
silently reporting nothing, and the suite caught it. Out-of-repo paths now key by absolute path, so
they can never match a baseline entry and are correctly treated as new.

### Still open

19 incohesive classes and 1 oversized, now bounded rather than growing. The largest single target is
**`BaseTreeSitterParser` at `LCOM4=8`** — four distinct jobs (query, walk, edit, format) in one
class, and clearing it also removes three of `TECH-023`'s violations.

## `BaseTreeSitterParser` split, 2026-08-12

The ticket's largest single target, and the debt `TECH-034` knowingly created when it concentrated
the parsers' shared mechanics into one class.

**Measured first: reading and editing share nothing.** Zero cross-references between the two
groups; each depends only on the per-language contract the base declares. That is what made this a
**move** rather than a rewrite, and it is worth checking before splitting anything — the split
would have been wrong if they had been entangled.

| | before | after |
|---|---|---|
| `BaseTreeSitterParser` | 338 lines, `LCOM4=8` | 155 lines, **`LCOM4=2`** |
| `SymbolReadingMixin` | — | 151 lines, **`LCOM4=1`** (cohesive) |
| `SymbolEditingMixin` | — | 88 lines, **`LCOM4=1`** (cohesive) |

Mixins rather than collaborators, so **no parser's public API changes** — every one still answers
`extract_symbol` and the rest exactly as before, and no caller moved.

Each mixin declares what it needs from its host under `if TYPE_CHECKING:`. That states the
dependency instead of letting `self.parser` resolve by luck, and does not touch the runtime MRO.
Getting those declarations to match cost three rounds — `_format_body_injection` takes a `margin`,
`_is_symbol_valid` takes five arguments, and the `SCM_*` members are read-only *properties* rather
than attributes. Each mismatch was a real inconsistency the type checker refused to let through.

**The complexity ratchet flagged the move as three new violations**, because the functions changed
file. Before re-freezing, each was checked against its old score: `extract_skeleton` 16→16,
`extract_traceability_tags` 16→16, `list_symbols` 19→19, and no genuinely new violation. A pure
relocation — but the ratchet was right to ask, and "review the diff" is exactly what it exists for.

**Suppressions went down, not up.** The one added exemption is a `per-file-ignore` for `N802` on
the reading mixin — the sanctioned form, in configuration rather than three call-site `noqa`s, per
the suppressions gate's own instruction. Against it, this session removed six `noqa: C901`, two
`noqa: E402` and three blanket `type: ignore`s: **239 → 229 total**.

`quality.py cb`: **0 failed of 12**. 6485 tests pass, `mypy` and `tach` clean.

### Where that leaves the ticket

18 incohesive classes and 1 oversized remain frozen. `BaseTreeSitterParser` is still above the
threshold at `LCOM4=2`, deliberately: what is left is construction plus the per-language contract,
which is one job stated two ways rather than two jobs. Squeezing it to 1 would be chasing the
metric.

## The dispatcher question, answered — 2026-08-12

**Verdict: the metric is wrong there.** Not a documented exemption, and not a split. The three
atoms' `LCOM4=2` is an artifact of how `check_class_health.py` builds its graph, and the same
artifact accounts for **11 of the 19 frozen classes**. Measured, not read.

### The mechanism

`analyse_class` admits a method to the cohesion graph when it is not `_is_stateless` — and
`_is_stateless` counts *calling a sibling* as coupling (`called & method_names`, line 177). But
edges are only drawn **between methods that are both in `graph_nodes`** (lines 258–262). When the
only sibling a method calls is itself excluded as stateless, the caller is **admitted and then
stranded** as a singleton component. The two rules disagree, and the disagreement inflates `LCOM4`
by exactly one per stranded caller.

All three atoms hit it identically. `run` is not coupled to its `_intent_*` handlers by attribute
(dispatch is `getattr(self, f"_intent_{intent}")`, invisible to AST analysis) — it is admitted
solely because it calls `self._known_intents()`, which touches no attribute and is therefore
excluded:

```
FileSystemAtom  LCOM4=2   comp 1: the 6 _intent_* + _validate_single_boundary + cwd   comp 2: run
GitAtom         LCOM4=2   comp 1: the 15 _intent_* + cwd                              comp 2: run
QARunnerAtom    LCOM4=2   comp 1: the 6 _intent_*                                     comp 2: run
```

**Probed, not inferred.** A synthetic dispatcher scores `LCOM4=1`; adding a single
`self._known_intents()` call to its `run` — no other change, no design difference — drives it to
2 with `run` alone in component 2. *A metric that flips on whether a dispatcher publishes its
known-intent list is not measuring cohesion.*

### It is not just the dispatchers — 11 of 19

Re-scoring every frozen class with graph admission re-tested against surviving siblings:

| Class | frozen | corrected |
|---|---|---|
| `PythonStandardsAnalyzer` | 6 | 0 † |
| `JSStandardsAnalyzer` | 5 | 0 † |
| `AsyncAPIParser`, `GRPCParser` | 2 | 0 † |
| `FileSystemAtom`, `GitAtom`, `QARunnerAtom` | 2 | **1** |
| `Java`/`Kotlin`/`Rust`/`TypeScript` `CodeStructure` | 2 | **1** |

`GRPCParser` is the clearest case: `extract_endpoints` and `extract_messages` **both call
`self._parse_proto`**. They are coupled *through* it — but `_parse_proto` touches no attribute, so
it is excluded and both callers strand. The honest score is 1. The ticket's §"two protocol parsers
with an identical split" reading was wrong for the same reason the dispatcher reading was.

The 8 that survive correction are real and remain this ticket's scope: `TopologyGraph` (3),
`TSStandardsAnalyzer` (3), `RichPipelineDisplay`, `MCPExplorerTool`, `BaseTreeSitterParser`,
`GoCodeStructure`, `MarkdownCodeStructure`, `SqlCodeStructure` (2 each).

### † The `0` is a second finding, and must not be shipped silently

Four classes correct to **`LCOM4=0`** — an empty graph. That is the *correct* reading:
`PythonStandardsAnalyzer` holds **no instance state at all** (every method's `self.` references are
method names, never attributes), so there is nothing for cohesion to be *of*. But `incohesive()` is
`lcom4 > 1`, so **0 passes** — and a stateless class would then be unmeasurable rather than
measured.

That is precisely this ticket's own subject: *a check that silently does not run is
indistinguishable from one that passes*. Any fix must therefore decide, explicitly and in the
output, what a stateless class means — report it under a separate rule, or exempt it with a stated
reason. **It must not be allowed to score 0 and pass quietly.**

### What this does not license

This is **not** relaxing the threshold, which stays at `MAX_LCOM4 = 1` and remains a non-goal
above. It is making graph *admission* agree with graph *edges*. The naive repair (iterate admission
to a fixed point) was tried first and is wrong on its own — it produces the `0`s above with no
signal that it did.

### Consequence for the ticket

The frozen baseline currently records 11 scores that are **not debt**, so "19 incohesive classes"
overstates the real figure by more than half. The reduction work is **8 classes**, and the first
deliverable is the checker fix plus a re-freeze — otherwise later work is measured against a
baseline that is wrong in a known direction.
## Where the 19 went — 2026-08-12

**19 incohesive + 1 oversized → 9 incohesive + 0 oversized.** Not one class was restructured to get
there: every reduction was a **measurement** correction, each probed and each measured across all
402 classes for regressions before it shipped. `MAX_LCOM4` is still 1 and `MAX_ATTRIBUTES` is still
15.

| Correction | Classes | What was wrong |
|---|---|---|
| Stranded callers | 7 | A method admitted for calling a sibling that was then excluded as stateless was left alone as its own component. Removing the stateless node also removed the edges **through** it — `extract_endpoints` and `extract_messages` both call `_parse_proto`, so they are coupled by it. Fixed by dropping a stateless method from the **count**, not the **graph**. |
| Dynamic dispatch | (of those 7) | `getattr(self, f"_intent_{…}")` is a call to *some* sibling. The analyser cannot say which, so the honest reading is any of them. Probed: a synthetic dispatcher scores 1, and adding one `self._known_intents()` call — no design change — drove it to 2. |
| Dispatch tables | 2 | `get_extractors` returns `[self._extract_tsdoc, …]`. Those are attribute loads, not calls, and the edge rule subtracted method names before comparing — so a dispatch table read as three unrelated classes. Handing a sibling around as a value is coupling exactly as much as invoking it. |
| Class constants | 1 | `MCPExplorerTool.role` is `return self.NO_ROLE`, where `NO_ROLE: str = "no_role"` lives on `BaseTool`. As stateless as `return "no_role"`, which was already excluded. Detected by PEP 8 naming because the constant is inherited, and a base class is out of scope when one class body is analysed. |
| ORM declarations | 1 oversized | `__tablename__` / `__table_args__` counted as state. All 13 mapped classes in `src` declare them, so they distinguish none — the `model_config` precedent exactly. `Task` was the single oversized class at 16 and has **14** real mapped columns against a limit of 15. |

**A rejected candidate, recorded because it looked right.** The first fix dropped stranded callers
instead of connecting them. Measured: it scored four real classes at **0**, and `incohesive()` is
`lcom4 > 1`, so 0 *passes*. It would have traded a false positive for a silent blind spot — this
ticket's own subject. The rule that shipped produces none.

### The 9 that remain, and why each is not this ticket's work

**7 are `TECH-034`'s recorded residue and this ticket's explicit non-goal.** `GoCodeStructure`,
`JavaCodeStructure`, `KotlinCodeStructure`, `MarkdownCodeStructure`, `RustCodeStructure`,
`SqlCodeStructure`, `TypeScriptCodeStructure` — all at `LCOM4=2`. `TECH-034` took the parsers from
10 flagged to 7 and knowingly stopped there; §Relationship above says *"Do not refactor the language
parsers here"* and §Non-Goals says *"Not the AST parsers — `TECH-034` owns them."*

Their components now name a real split, which they did not before: four of the seven cut along
`{_is_symbol_valid, _is_symbol_public|_is_symbol_private}` — a **symbol-filter** concern, with
`_is_symbol_valid` near-duplicated across all four and differing only in which visibility predicate
it calls. Go and Sql cut along reading-vs-editing, the same seam `TECH-034`/`TECH-035` already
split out of the base as `SymbolReadingMixin` / `SymbolEditingMixin`.

> **This is now unowned, and that is worth saying plainly.** `TECH-034` is DELIVERED, so nobody
> holds these seven. They are a real, actionable finding — a shared `_is_symbol_valid` on the
> class-based tier would clear four of them — and they need a ticket rather than a sentence here.
> Deliberately **not** absorbed into this one: expanding a ticket past its own stated non-goal is
> how scope stops meaning anything.

**2 are reviewed exemptions.** Both are the same shape: a read-only property exposing
constructor-assigned state that no other method in the class reads.

- **`TopologyGraph`** (3) — components 2 and 3 are `stale_nodes` and `warnings`, defensive-copy
  accessors for construction data. As a refactoring instruction this reads "extract a class that
  holds warnings, and a class that holds stale nodes", which nobody would do.
- **`BaseTreeSitterParser`** (2) — component 2 is `parser`, assigned in `__init__` and consumed by
  the mixins rather than by the base. §"`BaseTreeSitterParser` split" already recorded this:
  *"one job stated two ways rather than two jobs. Squeezing it to 1 would be chasing the metric."*

**Why these are an exemption and not a sixth checker fix.** A blanket "single-attribute getter is
stateless" rule was considered and rejected: it would let a god object with 15 getters score
`LCOM4=1`, which is the exact blindness the cohesion axis exists to cover for. Per-class judgement
recorded here is the honest mechanism, and the frozen baseline is what makes it reviewable —
they are named in `scripts/baselines/class_health.json`, so a reader asking "why is this allowed"
has one file to open.

### Adjacent finding, recorded because nobody has looked

`TopologyGraph._stale_nodes` is assigned **from outside the class** —
`graph._stale_nodes = final_stale_nodes` (`topology.py:271`), reaching into a private attribute of
an instance from a factory. That is why nothing inside the class couples to it, and it is a real
encapsulation defect rather than a cohesion one. Out of scope here (§Non-Goals: no behaviour
change), and it needs its own ticket.

### Verification

Both guards probed by planting violations, not by reading the code — a genuinely incohesive class
**and** a 20-column ORM table in one file: exit 1, both named, the incohesive one's components
printed as the split. Removed: exit 0. The ORM exemption did not blind the god-object axis.

The ratchet census floor moved 15 → 5 with the corrected measurement. It stays a floor rather than
an equality, and well below the current 9, so it catches `measure` collapsing to nothing without
pinning a debt number that later reduction is meant to shrink.

`6529 passed, 11 skipped, 0 failed`. `ruff`, `mypy` (335 files), `tach` clean; complexity ratchet
**40**, suppressions **227**.
