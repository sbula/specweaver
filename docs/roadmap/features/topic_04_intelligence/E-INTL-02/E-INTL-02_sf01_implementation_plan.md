# E-INTL-02 SF-01 — Spec Drafting

**Phase**: 1, build step 4 · **FRs owned**: FR-1, FR-2 · Design: [E-INTL-02_design.md](E-INTL-02_design.md)

## Goal

**Runnable:** `sw draft greet_service` → interactive session → spec produced.

## Changes

Created (nothing copied from FM):

- `context/provider.py`, `context/hitl_provider.py`
- `drafting/drafter.py`
- `config/templates/component_spec.md`
- `review/reviewer.py`, `review/prompts/spec_review.md`
- Tests with mocked LLM

**Since moved** (noted 2026-09-25): under `src/specweaver/` — `workspace/context/provider.py`,
`interfaces/cli/hitl_provider.py`, `workflows/drafting/drafter.py`, `workflows/review/reviewer.py`.

**Section review** (2026-10-13, FR-2): `ContextProvider.review(section, text)` returns "" to keep,
`skip`, or a change; `HITLProvider` asks at the terminal; `BaseDrafter._section_content` rewrites
until kept.
