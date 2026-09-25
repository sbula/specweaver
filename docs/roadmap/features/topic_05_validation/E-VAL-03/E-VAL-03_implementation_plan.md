# E-VAL-03 — AST Prompt Injection Sanitization: Plan

> **⚰️ RETIRED 2026-08-21.** See the design's retirement banner. Record only.

**FRs owned**: FR-1, FR-2, FR-3, FR-4 (descoped with the code) · Design:
[E-VAL-03_design.md](E-VAL-03_design.md)

One module and one call site; splitting four requirements this tightly coupled across sub-features
would be fiction. Proof and mutants were tabulated in `E-VAL-03_design.md`.

## Where it plugged in

- `src/specweaver/infrastructure/llm/injection.py` — new and pure: `findings_in` reports
  instruction-shaped spans; `redact_injections` returns the safe text with the record of what it took
  out. Beside `escaping.py`: same subject — what may be placed in a prompt — split by which half of the
  attack it answers. It had to be: `tach.toml` lets `infrastructure.llm` depend on
  `workspace.ast.parsers` and `core.config` and nothing else, so `assurance.validation` and `commons`
  are closed to it.
- `FilePromptAdapter.get_prompt_content` calls it immediately before `apply_escaping`. That adapter is
  the single chokepoint every file-shaped context passes through — `add_file`, `add_file_context`,
  `add_mentioned_files` and the skeleton path all render there — so the scan covers callers that do
  not know it exists, including future ones. Guarding each adder would leave every new caller to
  remember.

## Changes

Tests first, red before the code, per `ADR-005`.

1. `tests/unit/infrastructure/llm/test_injection.py` — the detector. Half the file is the control:
   ordinary source that names the same words must survive untouched; a detector that flags everything
   protects nothing.
2. `injection.py`, until that file is green.
3. `tests/unit/infrastructure/llm/test_injection_boundary.py` — the seam, written against
   `FilePromptAdapter` before the adapter knows about redaction; three tests go red, five controls stay
   green.
4. The adapter change, until all eight pass.
5. Mutation pass: neuter the detector, flag every line, truncate to the match instead of the line end,
   drop the attribute, drop the log. Each must fail the tests that claim it.

## Non-Goals

- A per-language AST walk. The reasoning is in the design's non-conformance section.
- A user-facing validation verdict for injection findings.
- Scanning `add_instructions`. FR-4 is the requirement that it stays unscanned.
