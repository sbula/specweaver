# US-04 Integration - Integration Contracts

## Base Story Contract (`INT-US-04`)
* **Status:** ✅ Complete (2026-08-15) — persistence delivered by `SF-01` across four commit
  boundaries (`e400cfdb`, `3e8c29f9`, `9a81719f`, `b15d372f`); `check_fr_coverage.py INT-US-04`
  exits 0. This line read `✅ Complete` from 2026-07 over unbuilt work, was corrected to `⬜ Pending`
  on 2026-08-14, and is now earned. **Two clauses of the description below are still not satisfied
  as written, and are recorded rather than papered over:** the store is `pipeline_state.db`, **not**
  the Config DB (`E-FLOW-01`) — a deliberate config/state separation, `INT-US-04_design.md` §Scope
  decision — and *sanitized* maps to `E-VAL-03`, which is unbuilt. See the proof matrix's `C1`/`C2`.
* **Integration Description:** The SQLite Config DB (`E-FLOW-01`) must statefully persist outputs
  from the Validation Engine (`E-VAL-01`), allowing the Pipeline Runner (`D-FLOW-01`) to pass
  sanitized, verified context into subsequent prompt steps.
* **Verifiable Proof:** `tests/e2e/capabilities/assurance/test_mcp_flow_e2e.py`,
  `tests/integration/core/flow/engine/test_validation_results_persistence.py`,
  `tests/integration/core/flow/engine/test_feedback_replay_across_resume.py`

> [!NOTE]
> **The description above is unchanged and must stay so** (`finished-stories-immutable`). The two
> unsatisfied clauses were NOT re-worded to make the `✅` fit — that is exactly what `TECH-017`
> `NFR-1` forbids, and the matrix records the mismatch instead of erasing it.

## Sub-Story Add-Ons

US-4's sub-story contracts (`INT-US-04-SF02` … `SF-08`) are defined per-section in
[INT-US-04_design.md](../../features/topic_08_integration/INT-US-04/INT-US-04_design.md) — see the
master roadmap's US-4 add-on groups for the current status of each.

* **`INT-US-04-SF09` — Declarative Dynamic Prompt Routing:** *Pending Design (minted 2026-07-24
  audit — every add-on group carries its own integration story).* Integrates `B-INTL-10`
  Declarative Prompt Optimization: DSPy-style declarative routing, with the `PipelineRunner`
  fetching and compiling an optimized prompt profile from runtime routing, telemetry and active
  models.

  > **RETIRED 2026-08-13 by `ADR-003`.** Never designed; its roadmap placeholder was removed in
  > `bb789a29` with the other 62. The scope above is NOT descoped — it moves to `B-INTL-10`, which
  > owns its own integration and e2e proof as FRs rather than a separate add-on restating them.
  >
  > **Recorded 2026-08-15.** SF-09 was the one placeholder of the 60 that lost its roadmap line
  > without gaining this note, because — unlike `SF-02`/`05`/`06`/`07` — it had no `RETIRED →
  > owner` line to carry the redirect and no design-doc anchor to link. It therefore survived in
  > the design doc's tracker as the last `⬜` under a `✅` contract, and the Session Handoff cited
  > it as the reason `INT-US-04` could not close. It was never a blocker; nothing was waiting on it.
  >
  > Note that `B-INTL-10` is itself `🔮` and carries an explicit re-scope warning
  > (`topic_04_intelligence.md`): premised on owning slot-prompt assembly, the layer `C-INTL-06` /
  > `C-FLOW-11` shrink — *"at design time either re-scope the optimization target to rubric/skill
  > content (`C-VAL-05` artifacts) or retire."* Designing an integration contract for it now would
  > have been designing against a capability that may not survive its own design.

* **`INT-US-04-SF10` — Envelope-vs-Content Prompt Externalization:** *Pending Design (minted
  2026-07-24 audit — every add-on group carries its own integration story).* Integrates
  `C-INTL-06` (unbuilt, middle-way): wires the externalized envelope/content split into the live
  prompt-assembly surfaces once the capability lands; sequenced behind `C-VAL-05` per the
  middle-way ordering.

  > **RETIRED 2026-08-13 by `ADR-003`.** Never designed; its roadmap placeholder is gone.
  > The scope above is NOT descoped — it moves to `C-INTL-06`, which owns its own
  > integration and e2e proof as FRs rather than a separate add-on restating them.

