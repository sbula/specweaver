# US-02 Integration - Integration Contracts

## Base Story Contract (`INT-US-02`)
* **Status:** 🟡 In Progress — [design APPROVED 2026-07-22](../../features/topic_08_integration/INT-US-02/INT-US-02_design.md); SF-01 implementation plan next.
* **Integration Description:** The interactive loop (`E-INTL-02`) must seamlessly hand off the generated context to the Review Engine, ensuring no manual copy-pasting is required.
* **Verifiable Proof:** `[Pending e2e draft test]`

## Sub-Story Add-Ons

* **`INT-US-02-SF01` — Surgical Spec Refactoring:** *Pending Design.* Depends on `D-SENS-05` (Markdown AST Mutators, unbuilt).
* **`INT-US-02-SF02` — Remote UI Integration:** *Pending Design.* Depends on `D-UI-04` (REST API Interactive Authoring, unbuilt).
* **`INT-US-02-SF03` — Grill-Style Agentic Drafting:** *Pending Design (minted 2026-07-22).* **Integrates the
  capability `D-INTL-07`** (Agentic Interview Drafting — adaptive grilling interview + `/to-spec`-style
  synthesis, rubric-content-driven) into the drafting flow via the `C-FLOW-11` draft-step dial. Like every
  add-on, the SF is **integration only** — the engine build lives in the capability. The base contract's
  gates (S-battery → semantic review → bounded loop, provider wiring, proof) are reused verbatim: they gate
  whatever engine produced the spec. Whether `D-INTL-07` **replaces** the `E-INTL-02` engine or leaves it as
  the oneshot/headless fallback mode is decided at `D-INTL-07`'s design intake (the finished `E-INTL-02`
  spec remains an immutable record either way). **Blocked on `C-FLOW-11`** (hard) + `C-VAL-05` (soft);
  deliberately sequenced AFTER the base contract closes US-2 (timeline decision Option A, 2026-07-22).
