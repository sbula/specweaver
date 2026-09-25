# C-VAL-05 — Rubrics-as-Content Validation: Plan

**FRs owned**: FR-1, FR-2, FR-3, FR-4, FR-5 · Design: [C-VAL-05_design.md](C-VAL-05_design.md)

One loader and one seam; a sub-feature split across five requirements this tightly coupled would be
fiction. Proof and mutants are tabulated in `C-VAL-05_design.md`.

## Where it plugs in

- `src/specweaver/assurance/validation/rubrics/` — a package with the loader and the shipped criteria.
  `loader.py` resolves an id through four candidates — project variant, project default, shipped
  variant, shipped default — and returns the criteria with provenance. The `.md` files beside it are
  the defaults and ship the way `workflows/pipelines/*.yaml` already do.
- Precedence follows `core/config/profiles.py` for pipelines: `.specweaver/<kind>/` over the packaged
  directory.
- `workflows/review/reviewer.py` keeps `REVIEW_OUTPUT_CONTRACT` and gains `review_instructions`, which
  joins criteria to contract.
- `resolve_review_instructions` in `core/flow/handlers/review.py` loads the rubric and passes the
  joined text to `_build_base_prompt` — `tach.toml` gives `workflows.review` only
  `infrastructure.llm`. `core.flow` already depends on `assurance.validation`; the new names join that
  module's `[[interfaces]]` expose list.

## Changes

Tests first, red before the code, per `ADR-005`.

1. `tests/unit/assurance/validation/test_rubrics.py` — the loader, with a control beside each
   requirement: no override still yields the shipped criteria, a DAL with no variant falls back, an
   edited rubric changes its checksum.
2. `rubrics/loader.py` and the three shipped `.md` files, until green.
3. `tests/unit/core/flow/handlers/test_review_rubric_seam.py` — written against
   `resolve_review_instructions` before it exists.
4. Split the two frozen constants; wire the handler; extend the tach interface.
5. `tests/e2e/capabilities/assurance/test_project_rubric_reaches_the_reviewer_e2e.py` — the whole
   chain, `ReviewSpecHandler` against a recording adapter. The only test that fails when the handler
   stops consulting the rubric at all.
6. Mutation pass: ignore the override, ignore the DAL variant, freeze the checksum, return empty
   criteria instead of raising, drop the output contract, hardcode the criteria back into the handler.

## Non-Goals

- Converting `S03`/`S07` to rubrics. Both are `requires_llm = False`; the design records the
  measurement.
- A rubric DSL. Frontmatter plus prose.
