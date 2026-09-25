# B-VAL-02 SF-02 — Dynamic Flow Handler (Detect Rot)

**Status**: APPROVED · **FRs owned**: FR-1, FR-2, FR-4, FR-8 (recorded 2026-08-17 under
`specweaver-dev` §3.2c, from `INT-US-01-SF03-MIG`) · **Depends on**: SF-01 · Design:
[B-VAL-02_design.md](B-VAL-02_design.md) §Sub-features → SF-02

Owned FRs: installing the hook, what the hook invokes, the one-step `DETECT`/`DRIFT` pipeline, and
aborting the commit. **The exit code is 42, not the `1` FR-8 declares**, and the hook script matches
on 42. The two have to agree, and that agreement is the actual requirement.

## Goal

Replace the SF-01 `check-rot` stub with the real check: take the staged code files, resolve each
one's parent `PlanArtifacts` (**Option A: Trace-to-Plan**, approved by the human engineer), and run
the deterministic AST drift engine. On structural drift, abort with exit code `42`.

## Where it plugs in

- SF-01 is complete: git hooks run `sw drift check-rot --staged`; `drift.py`'s `check-rot` is a stub
  that prints text.
- NFR-1 caps the hook at `<500ms`, so no LLM. The existing `detect_drift` in
  `src/specweaver/validation/drift_detector.py` is fast enough, and needs a structured
  `PlanArtifact`, not raw Markdown.

## Changes

`src/specweaver/cli/drift.py` — `drift_check_rot` (the `sw drift check-rot` sub-command):

1. **Locate target files** — the staged files from Git.
2. **Resolve plans** — Option A (Trace-to-Plan).
3. **Delegate** — one dynamic single step per staged file matched to a plan.
4. **Enforce** — on drift, compile an aggregate report.
5. **Terminate** — print a `Rich` console table to stderr showing the drift, then
   `raise typer.Exit(code=42)`.

## Tests

`tests/integration/cli/test_drift_rot_handler.py`:

| Case |
|---|
| mocked `subprocess.run` simulates `git diff --cached` returning sample paths, in a temporary workspace |
| drift → `sw drift check-rot --staged` exits `42` and prints the drift table |
| healthy file → exits `0` |
| single staged file; multiple staged files across different plans; un-planned files ignored |

No second E2E layer: the SF-01 `test_hooks_e2e.py` asserts the OS-level `exit 1` block.

## As built

All five changes and the test file done. **Since moved** (noted 2026-09-25): `drift_check_rot` →
`assurance/validation/interfaces/cli_drift.py` (exit via `sys.exit(42)`); the test →
`tests/integration/interfaces/cli/test_drift_rot_handler.py`.
