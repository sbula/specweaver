# US-28 — Agent-Native Issue & State Tracker

**Status**: `Pending` · **Active Features**: None yet. · **Topic**: `topic_03_flow_engine`

## What it does

A structured, SQLite-backed **Agent Memory Bank & Issue Tracker** that keeps execution state
deterministic across agent handovers.

## Why

As the orchestration engine scales into autonomous multi-agent execution, markdown task lists
(`task.md`) suffer rapid context degradation, formatting errors and token hallucination during
agent handovers.

## Goals

1. **Context hydration** — the flow engine injects the active task status, acceptance criteria and
   blocker notes into the LLM system prompt, so the agent does not "forget" its objective.
2. **Deterministic handovers** — when an agent's context window fills, it must execute a `handover`
   Tool. State is saved in SQLite; the next agent picks up exactly where the last left off.
3. **Multi-agent locking** — SQLite row-level locks stop two agents modifying the same feature or
   file concurrently.
4. **Structured rollbacks** — if a session crashes (Dirty Exit), the Flow Engine orchestrator
   detects the dead session and reverts the active task to `OPEN` with a warning flag for the next
   agent.

## Related

- Brainstorming & strategy:
  [Agent Workflow Tracker Brainstorm](../../../../analysis/agent_workflow_tracker_brainstorm.md)
