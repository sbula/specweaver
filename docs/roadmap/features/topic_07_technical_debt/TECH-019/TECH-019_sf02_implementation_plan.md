# Implementation Plan: Skill Instruction Integrity [SF-02: `check_skill_references.py` guardrail]

- **Feature ID**: TECH-019
- **Sub-Feature**: SF-02 — Ship the guardrail
- **Design Document**: `docs/roadmap/features/topic_07_technical_debt/TECH-019/TECH-019_design.md`
- **Design Section**: §Sub-Features → SF-02
- **Implementation Plan**: `docs/roadmap/features/topic_07_technical_debt/TECH-019/TECH-019_sf02_implementation_plan.md`
- **Status**: APPROVED

## Scope

Covers **FR-4**, **FR-5**, **FR-6**, and carries the live-tree assertion that proves **FR-1**.
Depends on SF-01 (`ffaa4a8b`), which is what makes the live-tree assertion green on arrival.

Three deliverables: the script, its unit tests, and one row in the quality matrix.

## The Rule (FR-4/FR-5, from the design)

A path-shaped token — inline-backticked, fenced, or bare in prose — is **enforced** only when all
five hold:

1. it contains `/`; and
2. its first segment is a real top-level entry of the repo (`docs`, `src`, `tests`, `scripts`,
   `specs`, `.agents`, `.claude`); and
3. it contains no placeholder metacharacter (`[`, `<`, `*`, `{`); and
4. no path segment is an uppercase stand-in token (`NN`, `XX`, `ID`, `N`, `SFxx`); and
5. it is not in `EXAMPLE_ALLOWLIST`.

Rules 4 and 5 were measured into existence, not anticipated: rules 1–3 alone produced two false
positives on the live tree. Do not drop them "as redundant" — the tests below pin both.

## Scan Scope (HITL-approved 2026-08-08)

- `.agents/**/*.md` — 28 files including `AGENTS.md`
- every `CLAUDE.md`: repo root, `src/specweaver/{core,graph,interfaces,sandbox}/`, `tests/`
  (6 files, all measured clean under the rule)

**Excluded:**

- `.claude/**` — byte-identical to `.agents/`, enforced by `check_skill_sync.py`. Scanning it
  would report every real finding twice, and duplicate findings are how a checker earns its way
  onto the ignore list. **This is a load-bearing dependency**: the script's module docstring must
  say that half its coverage comes from `skill_sync`, so that deleting `skill_sync` is visibly
  also a decision about this check.
- `.tmp/**` — `.tmp/pre/tests/CLAUDE.md` is a scratch copy, not an instruction.
- `docs/roadmap/features/**` — delivered designs and implementation plans are records of what was
  true then (finished-stories-immutable). Never scanned. This is a **non-goal, not an oversight**;
  a test pins it.

## Implementation Sketch

`scripts/check_skill_references.py`, following `check_skill_sync.py`'s shape: module docstring
explaining *why*, module-level constants, `main(argv) -> int`, `sys.exit(main())`.

Constants:

- `TOP_LEVEL` — the seven top-level names of rule 2.
- `PLACEHOLDER_CHARS` — `[<*{`.
- `PLACEHOLDER_TOKEN` — segment-anchored regex for rule 4.
- `EXAMPLE_ALLOWLIST: dict[str, str]` — path → reason. Seeded with one entry:
  `tests/unit/test_foo.py` → "worked example in specweaver-dev's TDD walkthrough — a stand-in
  filename, not a file". Same shape as `check_story_preconditions.py`'s `DEAD_PROMISE_ALLOWLIST`:
  an entry is a tracked exception that must state its reason, never a silent pass.
- `TOKEN` — the path-shaped-token regex. Must match inside fences and bare prose, not only inline
  backticks: the §1.1 site repaired in SF-01 sat inside a fence and a backtick-only scan missed it.

Pseudocode for the single pass:

```
for each file in scan_scope():
    for lineno, line in enumerate(file):
        for raw in TOKEN.findall(line):
            ref = strip surrounding punctuation/backticks
            if not enforced(ref):        # rules 1-5, in that order
                continue
            if not (REPO_ROOT / ref).exists():
                record (file, lineno, ref)
report; return 1 if any else 0
```

`enforced()` is the whole design surface — keep it one small predicate so the tests can drive it
directly rather than through file I/O.

Accept optional path arguments overriding the scan roots, as `check_skill_sync.py` does, so the
tests can point it at fixtures instead of the live tree.

## Test Plan — `tests/unit/scripts/test_check_skill_references.py`

Load the module by path (`scripts/` is not importable) using the `_load` idiom already in
`test_check_story_preconditions.py` and `test_check_coupling.py`.

Cite `TECH-019` and the FR ids in the module docstring — `check_fr_coverage.py` matches at file
level and the closure gate needs FR-1 and FR-4/5/6 cited.

| # | Bucket | Test | Proves |
|---|---|---|---|
| 1 | Happy | a resolving repo-rooted ref passes | FR-4 |
| 2 | Happy | a dangling repo-rooted ref fails, and the message carries file, line and the ref | FR-4, NFR-2 |
| 3 | Boundary | a ref inside a fenced block is enforced, not just inline-backticked ones | FR-4 |
| 4 | Boundary | bare basename (`check_fr_coverage.py`) ignored — names a real file, asserts no location | FR-5 |
| 5 | Boundary | shorthand (`flow/models.py`) ignored — first segment is not top-level | FR-5 |
| 6 | Boundary | bracket/angle/glob templates ignored (`[ID]`, `<skill-name>`, `topic_*.md`) | FR-5 |
| 7 | Boundary | `US-NN_integration.md` ignored — the rule-4 case, a real false positive before it existed | FR-5 |
| 8 | Boundary | an allowlisted example is ignored **and** its reason is non-empty | FR-5 |
| 9 | Hostile | a path escaping the repo (`docs/../../etc/passwd`) is not reported as resolving | FR-4 |
| 10 | Degradation | an unreadable/undecodable file degrades to a finding, never a traceback | NFR-2 |
| 11 | **Live tree** | the real scan scope has **zero** dangling references | **FR-1** |
| 12 | **Live tree** | `docs/roadmap/features/**` is outside the scan scope | non-goal |

Tests 1–10 use `tmp_path` fixtures — that is where red/green happens. Tests 11–12 assert against
the live tree and are the ones that make this a guardrail rather than a unit.

> Test 11 is the FR-1 proof deferred from SF-01. It is green on arrival because SF-01 already
> took the tree from 10 dangling sites to 0. If it is red, SF-01 regressed — do not "fix" it by
> loosening the rule.

## Quality-Gate Wiring (FR-6, HITL-approved)

Mirror `skill_sync` exactly — three edits to `scripts/quality.py`:

1. `MATRIX["skill_references"] = {"doc": "all"}`, placed in the `doc` track beside `skill_sync`
   and `roadmap_sync`, with a comment saying why it is repo-wide and takes no paths.
2. A `_skill_references(_paths)` builder returning `_script("check_skill_references.py")`.
3. `CHECKS["skill_references"] = Check("skill_references", (".agents", "docs"), _skill_references,
   ignores_paths=True, script="check_skill_references.py")`.

**Accepted trade:** doc-gate-only means a *code* commit that deletes a referenced document does not
trip this until the next doc-gate run. Consistency with the two existing registry checks was
preferred over closing that window; `TECH-008` itself was a doc refactor, which the doc gate covers.

Verify with `python scripts/quality.py doc` — it must run the new check and pass.

## Commit Boundary

**CB-1 (single).** Script + tests + wiring. Splitting them would land either a checker nothing
runs, or a matrix row pointing at a script that does not exist.

Suggested message: `feat(scripts): assert every repo-rooted reference in an instruction resolves`

## Verification

1. `.venv/Scripts/python.exe -m pytest tests/unit/scripts/test_check_skill_references.py -v` — all green.
2. `.venv/Scripts/python.exe scripts/check_skill_references.py` — exit 0, zero findings.
3. **Prove the checker can fail.** Temporarily add a dangling repo-rooted ref to a scratch file
   inside the scan scope, confirm exit 1 and that the message names file/line/ref, then revert.
   A guardrail that has never been observed failing is not known to work — this is the
   `test-quality.md` "make it fail on purpose" probe, and it is mandatory here because tests 11–12
   pass trivially on a clean tree.
4. `python scripts/quality.py doc` — passes with the new check present in the run.
5. `ruff check scripts/ tests/` + `mypy` clean; full suite green.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | Tests 11–12 pass vacuously — a scan scope that resolves to zero files also reports zero findings. | Test 11 asserts a **positive control**: the scan visited a non-zero number of files. This exact trap was hit during SF-01 verification, where `grep -r` reported a clean `.claude/` tree it had never traversed. |
| R2 | Rules 4/5 look redundant and get "simplified" away later, reintroducing the two measured false positives. | Tests 7 and 8 pin them, and both name the real reference that produced the false positive. |
| R3 | The scan silently stops covering `.claude/` if `skill_sync` is ever removed. | Stated in the module docstring as a load-bearing dependency, not left implicit. |
| R4 | Someone repairs a future finding by pointing at any file that resolves (e.g. `README.md`) — green checker, hollow instruction. | Cannot be enforced mechanically; called out in the docstring, and it is why SF-01's edit table named specific documents. |
