# Design: Envelope-vs-Content Prompt Externalization

- **Feature ID**: C-INTL-06
- **Epic**: Topic 04 (Intelligence)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Architecture-direction review (2026-07-21, Steve Bula + Claude) — the "middle way" applied to
  prompt assembly. Minted as a **new** story because the affected capabilities are already delivered and
  remain ✅/finished (`C-INTL-05` Configurable Prompt Render Profiles, `B-INTL-09` Agent Memory Bank slot
  hydration, `D-INTL-05` metadata injection lineage): completed stories are not reopened — their evolution is
  tracked here.
- **DAL**: C (Enterprise Standard)

## Problem Statement

The `PromptBuilder` slot/profile machinery (~4,800 lines across `infrastructure/llm`, incl. `prompt/adders.py`
477 + `prompt/builder.py` 304) conflates two different responsibilities:

1. **Envelope** — deterministic guarantees: block structure, injection safety (`TECH-007`), metadata
   (`PromptSafeConfig`), rendering profiles, the 2-Tier Handover standard. Harness territory; must stay code.
2. **Content** — knowledge injected through slots: constitution, standards, agent memory (hydration in
   `_build_base_prompt`), plan/context blocks. Knowledge territory; every new context source grows the
   assembly machinery (the exact compounding problem `TECH-006` documented as the RunContext god object +
   cross-interface loader spider-web).

With `C-FLOW-11` (graduated autonomy), agentic work units don't consume assembled prompts at all — an agent
*reads* constitution/standards/rubrics as mounted files and *pulls* memory via a tool. Keeping content in
slots then means maintaining two divergent context paths.

## Goal

**Narrow the PromptBuilder to the envelope; externalize the content.**

1. Constitution, standards, and guidance content become **mounted files** (canonical on-disk artifacts) that
   `C-FLOW-11` work units read directly; `oneshot` mode keeps working by having thin slots *reference the
   same files* (single source of truth, no behavioral change to shipped `C-INTL-05` profiles).
2. Agent-memory access for work units becomes **pull-based** (a memory tool/file view over the `B-INTL-09`
   repository) instead of slot injection; `oneshot` hydration stays as-is.
3. The envelope (structure, escaping, metadata, profiles) is explicitly declared the *only* long-term
   responsibility of `PromptBuilder`; new context sources land as files/rubrics, not adders.

## Relationship
- **Evolves (without reopening)**: `C-INTL-05` ✅ (profiles = envelope engine of oneshot mode), `B-INTL-09`
  (memory pull path), `D-INTL-05` ✅ (metadata stays envelope).
- **Consumes/serves**: `C-FLOW-11` (work-unit context mounting), `C-VAL-05` (rubrics are one content class).
- **Redirects**: `TECH-006`'s "move loading inside the prompt factory" recommendation — the destination
  becomes domain loaders + mounted files, not deeper factory centralization (Findings 1–2 stay valid).
- **Unaffected**: `TECH-007` escaping — a pure envelope concern, needed in both modes.

## Candidate Approaches (not yet designed)
1. Canonical context directory (e.g. `.specweaver/context/` or existing file locations) + a tiny resolver
   both modes share — recommended.
2. Memory pull: read-only tool surface over `MemoryRepository` for work units (role/DAL-gated).
3. Migration order: constitution/standards first (already files — mostly de-duplication of loaders), memory
   second, then declare the adders API frozen.

## Non-Goals (proposed, pending design)
- Removing profiles/slots (oneshot compat is permanent until the dial says otherwise).
- Any change to shipped `C-INTL-05` behavior or its ✅ status.
- Prompt *optimization* (`B-INTL-10` — separately re-scoped against this direction).

## Next Step
Run `specweaver-design C-INTL-06` after (or together with) `C-FLOW-11` intake — the work-unit context-mounting
contract is the forcing function.
