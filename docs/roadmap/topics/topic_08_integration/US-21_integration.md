# US-21: Autonomous Feature Decomposition - Integration Contracts

## Base Story Contract (`INT-US-21`)
* **Status:** ✅ Complete (2026-07-28) — [design](../../features/topic_08_integration/INT-US-21/INT-US-21_design.md); SF-01 (`f1de38f1` registry completeness + `c4c1a109` plan hydration bridge + `6811a943` cross-session rehydration + `5ebcc414` HITL approve-on-resume) + SF-02 (`4a42b87a` artifact persistence + `ce00be20` stub component specs + `5aa20ffa` plan-bridge seam pin & DAL summary) + SF-03 (`8fff2470` bare-name resolution + `d0c020f4` collision reporting & interrupt run id + `ccdda8f8` verifiable proof + `39aa3860` interrupt survival) all committed. Closing this contract closes the **US-21 epic**. Scope was re-cut mid-flight (`52ef2cdf`): `FR-9(a)`'s fan-out pin was descoped because it would have frozen a guess at an undesigned consumer, and `AD-9`'s delivered-add-on audit moved to `TECH-018` so an audit of a *different* story could not gate this epic's closure.
* **Integration Description:** `sw run feature_decomposition <spec|name>` is a working three-session journey: draft (exists-skip) → **park** → resume-as-approval → validate at feature thresholds → decompose → **park** → resume-as-approval → COMPLETED, producing a durable uuid-tagged `<stem>_decomposition.yaml` plus one never-overwritten stub component spec per DAG node, at a cost of exactly one LLM call. It solves the built-but-not-integrated problem: `D-INTL-02` and `D-INTL-03` shipped capabilities behind a pipeline that could not execute a single step (unregistered handlers), a `context.plan` documented as hook-populated with **zero writes in `src/`**, a flow engine with no HITL approval semantics (`sw resume` re-parked forever, proven empirically), and a plan artifact that was never persisted. All four are closed. Autonomous DAG *execution* is deliberately delegated to `C-FLOW-12` / `INT-US-21-SF02`, sequenced behind `C-EXEC-07` and `TECH-014`.
* **Verifiable Proof:** `tests/e2e/capabilities/workflows/test_feature_decomposition_e2e.py` — 22 scenarios on the REAL CLI (scripted LLM only, with `ModelRouter.get_for_task` patched to `None` so the router cannot build a live provider around the factory patch). **The first test in the suite to drive a bundled pipeline THROUGH a HITL gate**, and every assertion reads the persisted run status rather than the exit code, because `PARKED` and `COMPLETED` both exit `0` — the precise reason `INT-US-02`'s E6/E7 were green for months without ever advancing past their first gate. Covers: the happy three-session journey (both approve-on-resume advances, one LLM call, artifact + stub inventory) · coverage<1.0 → failed-gate park · malformed LLM JSON · missing spec · cross-session rehydration matching the on-disk artifact · zero-component plan · stub no-overwrite · validate-fails → loop_back → draft park · feature-spec name collision · journey re-run reusing the artifact identity · refusal to resume a finished run · interrupt survival and resumability. Plus `tests/integration/core/flow/handlers/test_decomposition_artifacts_integration.py` (33) and `tests/integration/core/flow/engine/test_seam_pins.py` (4, the hook-driven plan bridge).

## Sub-Story Add-Ons

* **Recursive Planning (`INT-US-21-SUB`)**
  * **Status:** ✅ Complete
  * **Integration Description:** The `C-INTL-01` feature implements iterative decomposition, generating a structured DecompositionPlan by resolving the AST graph into sub-tasks.
  * **Verifiable Proof:** Covered by integration testing under `pytest -m integration` and the `FeatureDecomposer` suite.

* **Autonomous DAG Execution (`INT-US-21-SF02`)**
  * **Status:** ⬜ Pending Design
  * **Integration Description:** Integrates `C-FLOW-12` — per-component spec synthesis, race-hardened fan-out, and `proposed_dal`-driven run isolation — on top of the base contract's frozen seams (`context.decomposition` via the shared `DECOMPOSITION_PLAN_KEY`, the `<stem>_decomposition.yaml` schema, stub spec paths, `proposed_dal` presence, approve-on-resume). Sequenced behind `C-EXEC-07` (isolation posture) and `TECH-014` (the fan-out shared-`RunContext` race, which this capability would be the first to actually exercise).
  * **Verifiable Proof:** [Pending — writes its own seam pin as its first commit, against a contract it can see. The base deliberately does **not** ship a forward-compatibility pin on its behalf: `FR-9(a)` attempted that and was descoped.]

---

> **Re-validation of the delivered add-on — `TECH-018`.** `INT-US-21-SUB` was proven against a
> decomposition path that was never runnable end to end (the four gaps named in the base contract
> above meant `sw run feature_decomposition` could not execute step 1), so its integration claim
> was never exercised through a real journey. Auditing it against the now-integrated base is
> tracked as `TECH-018` — audit-only, findings become new stories, and it does **not** gate this
> epic. Recorded here rather than inside the delivered entry, which stays untouched.

> **Naming note (OQ-1, resolved 2026-07-25).** This file keeps `INT-US-21-SUB` for the delivered
> Recursive-Planning add-on while `master_story_roadmap.md` spells the same add-on
> `INT-US-21-SF01`. The divergence is accepted and documented rather than corrected, because
> renaming a delivered entry's identifier would breach the finished-stories-immutable rule.
> Recorded so no future session re-opens it as registry corruption.
