# E-INTL-02 — Spec Drafting & Review

### F2: Spec Drafting (`sw draft`)

Interactive session. Agent and HITL co-author a Component Spec.
- **Asks questions** based on the 5-section template (Purpose, Contract, Protocol, Policy, Boundaries)
- **Makes suggestions** — proposes content for each section
- HITL accepts, modifies, or rejects suggestions
- Agent flags completeness gaps
- Output: `<name>_spec.md` — DRAFT, not yet validated/reviewed
- LLM required (via adapter interface)

### F4: Spec Review (`sw review spec`)

LLM semantic evaluation of a spec that passed validation. Assesses meaning, not structure. Output: ACCEPTED or DENIED with findings. Same review module as F7, different prompts.
