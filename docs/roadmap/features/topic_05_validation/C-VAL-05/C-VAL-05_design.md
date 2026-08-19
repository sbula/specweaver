# Design: Rubrics-as-Content Validation (Rules as Code, Rubrics as Content)

- **Feature ID**: C-VAL-05
- **Epic**: Topic 05 (Validation Engine)
- **Status**: ✅ Delivered — this document is a **record**, not a plan.
- **DAL**: C (Enterprise Standard)

## What shipped

Semantic judgment criteria are markdown files under `src/specweaver/assurance/validation/rubrics/`.
A project overrides any of them from `.specweaver/rubrics/`, the run's DAL selects a stricter
variant where one is shipped, and every load carries the id, version, checksum and source path of
the file that judged it.

The line the feature draws: **what counts as good is content, how the verdict is read is code.**
`REVIEW_OUTPUT_CONTRACT` in `workflows/review/reviewer.py` stays in Python because `_parse` depends
on it, and `resolve_review_instructions` in the review handler joins the two halves.

## The stub's premise was half stale

The stub named three targets: `S03` stranger-test, `S07` test-first, and the review criteria. Two of
the three no longer hold, measured against the code on delivery:

- `s03_stranger.py` and `s07_test_first.py` both return `requires_llm = False`. They are regexes and
  thresholds — `_EXT_LINK_RE`, `_WARN_THRESHOLD`, an abstraction-leak scan. There is no judgment
  criterion in either, so there is nothing to externalize.
- **No rule in the battery requires an LLM.** All 23 are mechanical, not 21 of 23.

The real frozen judgment was `SPEC_REVIEW_INSTRUCTIONS` and `CODE_REVIEW_INSTRUCTIONS`, defined in
`reviewer.py` and consumed by the review handler. Each already contained the two halves as separate
markdown sections — `## Review Criteria` and `## Output Format` — which is why the cut is clean.

So this capability externalizes the review criteria and builds the substrate. It does **not** convert
`S03`/`S07`, because converting a regex to a rubric would replace a cheap deterministic check with an
LLM call and call it progress.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Criteria are content, not code | System | Ships judgment criteria as markdown with `id` and `version` frontmatter, loaded by id | Changing what a review asks for is an edit to a file, not a code change and a release |
| FR-2 | A project sets its own standard | System | Resolves `.specweaver/rubrics/<id>.md` ahead of the shipped default, per rubric | A team tunes criteria to its domain; an untouched project keeps the shipped criteria rather than losing them |
| FR-3 | Risk selects the standard | System | Prefers `<id>.<DAL>.md` using the run's own resolved DAL, falling back to the default when no variant exists | A DAL-A spec is judged against catastrophic-failure criteria without a step parameter anyone must remember, and a DAL-D spec is not |
| FR-4 | The verdict is auditable | System | Records id, version, sha256 of the criteria and the source path on every load | DAL-C can answer *which criteria produced this verdict*, and an edited rubric is visibly a different one |
| FR-5 | The engine contract is not overridable | System | Keeps the response format in `REVIEW_OUTPUT_CONTRACT` and appends it to whatever criteria were loaded | An override cannot break the response parser — the failure mode would appear as a wrong verdict, not as a bad rubric |

Proof is by citation in the test files, read by `check_fr_coverage.py`. Each FR is behind a killed
mutant: ignoring the project override, ignoring the DAL variant, freezing the checksum, returning
empty criteria instead of raising, and dropping the output contract each fail the tests that claim
them.

`FR-2` and `FR-5` are also proven at full distance by
`tests/e2e/capabilities/assurance/test_project_rubric_reaches_the_reviewer_e2e.py`, which runs
`ReviewSpecHandler` against a recording adapter and reads what the model was actually sent. The
unit tests cannot see the wiring being dropped — a correct `resolve_review_instructions` whose
result is never passed to the prompt leaves them green, and hardcoding the criteria back into the
handler fails all three of these.

A missing rubric raises `RubricNotFound` rather than resolving to empty criteria. Empty criteria
would send the model no standard, and it would still return a verdict.

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-2 | Project-override precedence, as already established for pipelines | `E-FLOW-02` · `profiles._custom_pipelines_dir(project_dir)` | read `src/specweaver/core/config/profiles.py:74` — `.specweaver/<kind>/` over the packaged directory |
| FR-3 | The run's resolved criticality | `C-VAL-03` · `context.isolation.dal_level` | read `src/specweaver/core/flow/engine/isolation.py` — `seed_dal_level` resolves it once per run |
| FR-5 | The response format the verdict parser depends on | `E-INTL-03` · `reviewer.REVIEW_OUTPUT_CONTRACT` | read `src/specweaver/workflows/review/reviewer.py` — `_parse` reads `VERDICT:` and `[confidence: N]` |

`workflows.review` may depend only on `infrastructure.llm` (`tach.toml`), so it cannot load a
rubric itself. The handler composes — which is why `FR-5` is proven at the handler, and end to end
at e2e, not inside the reviewer.

## Non-Functional Requirements

| # | NFR | Requirement |
|---|-----|-------------|
| NFR-1 | Format | Markdown with a small frontmatter, parsed by two regexes. A rubric is prose with a label; a YAML dependency would make the criteria harder to edit, not easier |
| NFR-2 | Precedence | A project's plain rubric outranks a shipped DAL variant — an override that names no DAL still means *use mine* |
| NFR-3 | Boundary | The loader lives in `assurance.validation`; `workflows.review` reaches only `infrastructure.llm`, so the handler composes and the reviewer stays unaware. **[proof: arch — `tach check`, not pytest: the expose list and `depends_on` are what enforce it]** |

## Non-Goals

- Softening mechanical rules. C01–C13 and the spec rules stay code.
- Changing the battery, report or gate contracts.
- User-defined rule IDs — that remains `D-VAL-02`.
- Converting `S03`/`S07`. See the premise section: there is no judgment content in either.

## What this is the substrate for

`B-VAL-03`, `E-VAL-04` and `B-INTL-08` should be designed rubric-first on this loader rather than
freezing new prompts in Python. The extension point is a markdown file plus a `load_rubric` call,
not a rule class.
