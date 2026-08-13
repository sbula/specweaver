# US-24: Behavioral Scenario Verification - Integration Contracts

## Base Story Contract (`INT-US-24`)
* **Status:** ✅ Complete (2026-07-24) —
  [design](../../features/topic_08_integration/INT-US-24/INT-US-24_design.md); SF-01 (`3fece855`
  dual dispatch + arbiter evidence contract + false-green fix) + SF-02 (`7e3cb13c` feedback loop
  closed on both verdict branches, NFR-8 opacity seam-pinned) + SF-03 (`08cffe0d` CLI journey +
  verifiable proof + converter repair) all committed. Closing this contract closes the **US-24
  epic**. Ten inherited defects were flushed across the three SFs (dead dual dispatch, evidence
  starvation, TWO false-green layers — the `kind: scenario` marker and the STUB converter bodies — a
  pytest-parser miscount in D-VAL-01's core, the dual-fan-out HITL deadlock, the LLMResponse
  contract in generator+arbiter, and `sw resume` never wiring the LLM).
* **Integration Description:** The already-built Scenario Testing Pipeline (`B-FLOW-01`: contract
  extraction → parallel coding + scenario pipelines → JOIN → scenario test execution → arbiter fault
  attribution) is wired into a real, working `sw run scenario_integration <spec>` journey executed
  through the QA Runner (`D-VAL-01`) on top of the shipped US-3 loop. Green verification rounds cost
  ZERO arbitration LLM calls; a parked `spec_ambiguity` heals through the loop on `sw resume`
  (evidence re-publishes on the fresh round). DAL escalation for run journeys is deliberately
  delegated to `C-EXEC-07`/`INT-US-09-SF06` (US-9 add-on).
* **Verifiable Proof:** `tests/e2e/capabilities/workflows/test_scenario_verification_e2e.py` — 9
  scenarios on the REAL CLI (scripted LLM adapter; real contract extraction, converter, pytest
  subprocesses, arbiter, gates, park state; the coding sub-pipeline doubled at the US-3 boundary
  with a scripted buggy→fixed implementer): happy · code_bug loop → fix → green · scenario_error
  loop → regeneration-with-delta · ambiguity park · retries exhausted · zero-collected loud ·
  park-heals-through-the-loop resume · degraded resume without LLM · generator exhaustion. Plus
  `tests/integration/workflows/scenarios/test_converter_execution.py` (emitted tests genuinely
  execute AND genuinely fail).

## Sub-Story Add-Ons

* No explicit sub-story contracts defined yet.
