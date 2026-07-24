# US-04 Integration - Integration Contracts

## Base Story Contract (`INT-US-04`)
* **Status:** ✅ Complete
* **Integration Description:** The SQLite Config DB (`E-FLOW-01`) must statefully persist outputs from the Validation Engine (`E-VAL-01`), allowing the Pipeline Runner (`D-FLOW-01`) to pass sanitized, verified context into subsequent prompt steps.
* **Verifiable Proof:** `tests/e2e/capabilities/assurance/test_mcp_flow_e2e.py`

## Sub-Story Add-Ons

US-4's sub-story contracts (`INT-US-04-SF02` … `SF-09`) are defined per-section in
[INT-US-04_design.md](../../features/topic_08_integration/INT-US-04/INT-US-04_design.md) — see the
master roadmap's US-4 add-on groups for the current status of each.

* **`INT-US-04-SF10` — Envelope-vs-Content Prompt Externalization:** *Pending Design (minted
  2026-07-24 audit — every add-on group carries its own integration story).* Integrates
  `C-INTL-06` (unbuilt, middle-way): wires the externalized envelope/content split into the live
  prompt-assembly surfaces once the capability lands; sequenced behind `C-VAL-05` per the
  middle-way ordering.
