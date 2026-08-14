# US-04 Integration - Integration Contracts

## Base Story Contract (`INT-US-04`)
* **Status:** ⬜ Pending — **corrected 2026-08-14, was `✅ Complete`.** The description below claims
  the Config DB persists Validation Engine outputs. **That surface was never built:** the config DB
  has no validation table and `ValidationResult` does not appear in `src/`. `SF-01: Core Flow DB
  Integration` carries it and stands at Design ✅, Impl Plan ⬜, Dev ⬜ — designed 2026-07, never
  implemented, while this line read `✅ Complete` for the whole period.
  **Delivered and unaffected by the correction:** the SF-03, SF-04 and SF-08 add-ons, and the
  context-assembly half of the description (`test_mcp_flow_e2e_fetch`). Only the *persistence* half
  is missing, which is why the marker is wrong rather than the work absent.
  Evidence: `docs/analysis/integration_contract_proof_matrix.md` (`INT-US-04` C1/C2, both
  `unproven`); scope decided in `INT-US-04_design.md` §Scope decision.
* **Integration Description:** The SQLite Config DB (`E-FLOW-01`) must statefully persist outputs
  from the Validation Engine (`E-VAL-01`), allowing the Pipeline Runner (`D-FLOW-01`) to pass
  sanitized, verified context into subsequent prompt steps.
* **Verifiable Proof:** `tests/e2e/capabilities/assurance/test_mcp_flow_e2e.py`

> [!NOTE]
> **The description above is unchanged and must stay so** (`finished-stories-immutable`). Correcting
> a false *status marker* is not editing a delivered contract's scope — nothing was delivered under
> it. The `sanitized` clause is not deliverable by SF-01 at all: it maps to `E-VAL-03` (AST Prompt
> Injection Sanitization), which is `🔜` unbuilt, so C2's sanitization half stays `unproven`
> regardless of how SF-01 lands.

## Sub-Story Add-Ons

US-4's sub-story contracts (`INT-US-04-SF02` … `SF-09`) are defined per-section in
[INT-US-04_design.md](../../features/topic_08_integration/INT-US-04/INT-US-04_design.md) — see the
master roadmap's US-4 add-on groups for the current status of each.

* **`INT-US-04-SF10` — Envelope-vs-Content Prompt Externalization:** *Pending Design (minted
  2026-07-24 audit — every add-on group carries its own integration story).* Integrates
  `C-INTL-06` (unbuilt, middle-way): wires the externalized envelope/content split into the live
  prompt-assembly surfaces once the capability lands; sequenced behind `C-VAL-05` per the
  middle-way ordering.

  > **RETIRED 2026-08-13 by `ADR-003`.** Never designed; its roadmap placeholder is gone.
  > The scope above is NOT descoped — it moves to `C-INTL-06`, which owns its own
  > integration and e2e proof as FRs rather than a separate add-on restating them.

