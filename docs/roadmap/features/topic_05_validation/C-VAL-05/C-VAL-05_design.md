# C-VAL-05 — Rubrics-as-Content Validation (Rules as Code, Rubrics as Content)

**Status**: APPROVED by the user 2026-10-17 — 🔧 built, then reviewed at Phase 6 that day: NFR-2 did not hold and FR-4 recorded
only a log line. Status returns to ✅ after those corrections and the user's sign-off. · **DAL**: C (Enterprise Standard) · **Epic**: Topic 05 (Validation Engine) ·
**Feature ID**: C-VAL-05

| | |
|---|---|
| Uses | `E-FLOW-02` (project-override precedence) · `C-VAL-03` (run DAL) · `E-INTL-03` (`REVIEW_OUTPUT_CONTRACT`) |
| Substrate for | `B-VAL-03`, `E-VAL-04`, `B-INTL-08` |
| Not touched | mechanical rules; `S03`/`S07`; user-defined rule IDs (`D-VAL-02`) |

## What it does

Semantic judgment criteria are markdown files under `src/specweaver/assurance/validation/rubrics/`.
A project overrides any of them from `.specweaver/rubrics/`, the run's DAL selects a stricter variant
where one is shipped, and every load carries the id, version, checksum and source path of the file
that judged it.

The line it draws: **what counts as good is content, how the verdict is read is code.**
`REVIEW_OUTPUT_CONTRACT` in `workflows/review/reviewer.py` stays in Python because `_parse` depends on
it; `resolve_review_instructions` in the review handler joins the two halves.

## Why not S03/S07

The stub named three targets: `S03` stranger-test, `S07` test-first, and the review criteria. Measured
on delivery, two of the three did not hold:

- `s03_stranger.py` and `s07_test_first.py` both return `requires_llm = False`. They are regexes and
  thresholds — `_EXT_LINK_RE`, `_WARN_THRESHOLD`, an abstraction-leak scan. No judgment criterion to
  externalize.
- **No rule in the battery requires an LLM.** All 23 are mechanical, not 21 of 23.

The frozen judgment was `SPEC_REVIEW_INSTRUCTIONS` and `CODE_REVIEW_INSTRUCTIONS` in `reviewer.py`,
consumed by the review handler. Each already split into `## Review Criteria` and `## Output Format`,
so the cut is clean.

So this capability externalizes the review criteria and builds the substrate. Converting a regex to a
rubric would replace a cheap deterministic check with an LLM call.

## Architecture

| Piece | Lives in | Does |
|---|---|---|
| `load_rubric` loader + shipped `.md` defaults | `assurance.validation` (`rubrics/`) | resolves id → criteria + provenance |
| `REVIEW_OUTPUT_CONTRACT`, `review_instructions` | `workflows/review/reviewer.py` | the fixed response format |
| `resolve_review_instructions` | review handler (`core.flow`) | loads the rubric, appends the contract |

`workflows.review` may depend only on `infrastructure.llm` (`tach.toml`), so it cannot load a rubric
itself. The handler composes — which is why `FR-5` is proven at the handler, and end to end at e2e,
not inside the reviewer.

A missing rubric raises `RubricNotFound` rather than resolving to empty criteria, so the review step
fails and names it: empty criteria send the model no standard, and it would still return a verdict
`[agreed 2026-10-17]`.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Criteria are content, not code | System | Ships judgment criteria as markdown with `id` and `version` frontmatter, loaded by id | Changing what a review asks for is an edit to a file, not a code change and a release |
| FR-2 | A project sets its own standard | System | Resolves `.specweaver/rubrics/<id>.md` ahead of the shipped default, per rubric | A team tunes criteria to its domain; an untouched project keeps the shipped criteria rather than losing them |
| FR-3 | Risk selects the standard | System | Prefers `<id>.<DAL>.md` using the run's own resolved DAL, falling back to the default when no variant exists | A DAL-A spec is judged against catastrophic-failure criteria without a step parameter anyone must remember, and a DAL-D spec is not |
| FR-4 | The verdict is auditable | Review step | SHALL record the rubric's id, version, sha256 of its criteria and its source path in the step's result, beside the verdict, saved with the run `[agreed 2026-10-17]` | DAL-C can answer *which criteria produced this verdict* from the run itself, and an edited rubric is visibly a different one |
| FR-5 | The engine contract is not overridable | System | Keeps the response format in `REVIEW_OUTPUT_CONTRACT` and appends it to whatever criteria were loaded | An override cannot break the response parser — the failure mode would appear as a wrong verdict, not as a bad rubric |

Proof is by citation in the test files, read by `check_fr_coverage.py`. Measured 2026-10-17, three
mutants existed (override ignored, checksum frozen, contract dropped); the corrections add ignoring
the DAL variant, empty criteria instead of raising, a shipped variant outranking a project's plain
rubric, and the provenance left out of the result.

`FR-2` and `FR-5` are also proven at full distance by
`tests/e2e/capabilities/assurance/test_project_rubric_reaches_the_reviewer_e2e.py`: it runs
`ReviewSpecHandler` against a recording adapter and reads what the model was sent. Unit tests cannot
see the wiring dropped — a correct `resolve_review_instructions` whose result never reaches the
prompt leaves them green; hardcoding the criteria back into the handler fails all three e2e tests.

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-2 | Project-override precedence, as already established for pipelines | `E-FLOW-02` · `profiles._custom_pipelines_dir(project_dir)` | read `src/specweaver/core/config/profiles.py:74` — `.specweaver/<kind>/` over the packaged directory |
| FR-3 | The run's resolved criticality | `C-VAL-03` · `context.isolation.dal_level` | read `src/specweaver/core/flow/engine/isolation.py` — `seed_dal_level` resolves it once per run |
| FR-5 | The response format the verdict parser depends on | `E-INTL-03` · `reviewer.REVIEW_OUTPUT_CONTRACT` | read `src/specweaver/workflows/review/reviewer.py` — `_parse` reads `VERDICT:` and `[confidence: N]` |

## Non-Functional Requirements

| # | NFR | Requirement |
|---|-----|-------------|
| NFR-1 | Format | Markdown with a small frontmatter, parsed by two regexes. A rubric is prose with a label; a YAML dependency would make the criteria harder to edit, not easier |
| NFR-2 | Precedence | A project's plain rubric outranks a shipped DAL variant — an override that names no DAL still means *use mine*; a project wanting a stricter DAL-A rubric names it `<id>.DAL_A.md` `[agreed 2026-10-17]`. Measured 2026-10-17: the loader searched project variant, **shipped variant**, project plain, shipped plain — so a DAL-A project's own rubric was ignored, and no test covered it |
| NFR-3 | Boundary | The loader lives in `assurance.validation`; `workflows.review` reaches only `infrastructure.llm`, so the handler composes and the reviewer stays unaware. **[proof: arch — `tach check`, not pytest: the expose list and `depends_on` are what enforce it]** |

## Non-Goals

- Softening mechanical rules. C01–C13 and the spec rules stay code.
- Changing the battery, report or gate contracts.
- User-defined rule IDs — that remains `D-VAL-02`.
- Converting `S03`/`S07` — no judgment content in either (see above).

## Substrate for

`B-VAL-03`, `E-VAL-04` and `B-INTL-08` should be designed rubric-first on this loader rather than
freezing new prompts in Python. The extension point is a markdown file plus a `load_rubric` call, not
a rule class.

## Corrections (Phase 6, 2026-10-17)

| # | Correction | FR | Proof |
|---|---|---|---|
| K-1 | the search order becomes project variant, project plain, shipped variant, shipped plain | NFR-2 | a DAL-A project with its own plain rubric is judged by it; mutant: the shipped variant first again |
| K-2 | the review step's result carries `rubric: {id, version, checksum, source}` | FR-4 | a review run's saved result names the rubric that judged it; mutant: the field dropped |
| K-3 | the two missing mutants: DAL variant ignored, empty criteria instead of raising | FR-3, FR-1 | killed by the existing tests, or the tests are fixed |

## Session Handoff

**Now**: Phase 6 review done 2026-10-17; the user answered Q1–Q3.
**Next**: the plan for K-1..K-3 ([plan](C-VAL-05_corrections_plan.md)).
