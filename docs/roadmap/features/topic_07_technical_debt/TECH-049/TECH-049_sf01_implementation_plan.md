# Implementation Plan: Mutation Campaign Corpus and Session Gate [SF-01: Campaign Corpus and Drift Hashing]

- **Feature ID**: TECH-049
- **Sub-Feature**: SF-01 — Campaign Corpus and Drift Hashing
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-049/TECH-049_sf01_implementation_plan.md
- **Status**: APPROVED

**FRs owned: FR-1, FR-1a, FR-2, FR-13.** Depends on: none.

## Scope

The on-disk corpus format and everything that reads or maintains it. This sub-feature **runs no
mutants and touches no sandbox** — it produces validated campaign objects and drift state for SF-02
to execute.

## Research Notes

Facts the plan rests on. Everything below was executed or read, not recalled.

| Fact | Evidence |
|---|---|
| `ast.dump(node)` **omits line numbers by default** — the design's "line numbers stripped" is free, `include_attributes` defaults to `False` | executed |
| A whitespace-only reformat leaves the dump **identical** — `ruff format` cannot cause a false `STALE` | executed |
| Renaming a local **does** change the dump — a behaviour-adjacent edit is caught | executed |
| A **docstring edit changes the dump** — a docstring is a real AST node, so rewording one would report a false `STALE` (Q1) | executed |
| `node.lineno` / `node.end_lineno` give the symbol's bounds | executed |
| `load_campaign()` validates every required key and raises before any sandbox work; `_REQUIRED = ("file", "old", "new", "claim")` | read `scripts/_mutate_campaign.py:63-79` |
| `apply_mutation()` refuses on 0 matches (stale) and >1 (ambiguous), counting over the **whole target file** | read `scripts/_mutate.py:77-92` |
| Anchors are not file-unique in practice: `return None` 191×/77 files, `return False` 69×/37, `return []` 59×/31 | executed over `src/` |
| `scripts/` files: YELLOW at 451 lines, **RED at 600**. `_mutate.py` is 298, `_mutate_campaign.py` 217 | read `scripts/check_file_sizes.py:39`, `wc -l` |
| A checker's own tests must carry `# fr-coverage: fixture-data` or they credit requirements they merely quote | read `tests/unit/scripts/test_mutate.py:3`, closure-contract.md:189 |
| Scripts tests load the module under test via `importlib.util.spec_from_file_location` behind a module-scoped fixture | read `tests/unit/scripts/test_mutate.py:37-51` |
| `scripts/_corpus.py` and `tests/unit/scripts/test_corpus.py` are both free (basenames must be repo-unique) | `find` |
| `scripts/` is outside the `tach` graph; no `context.yaml` governs it | read `tach.toml` |

## Decisions taken at the Phase 4 gate (Steve Bula, 2026-08-15)

| # | Question | Decision |
|---|---|---|
| Q1 | Docstrings change the hash | **Strip the leading docstring node** before hashing. A docstring cannot change behaviour, and `STALE` must mean the claim may have moved. |
| Q2 | New module or grow an existing one | **New `scripts/_corpus.py`.** Growing `_mutate.py` (298/600) walks it toward the cap for no benefit; the corpus is a separate concern from running mutants. |
| Q3 | Anchor uniqueness scope | **Unique within the declared symbol**, not the whole file. Project-uniqueness is impossible for code snippets. |
| Q3a | Mutant identity | **Derived and project-unique**: `<feature> <requirement> <id>`. Never hand-typed. Duplicates rejected. (Design FR-1a, added by this planning session.) |
| Q4 | Retire semantics | **Mark `retired` with a reason, never delete.** Deleting destroys the only record the requirement was ever measured. |
| Q5 | Module-level anchors | **Rejected in v1** with a clear error. Hashing the whole module would make the mutant stale on every unrelated edit in the file — worse than not supporting it. |
| Q6 | Schema version | **Yes** — `"schema": 1`. |
| Q7 | Where `symbol_sha` lives | **In the committed corpus file.** That diff is the reviewability FR-13 asks for; a side-file cache would make refreshes invisible. |

## Corpus format

```
docs/roadmap/features/<topic>/<ID>/<ID>_mutants.json
```

```json
{
  "schema": 1,
  "feature": "C-EXEC-06",
  "campaigns": [
    {
      "requirement": "FR-8",
      "title": "Multi-step generated-file e2e stays worktree-bounded",
      "scope": ["tests/e2e/sandbox/test_session_worktree_isolation_e2e.py"],
      "mutants": [
        {
          "id": "isolation-off",
          "file": "src/specweaver/core/flow/engine/isolation.py",
          "symbol": "apply_session_policy",
          "_comment_symbol": "dotted for methods, e.g. \"SessionPolicy.apply\"",
          "old": "return policy.enabled",
          "new": "return False",
          "breaks": "no worktree is created, so step 2 runs at the real root",
          "symbol_sha": "sha256:9f2c..."
        }
      ]
    }
  ]
}
```

`retired` is an optional object on a campaign: `{"reason": "...", "date": "..."}`.

## Validation rules (FR-1, FR-1a)

Ordered, and the order matters — cheap structural checks first so a malformed file never reaches
the filesystem or the AST parser:

1. `schema` present and known. Unknown version → refuse, naming the version found.
2. `feature` present **and equal to the owning directory's feature id**. This is what makes rule 5
   a single-file check: two corpus files cannot declare the same `feature`, so a derived id
   collision across files is structurally impossible rather than merely unlikely.
3. Every campaign has `requirement`, `scope` (non-empty), `mutants` (non-empty).
4. Every mutant has `id`, `file`, `symbol`, `old`, `new`, `breaks`.
5. `old != new` — an identical replacement mutates nothing and would report a false survival.
   (`apply_mutation` already refuses this; catching it at load is cheaper and names the campaign.)
6. Derived id `<feature> <requirement> <id>` is unique within the file — and therefore corpus-wide,
   by rule 2.
7. `file` exists and is readable.
8. `symbol` resolves to **exactly one** node (see *Symbol paths* below).
9. `old` occurs **exactly once within the symbol's line range** — 0 is a stale anchor, >1 ambiguous.
10. A `retired` campaign skips rules 7–9: its code may legitimately be gone.

### Symbol paths

`symbol` is a **dotted path** — `apply_session_policy` for a module-level function,
`SessionPolicy.apply` for a method — resolved by walking the named path segment by segment, never
by `ast.walk` over the whole tree.

This is not future-proofing. Measured across `src/`: **25 files carry duplicate symbol names**, and
one holds `__init__` six times alongside `_get_import_prefix` six times. A bare `symbol: "apply"`
would be ambiguous in most files that have classes, so rule 8 would reject nearly every method
mutant and the format would be unusable for exactly the code most worth mutating.

Every failure names the corpus file, the campaign and the mutant. A message that says only
*"missing key"* costs the reader a search.

## Symbol hashing (FR-2)

Pseudocode, not code:

1. Parse the file with `ast.parse`.
2. Resolve the dotted `symbol` path one segment at a time, searching only the current node's direct
   body for a `FunctionDef` / `AsyncFunctionDef` / `ClassDef` of that name. Zero → error naming the
   segment that failed. More than one → error; ambiguous even at that level.
3. If the anchor's line falls outside the resolved node's `lineno`…`end_lineno`, error — the mutant
   claims a symbol it is not inside.
4. Strip the leading docstring node from the matched node's body (Q1).
5. `sha256(ast.dump(stripped_node))`, prefixed `sha256:`.

Drift is then a comparison: recorded `symbol_sha` vs recomputed. Unequal, or the symbol is gone →
`STALE`. **SF-01 reports drift; it does not act on it** — verdicts are SF-03's.

## Refresh and retire (FR-13)

A CLI on `_corpus.py`, deliberately explicit:

- `--refresh <derived-id>` recomputes and rewrites one mutant's `symbol_sha`. One at a time on
  purpose: a bulk refresh is how drift detection gets defeated in a single command.
- `--retire <feature> <requirement> --reason "..."` marks a campaign retired.
- Neither is ever invoked automatically by any other component.

## Commit boundaries

### CB-1 — Format, loader, validation

**Delivers:** `scripts/_corpus.py` with the loader and rules 1–5 and 9 (structural + identity;
nothing that touches source files yet).

**Tests:** unit, `tests/unit/scripts/test_corpus.py`. Header carries
`# fr-coverage: fixture-data` and a `Proves: TECH-049 FR-1, FR-1a` module docstring tag.

Adversarial matrix: happy (a valid two-campaign corpus); boundary (empty `mutants`, empty `scope`,
single campaign); degradation (unknown `schema`, missing keys, malformed JSON); hostile
(`old == new`, duplicate derived id within a file, `feature` disagreeing with its directory,
`..` in `file`).

**Done when:** the duplicate-id test kills a mutant. Neutralise the uniqueness check —
`--old "if derived in seen:" --new "if False:"` — and confirm exactly that test goes red. A
validation rule that cannot fail is the shape `check_useless_asserts.py` exists to catch.

**Tier: unit.** This boundary reads a JSON file it was handed and touches no other module.

### CB-2 — Symbol resolution and hashing

**Delivers:** symbol lookup, docstring stripping, `symbol_sha` computation, and validation rules
6–8 (which need the source file and the AST).

**Tests:** unit, extending `test_corpus.py`. Docstring **must** carry
`Proves: TECH-049 FR-2`.

The four research facts each become a test, because each is a property someone will otherwise
assume: reformat-stable, rename-sensitive, docstring-insensitive (the Q1 decision — this one would
silently regress), and anchor-outside-symbol rejected. Plus: symbol absent, **a method reached by a
dotted path in a file where the bare name is ambiguous** (the case that makes the format usable at
all), and a module-level anchor rejected with a clear message (Q5).

**Done when:** the docstring-insensitivity test kills a mutant. Neutralise the strip step and
confirm that test alone goes red. It is the only guard on Q1, and without a mutant it is an
assertion nobody has proven can fail.

**Tier: unit.** Still one module plus stdlib `ast`.

### CB-3 — Refresh and retire CLI

**Delivers:** the `--refresh` / `--retire` entry points and their write-back.

**Tests:** unit. Round-trip (load → refresh → reload sees the new hash), retire (campaign is
skipped by rules 6–8 and still counted), and the hostile case that matters: **refreshing a mutant
whose symbol no longer exists must fail**, not write a hash for a symbol that is gone.

**Done when:** the write-back preserves unrelated content byte-for-byte — a refresh that reformats
the whole corpus file makes every future diff unreviewable, which defeats Q7.

**Tier: unit.**

> **No integration or e2e tier in this sub-feature, and that is a claim, not an omission.** SF-01
> crosses no module boundary: it reads JSON and source files with stdlib `ast`, and calls nothing.
> The first seam is SF-02 consuming these objects to drive `run_one()`, and **that integration test
> belongs to SF-02's first boundary**, written where the interface exists and the behaviour does
> not. Per `ADR-003` it is not deferred to a later story — there is no later story.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | `symbol_sha` proves stable against reformatting in tests but not against a real `ruff format` run | CB-2 asserts on real reformatted source, not a hand-written pair |
| R-2 | Validation messages name the rule but not the campaign, so a 40-mutant corpus fails unlocatably | Every message names corpus file + campaign + mutant id; asserted in tests |
| R-3 | `--refresh` becomes the habitual response to any `STALE` | One id at a time; no bulk flag. The diff is the review |
| R-4 | Q3's within-symbol uniqueness changes `apply_mutation`'s contract, which SF-02 relies on | SF-01 only *validates* against the symbol range; `apply_mutation` is unchanged here, and the change is called out for SF-02's plan |
| R-5 | `scripts/_corpus.py` grows past 451 (YELLOW) as three concerns land in it | Measured at each boundary; if CB-3 crosses it, the CLI splits into `_corpus_cli.py` |

## Out of scope

Running mutants, sandboxes, baselines, verdicts, reports, scheduling, the gate. All later
sub-features. SF-01 produces data; it decides nothing.
