# Design: Graduated Autonomy — DAL-Driven Execution-Mode Dial

- **Feature ID**: C-FLOW-11
- **Epic**: Topic 03 (Flow Orchestration)
- **Status**: ✅ Delivered — this document is a **record**, not a plan.
- **DAL**: C (Enterprise Standard) — the dial is itself assurance policy.

## What shipped

A pipeline step declares `mode: oneshot | agentic`. The install declares a policy in
`[autonomy]`. The run's own DAL decides whether the request is allowed. `agentic` runs a bounded
work unit — an agent iterating with tools — behind a replaceable runtime.

Execution rigidity used to be an architectural constant: one LLM call per generation step, a
hand-rolled reflection loop for fixes. That is too much ceremony for a throwaway script and too
little capability for work an agent could iterate on. The zero-trust machinery already guarantees
the result at the step boundary — session isolation, the authorized merge, the gate battery — so
**the gates make the middle free**. Nothing here softens a gate.

## The strategic decision, and how it was taken

The stub left the agent-runtime binding open and asked for it to be settled at intake. It was, in
favour of an **in-process loop behind an `AgentRuntime` protocol**, on one decisive fact:
`_CREDENTIAL_VARS` in the sandbox executor strips every provider API key from sandboxed child
processes, deliberately, so that generated code cannot exfiltrate one. An external agent CLI
running inside the work unit's own worktree would therefore have no credentials, and giving it any
means putting a hole in that control.

The protocol keeps the question open rather than closing it: a subprocess runtime is a class, not
a rewrite.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Rigidity is declarable, and today's behaviour is the default | System | Adds a tri-state `mode` to `PipelineStep` and an install policy that ships `oneshot` | A pipeline written before the dial runs byte-identically; a step that wants to iterate says so in one word |
| FR-2 | Criticality overrules the pipeline author | System | Resolves the mode at the composition root against the run's DAL and the configured `agentic_max_dal` ceiling | A DAL-A target stays deterministic however the YAML is written, and a run whose DAL never resolved fails closed to `oneshot` |
| FR-3 | An agentic step actually iterates | System | Drives the LLM in a tool loop, executing each requested tool and feeding the result back until no more are asked for | The agent can read, act and correct within one step, instead of one prompt and one answer |
| FR-4 | The loop cannot run away | System | Bounds every work unit by turns *and* by the run's spend ceiling, refusing a `max_turns` below 1 | Neither cheap infinite tool calls nor ten ruinous LLM calls can continue past a bound; a tripped spend breaker ends the run rather than counting as a failed turn |
| FR-5 | The runtime is replaceable | System | Defines `AgentRuntime` as a protocol and depends only on it | The open question of which agent runtime SpecWeaver stands on is not answered by accident, and a second one costs a class |

Proof is by citation in the test files, read by `check_fr_coverage.py`. Each FR is behind a killed
mutant: removing the DAL override, letting an unresolved DAL go agentic, unbounding the turn loop,
never executing a tool, never seeding the policy onto the context, shipping the policy as
`agentic`, and raising the ceiling to DAL-A all fail the tests that claim them.

## Why the policy is seeded where it is

`apply_isolation_policy` already serves both composition roots — `sw run`/`sw resume` and the
API's run endpoints — and seeding at only one of them is the exact defect `TECH-013` closed for
isolation. The autonomy policy rides along.

It is read with `getattr`, not attribute access, and that is load-bearing: the whole block is
best-effort, so a settings object without the attribute would otherwise take the **isolation**
policy down with it. That regression was introduced and caught by the API's own policy tests
before it left the branch.

## Non-Functional Requirements

| # | NFR | Requirement |
|---|-----|-------------|
| NFR-1 | Zero regression | `oneshot` is the shipped policy and the resolved mode for every existing pipeline; the one-shot handlers are untouched |
| NFR-2 | Fail closed | An unresolved DAL, an unknown mode string and a `max_turns` below 1 are each refused rather than guessed |
| NFR-3 | Two bounds | Turns and spend are independent; neither substitutes for the other |

## Non-Goals

- Removing or rewriting the one-shot handlers. They are the deterministic position of the dial.
- Multi-agent orchestration — that is `B-INTL-06`.
- Softening any guarantee. Sandbox, authorization, mechanical rules and gates are identical at
  every dial position.
- Choosing SpecWeaver's long-term agent runtime. `AgentRuntime` exists so that stays open.
