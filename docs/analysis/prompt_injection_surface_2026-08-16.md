# What Actually Reaches a Prompt — E-VAL-03 Intake Research

*2026-08-16. Phase 1 of `specweaver-design` for `E-VAL-03`, stopped at its HITL gate. Recorded here
rather than in a design document because no design decision has been taken — three scope questions
are unanswered, and `E-VAL-03` has no feature directory by intent.*

## The structural half already exists

`infrastructure/llm/escaping.py` gives every prompt block XML/CDATA escaping, applied by
`PromptBuilder`, with an `escaping=` argument on each `add_*` method. **Tag breakout is handled.**

What escaping cannot touch is the semantic payload: `Ignore previous instructions` reads identically
inside a CDATA block. That is `E-VAL-03`'s real target, and the distinction belongs in its design.

## Every untrusted block reaching a prompt today

| call site | content | has an AST? |
|---|---|---|
| `core/flow/handlers/arbiter.py:227` — `add_context(filtered_trace, "Failures")` | **LLM-authored** failure traces (`INT-US-24`) | ✗ |
| `core/flow/handlers/draft.py:166,357` — `reviewer_findings` | **LLM-authored** review findings | ✗ |
| `workflows/implementation/generator.py:110` — `validation_errors` | validation output | ✗ |
| `workflows/review/reviewer.py:145` — `add_mentioned_files` | user / third-party files | ✓ |
| `add_constitution` / `add_standards` / `add_plan` / `add_topology` | project files | mixed |

**The capability's name is narrower than its threat.** Most untrusted text in prompts today is not
source code and has no AST — and it is precisely the LLM→LLM feedback loop the routing queue cites
as the reason urgency increased. An AST-only scanner would not touch it.

## The three questions Phase 1 could not answer from the repo

1. **Input scope** — AST-only as the name says, or every untrusted block at the `PromptBuilder`
   chokepoint? Decides the mechanism (AST node inspection vs text scanning), the module
   (`workspace/ast` vs `infrastructure/llm/prompt`), and whether the feedback loop is covered.
2. **Response on detection** — block the run, redact the span, or annotate and continue? This
   detector will have false positives, and a false positive that halts a pipeline is a different
   product from one that adds a warning.
3. **DAL behaviour** — always-on at every DAL, as `E-VAL-05` argues for itself, or escalating with
   DAL like the isolation capabilities?

## Also established

- `check_story_preconditions.py E-VAL-03` passes; its two warnings are only the absent design.
- `assurance/validation/` is the **spec** battery. Placing `E-VAL-03` in the VAL column is a registry
  taxonomy choice and does not by itself mean the check belongs in that battery.
