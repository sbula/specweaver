# C-INTL-06 — Envelope-vs-Content Prompt Externalization

**Status**: STUB — not yet run through the `specweaver-design` skill · **DAL**: C (Enterprise
Standard) · **Topic**: 04 (Intelligence) · **Feature ID**: C-INTL-06 · **Origin**:
architecture-direction review (2026-07-21, Steve Bula + Claude) — the "middle way" applied to prompt
assembly

| | |
|---|---|
| Evolves (without reopening) | `C-INTL-05` ✅ Configurable Prompt Render Profiles (profiles = envelope engine of oneshot mode) · `B-INTL-09` Agent Memory Bank (memory pull path) · `D-INTL-05` ✅ (metadata stays envelope) |
| Serves | `C-FLOW-11` (work-unit context mounting) · `C-VAL-05` (rubrics are one content class) |
| Redirects | `TECH-006`'s "move loading inside the prompt factory" — see below |
| Not touched | `TECH-007` escaping — pure envelope, needed in both modes |

A **new** story because the affected capabilities are delivered and stay ✅/finished. Completed
stories are not reopened; their evolution is tracked here.

`TECH-006` redirect: the destination becomes domain loaders + mounted files, not deeper factory
centralization (its Findings 1–2 stay valid).

## What it does

Narrows the `PromptBuilder` to the envelope and externalizes the content:

1. Constitution, standards and guidance become **mounted files** (canonical on-disk artifacts) that
   `C-FLOW-11` work units read directly. `oneshot` mode keeps working: thin slots *reference the
   same files* (single source of truth, no behavioral change to shipped `C-INTL-05` profiles).
2. Agent-memory access for work units becomes **pull-based** (a memory tool/file view over the
   `B-INTL-09` repository) instead of slot injection. `oneshot` hydration stays as-is.
3. The envelope (structure, escaping, metadata, profiles) is declared the *only* long-term
   responsibility of `PromptBuilder`. New context sources land as files/rubrics, not adders.

## Why

The `PromptBuilder` slot/profile machinery (~4,800 lines across `infrastructure/llm`, incl.
`prompt/adders.py` 477 + `prompt/builder.py` 304) mixes two responsibilities:

| | Is | Territory |
|---|---|---|
| **Envelope** | deterministic guarantees: block structure, injection safety (`TECH-007`), metadata (`PromptSafeConfig`), rendering profiles, the 2-Tier Handover standard | harness — must stay code |
| **Content** | knowledge injected through slots: constitution, standards, agent memory (hydration in `_build_base_prompt`), plan/context blocks | knowledge — every new source grows the assembly machinery |

Content growth is the compounding problem `TECH-006` documented: the RunContext god object + the
cross-interface loader spider-web.

With `C-FLOW-11` (graduated autonomy), agentic work units do not consume assembled prompts: an
agent *reads* constitution/standards/rubrics as mounted files and *pulls* memory via a tool. Keeping
content in slots means maintaining two divergent context paths.

## Candidate approaches (not yet designed)

1. Canonical context directory (e.g. `.specweaver/context/` or existing file locations) + a tiny
   resolver both modes share — recommended.
2. Memory pull: read-only tool surface over `MemoryRepository` for work units (role/DAL-gated).
3. Migration order: constitution/standards first (already files — mostly de-duplicating loaders),
   memory second, then declare the adders API frozen.

## Non-goals (proposed, pending design)

- Removing profiles/slots (oneshot compat is permanent until the dial says otherwise).
- Any change to shipped `C-INTL-05` behavior or its ✅ status.
- Prompt *optimization* (`B-INTL-10` — separately re-scoped against this direction).

**Next**: run `specweaver-design C-INTL-06` after (or together with) `C-FLOW-11` intake — the
work-unit context-mounting contract is the forcing function.
