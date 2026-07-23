# Task List — INT-US-02 SF-02: Composition-Root Provider Wiring (SF-01 record: git history + walkthrough)

- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-02/INT-US-02_sf02_implementation_plan.md
- **FRs**: FR-4 (TTY-gated provider wiring), FR-5 (headless park contract byte-identical)
- **Commit boundary**: single **CB-1** — ✅ committed `f16033a0` (2026-07-23).

## Tasks (SF-02)

- [x] **T1 — the seam** (FR-4)
  - src: `core/flow/interfaces/cli.py` — `set_context_provider_factory` (generic channel seam,
    post-TECH-006-oriented) + `_maybe_attach_provider` at BOTH composition sites; declared in
    tach.toml `[[interfaces]]`. Core terminal-agnostic, zero new delivery imports.
  - test: `tests/unit/core/flow/interfaces/test_provider_seam.py` — 5 direct cases, R1 reset fixture.

- [x] **T2 — delivery registration + composition proof** (FR-4, FR-5)
  - src: `interfaces/cli/main.py` — `_stdin_isatty()` + `_interactive_context_provider()`
    (TTY → HITLProvider, else None), registered at flow_cli wiring.
  - test: 3 factory units (incl. R4 registration proof) + 3 composition integrations
    (TTY run/resume attach; headless None).

- [x] **T3 — Full suite + pre-commit gate (CB-1)** — done, committed.

## Progress (SF-02)
- Task list approved (R1 reset fixture, R4 end-to-end registration proof honored).
- T1+T2 TDD complete. Step A: unit 4768 · integration 501 · e2e 150.
- Pre-commit:
  - Phase 1: ✅ tach caught the undeclared seam symbol → declared in `[[interfaces]]` (honest fix).
  - Phase 2/3: ✅ user approved G1 → **exposed + fixed inherited defect**: broad `except Exception`
    swallowed `typer.Exit(0)` — every PARKED run exited 1 with "Error: Exit:". Now `except typer.Exit:
    raise` passthrough; parked runs exit 0 as intended.
  - Phase 4: ✅ unit 4768 · integration 502 · e2e 150 (5420 passed, 0 failures).
  - Phase 5: ✅ ruff/C901/mypy(303)/file-size/tach/roadmap-sync clean.
  - Phase 6: ✅ HITL-gates user guide (interactive vs headless drafting, park exit 0), as-built notes.
  - Phase 7: ✅ INT-US-02_sf02_walkthrough.md. Phase 7.5: ✅ no criticals.
  - Phase 8: ✅ committed `f16033a0` (direct to master, 2026-07-23); tracker all ✅ (`1a66ef95`).

## Next
SF-03 — FR-8 e2e proof (scripted-provider co-author flow + headless park control) → closes INT-US-02
and the **US-2 epic** (unblocks US-21).
