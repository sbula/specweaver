# Design: Interactive Drafter Integration (INT-US-02)

- **Feature ID**: INT-US-02
- **Phase**: 6
- **Status**: APPROVED — approved by Steve Bula on 2026-07-22 (AD-1..5 confirmed; **AD-6 resolved to (a)** — feedback-aware re-draft).
- **Design Doc**: docs/roadmap/features/topic_08_integration/INT-US-02/INT-US-02_design.md

## Feature Overview

Feature INT-US-02 closes the US-2 flagship loop: *co-author a spec with the LLM section-by-section, and
have it validated and semantically reviewed with **zero manual copy-pasting***. All six Core-Required
capabilities are ✅ built; today they form **two half-loops that never meet**:

1. **`sw draft <name>`** (registered in the review CLI module) runs a **single-step** `draft_spec`
   pipeline with the interactive `HITLProvider` — co-authoring works — then stops and prints
   *"Run 'sw check' to validate the drafted spec."* — the manual handoff the contract forbids
   (the same defect shape `INT-US-03` removed from `sw implement`).
2. **`sw run new_feature <name>`** has the full `draft_spec → validate_spec → review_spec` chain with
   `loop_back` — but its composition root **never wires a `context_provider`**, so `DraftSpecHandler`
   **parks** ("write the spec manually, then `sw resume`") instead of co-authoring.

The contract joins the halves: `sw draft` gains the in-pipeline validate+review chain (with the bounded
draft↔review reflection loop), and the `sw run`/`sw resume` composition roots gain TTY-gated
`HITLProvider` wiring so `new_feature` co-authors instead of parking. **Integration-only** — no new
capability, no new prompt machinery (middle-way constraint: drafting/review guidance stays
knowledge-shaped content; future rubric externalization is `C-VAL-05`, out of scope here).

## Research Findings

### Codebase Patterns

**What already exists (all US-2 Core deps ✅ — this is pure integration):**

- **`sw draft` (E-INTL-02)** — `workflows/review/interfaces/cli.py` (`@review_cli.command(name="draft")`,
  registered via `main.py:109 add_typer(review_cli)`). Builds
  `PipelineDefinition.create_single_step(name="draft_spec", ...)`, wires
  `context_provider=HITLProvider(console=_core.console)` (`:111`), runs via `PipelineRunner`, then prints
  the stale *"Run 'sw check'…"* next-step message and exits. Loads settings with `llm_role="draft"`.
- **`DraftSpecHandler` (`core/flow/handlers/draft.py`)** — `DRAFT+SPEC` handler: spec exists → PASSED
  (skip); provider+llm present → `_execute_drafting` (builds `Drafter` with `_build_base_prompt`
  INTERACTIVE profile — **D-INTL-05 metadata + constitution/standards already injected here**); otherwise
  → **PARKS** ("spec creation parking") for `sw resume`.
- **`Drafter` (`workflows/drafting/drafter.py`)** — the section-by-section interactive engine
  (`SectionDef`, topology contexts, lineage UUID stamping).
- **`HITLProvider` (`interfaces/cli/hitl_provider.py`)** — Rich-prompt ContextProvider (terminal-coupled).
- **Spec validation (E-VAL-01/US-1)** — `VALIDATE+SPEC` step runs the S01–S12 battery
  (`validation_spec_*.yaml` presets); gate `all_passed`.
- **`ReviewSpecHandler` (`core/flow/handlers/review.py:155-168`)** — LLM semantic review; PASSED iff
  `verdict == "accepted"`, outputs `{verdict, findings…}` — gate condition `accepted` already used by
  `new_feature.yaml`.
- **`new_feature.yaml`** — `draft_spec (hitl gate) → validate_spec (auto, on_fail abort) → review_spec
  (auto, `on_fail: loop_back → draft_spec`)` → generation steps. **Defect claim corrected (2026-07-22,
  SF-01 Phase 0):** the gate omits `max_retries`, but `GateDefinition.max_retries` defaults to **3**
  (`models.py:160`) — the loop was bounded-but-DEAD (see next bullet), not unbounded. FR-7 shrinks to
  making the bound explicit (`max_retries: 2`, `INT-US-03` parity).
- **Composition-root gap (the crux):** `flow/interfaces/cli.py` `_execute_run` (`:251-259`) and `resume`
  (`:452-460`) build `RunContext` **without** `context_provider` — the only `HITLProvider` wiring in the
  entire codebase is the `sw draft` command. `DraftSpecHandler`'s park path is therefore the ONLY behavior
  `sw run new_feature` can exhibit for a missing spec.
- **Dead rejection loop (defect found by this design's Red/Blue):** `DraftSpecHandler`'s FIRST check is
  *spec exists → PASSED (skip)*. Therefore `new_feature.yaml`'s `review_spec` `on_fail: loop_back →
  draft_spec` re-enters a handler that **skips** — the shipped rejection loop has ALWAYS been dead
  (validate→review→fail→skip→… until abort), masked because the unwired provider meant nobody ever
  reached it interactively. Any variant of this contract must make re-drafting real (AD-6) or the
  `accepted`-gated loop is theater.
- **Structural precedent:** `INT-US-03` (✅ closed) — extend the command's inline pipeline (AD-1 there),
  wire policy/context at the composition root (AD-2 there), verifiable-proof e2e with paired controls
  (NFR-6 there). This contract deliberately mirrors that shape.

**Modules touched:** `workflows/review/interfaces/cli.py` (extend `sw draft` inline pipeline + report),
`core/flow/interfaces/cli.py` (TTY-gated provider wiring), `workflows/pipelines/new_feature.yaml`
(bound the review loop), `tests/` (proof). No new module, no handler changes, no prompt-machinery changes.

**Boundary rules:** `workflows/review` already imports flow symbols + `HITLProvider`;
`core/flow/interfaces` already imports from `interfaces/cli` siblings? — NO: `hitl_provider.py` lives in
`interfaces/cli/` (top-level delivery layer) while `flow/interfaces/cli.py` is `core.flow.interfaces`.
Wiring the provider there means `core.flow.interfaces → interfaces.cli` — a **wrong-direction import**
(core must not depend on the delivery layer). Resolution: inject the provider from `interfaces/cli/main.py`
routing (the layer that already owns `HITLProvider`) or pass a factory — decided in AD-2. `tach check`
must stay green.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| — | — | No external tool; pure internal integration (Rich prompts already vendored) | — |

Internet research not applicable — no new external dependency or algorithm; all surfaces are in-repo.

### Blueprint References
`INT-US-03` (inline-pipeline extension + composition wiring + proof pattern) and the `INT-US-09` e2e
control-test pattern (`test_int_us_09_isolation_e2e.py`).

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | In-pipeline validate | `sw draft` pipeline | SHALL append `validate_spec` (`VALIDATE`/`SPEC`, S-battery) after `draft_spec` in the inline pipeline. | A co-authored spec is validated immediately; failures reported inline. |
| FR-2 | In-pipeline semantic review | `sw draft` pipeline | SHALL append `review_spec` (`REVIEW`/`SPEC`) after validation, gate `condition: accepted`. | The Review Engine judges the draft with no manual handoff (the contract's core sentence). |
| FR-3 | Bounded reflection loop | `sw draft` pipeline | SHALL gate `review_spec` with `on_fail: loop_back → draft_spec`, **`max_retries: 2`**; the re-entered draft step SHALL actually re-draft with the reviewer findings (AD-6 — today it would skip on "spec exists", making the loop dead); on exhaustion surface the findings and exit non-zero. | Rejected drafts get REAL bounded re-drafting with reviewer findings fed back; no unbounded LLM spend. |
| FR-4 | Composition-root provider wiring | `sw run` / `sw resume` | SHALL wire the interactive `HITLProvider` into `RunContext.context_provider` **when attached to an interactive terminal (TTY)**, injected without a core→delivery import (AD-2). | `sw run new_feature <name>` co-authors instead of parking; layering stays legal. |
| FR-5 | Headless behavior preserved | `sw run` / `sw resume` | SHALL keep the park-for-user-input behavior byte-identical when no TTY (CI, scripts, API) or when the spec already exists. | Zero regression for autonomous/headless flows; parking remains the headless contract. |
| FR-6 | Inline outcome reporting | `sw draft` command | SHALL report validation + review outcomes inline (rules passed/failed, verdict, findings count, retries used) and REMOVE the stale "Run 'sw check'…" message. | One command shows the whole result; no manual follow-up implied. |
| FR-7 | Explicit loop bound | `new_feature.yaml` | SHALL add an explicit `max_retries: 2` to the `review_spec` loop_back gate *(corrected 2026-07-22: the default bound is 3, not unbounded — this is parity/self-documentation, not a fix; the real defect is the dead loop, fixed by FR-3/AD-6)*. | The shipped pipeline's loop bound is explicit and consistent with `INT-US-03`. |
| FR-8 | Verifiable proof | test suite | SHALL provide an e2e driving draft→validate→review through the real `PipelineRunner` with a **scripted ContextProvider** (deterministic answers) + mocked LLM verdicts: [accept path], [reject→loop_back→re-draft→accept], [retries exhausted → non-zero + findings], and a **headless control** proving `sw run` without TTY still parks. | The contract's Verifiable Proof is a real, unmocked-runner, CI-runnable test; the park control guards FR-5. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Integration-only | No new capability, handler, or prompt machinery (middle-way: drafting/review guidance stays content-shaped; rubric externalization = `C-VAL-05`, out of scope). |
| NFR-2 | Backward compatibility | Headless `sw run`/`resume` and existing `sw draft` happy path byte-identical except the added chain + report; parking semantics unchanged without TTY. |
| NFR-3 | Bounded cost | All reflection loops `max_retries ≤ 2`; no unbounded LLM spend (fixes the found defect). |
| NFR-4 | Architecture compliance | No `core.flow.interfaces → interfaces.cli` import (AD-2 injection); `tach`/`ruff`/`mypy --strict` green. |
| NFR-5 | Deterministic proof | The e2e uses a scripted provider + mocked LLM (no live keys, no prompts blocking CI); includes the headless park control (INT-US-09 discriminator pattern). |
| NFR-6 | Terminal-coupling containment | `HITLProvider` (Rich) stays in the delivery layer; core sees only the `ContextProvider` protocol. |

## External Dependencies
| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| — | — | none new | — | Pure internal integration. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Extend `sw draft`'s **existing inline** pipeline (draft→validate→review) rather than switching the command to load `new_feature.yaml`. | `new_feature.yaml` continues into code generation — wrong for a drafting command. Mirrors `INT-US-03` AD-1 (proven shape); minimal, in-module. | No |
| AD-2 | Wire `HITLProvider` at the composition root **by injection from the delivery layer**: the `interfaces/cli` layer (which already owns `HITLProvider`) passes a provider (or factory) into the flow CLI's context construction, gated on `sys.stdin.isatty()`. Core imports only the `ContextProvider` protocol. | The naive wiring (`core.flow.interfaces` importing `interfaces.cli.hitl_provider`) is a wrong-direction dependency; injection keeps the boundary clean (NFR-4/NFR-6) and the TTY gate keeps headless parking intact (FR-5). Exact mechanism (parameter vs. small provider-registry) chosen at impl-plan time. | No (composition wiring; same class as `INT-US-03` AD-2). |
| AD-3 | Leave the `draft` command's **module home** (`workflows/review/interfaces/cli.py`) untouched. | Moving it to `workflows/drafting/interfaces/` is a placement cleanup with zero user-facing value — `TECH-006`-class refactoring; noted as a Refactoring Opportunity, not contract scope. | No |
| AD-4 | Fix the unbounded `review_spec` loop in `new_feature.yaml` **inside this contract** (FR-7) rather than minting a separate TECH ticket. | One-line gate change, discovered by this design's research, tested by this contract's proof; a ticket would be bloat (per 2026-07-21 no-bloat guidance). | No |
| AD-5 | Reviewer findings feed the re-draft via the existing feedback mechanism (`loop_back` carries step output into `context.feedback`, as `INT-US-03`'s QA loop does). | Reuse, not invention; the Drafter already receives base-prompt context. Verified at impl-plan time; if the drafting path ignores `context.feedback`, the impl plan surfaces it as a gap (not silently absorbed). | No |
| AD-6 | **[RESOLVED — approved by Steve Bula 2026-07-22: option (a)]** Make the rejection loop REAL: `DraftSpecHandler` becomes **feedback-aware** — when re-entered via `loop_back` with reviewer findings in `context.feedback`, it re-drafts (regenerates the spec incorporating the findings, bounded by `max_retries`) instead of skipping on "spec exists". Alternatives considered: **(b)** park-with-findings for manual editing (reintroduces the manual step the contract forbids); **(c)** no loop in v1 — single pass, rejection = report + exit (but re-running `sw draft` also skips on the existing spec, stranding the user in manual editing anyway). | The shipped `loop_back → draft_spec` gate is dead code today (see Research Findings) — (a) is the only option that delivers US-2's benefit AND fixes the latent defect. It is a small, targeted handler change: integration glue in the `INT-US-03` SF-02 precedent class (LintFixHandler target fix), not a new capability. Full *surgical* revision (AST mutators) remains `INT-US-02-SF01` add-on territory — (a) regenerates whole-spec with findings, which is base-grade. | No (handler glue + defect fix; flagged for explicit sign-off because it modifies a shipped handler's skip semantics — narrowly, only on the feedback-bearing loop_back path). |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| Extend `sw draft` inline pipeline + inline report | Low (single file + yaml gate) | Low — steps/handlers exist |
| TTY-gated provider injection at composition roots | Low-Medium (layering care, AD-2) | Medium — touches `sw run`/`resume` construction |
| `new_feature.yaml` loop bound | Trivial | Low |
| e2e proof (scripted provider + controls) | Medium | Low — mirrors shipped proof patterns |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| End user | "Co-author → validated → reviewed" in one command; `new_feature` finally co-authors instead of parking | High — closes the US-2 flagship epic |
| US-21 (Autonomous Decomposition) | Its ONLY blocker is US-2 Core → becomes integration-only | High |
| US-8 / US-12 / US-14 | US-2 Core dependency satisfied (each retains one other blocker) | Medium (cascading) |
| Cost posture | Unbounded review loop bounded (defect fix) | Medium |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| TTY-gated provider changes `sw run` behavior for interactive users who EXPECTED parking | Low | Low | It replaces a dead-end (park + manual spec authoring) with the designed co-author flow; headless unchanged (FR-5); document in the run output. |
| Review loop_back re-draft ignores reviewer findings (weak loop) | Medium | Medium | AD-5 — verified at impl-plan time against the existing feedback plumbing; surfaced as gap if absent. |
| Interactive prompts block CI if TTY misdetected | Low | Medium | Gate strictly on `isatty()`; the headless park control (FR-8) is the regression tripwire. |
| Scope creep into drafting-content quality (rubrics, question flows) | — | — | NFR-1; that is `C-VAL-05`/`D-INTL-04` territory. |

### Refactoring Opportunities
| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| `draft` command placement | Lives in `workflows/review/interfaces/cli.py` | Move to `workflows/drafting/interfaces/` (TECH-006-class cleanup) | Low (follow-up) |
| Review criteria in handler prompts | Frozen judgment content | Externalize rubric-first once `C-VAL-05` lands | — (separate story) |

## Developer Guides Required
| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Interactive drafting loop | Update the drafting section of the user/dev guides: one-command draft→validate→review, TTY vs headless behavior | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-01: Draft → Validate → Review Inline Chain
- **Scope**: Extend `sw draft`'s inline pipeline with `validate_spec` + `review_spec` (gate `accepted`,
  `loop_back → draft_spec`, `max_retries: 2`); make `DraftSpecHandler` feedback-aware on the loop_back
  path so the rejection loop is real (AD-6, pending its sign-off); inline outcome report; remove the stale
  "Run 'sw check'…" message; apply the same `max_retries` bound to `new_feature.yaml`'s review gate (FR-7).
- **FRs**: [FR-1, FR-2, FR-3, FR-6, FR-7]
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-02/INT-US-02_sf01_implementation_plan.md

### SF-02: Composition-Root Provider Wiring (TTY-Gated)
- **Scope**: Inject the interactive provider into `sw run`/`sw resume` context construction from the
  delivery layer (AD-2), gated on `isatty()`; headless parking byte-identical (FR-5); no core→delivery import.
- **FRs**: [FR-4, FR-5]
- **Depends on**: none (parallel-safe with SF-01, but executed serially per repo convention)
- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-02/INT-US-02_sf02_implementation_plan.md

### SF-03: Verifiable Proof
- **Scope**: The FR-8 e2e: scripted ContextProvider + mocked LLM through the real runner — accept path,
  reject→loop_back→accept path, retries-exhausted path, headless park control. Closes the contract.
- **FRs**: [FR-8]
- **Depends on**: SF-01, SF-02
- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-02/INT-US-02_sf03_implementation_plan.md

## Execution Order
1. **SF-01** — inline chain (no deps)
2. **SF-02** — provider wiring (after SF-01, serial per convention)
3. **SF-03** — proof (depends on SF-01, SF-02)

Linear DAG; acyclic.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Draft → Validate → Review Inline Chain | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Composition-Root Provider Wiring | SF-01 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| SF-03 | Verifiable Proof | SF-01, SF-02 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff
**Current status**: Design **APPROVED** (2026-07-22) — AD-6 = (a) feedback-aware re-draft.
**Execution discipline (2026-07-22, post `D-INTL-07` minting — scope UNCHANGED):** the drafting engine is a
supersession target (`D-INTL-07`/`INT-US-02-SF03`, blocked on `C-FLOW-11`). Therefore: (1) engine-coupled
internals (AD-6a findings-injection plumbing) at **minimal depth** — smallest working version, no prompt
polish; (2) **investment freeze** on the `E-INTL-02` engine — no `SPEC_SECTIONS` tuning or Drafter refactors;
(3) **seam-first tests** — assert the feedback/re-draft/park contract, not Drafter internals; (4) SF-02
planning: prefer the AD-2 mechanism shape (provider factory) that stays engine-neutral. The gates/wiring this
contract builds are the permanent harness the replacement engine will be verified by.
**Next step**: On approval → `/specweaver-implementation-plan INT-US-02 SF-01`.
**If resuming mid-feature**: Read the Progress Tracker; resume at the first ⬜.
