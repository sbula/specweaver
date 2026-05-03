# US-28: Agent-Native Issue & State Tracker

## Overview

As the SpecWeaver orchestration engine (`topic_03_flow_engine`) scales into autonomous multi-agent execution, traditional markdown-based task lists (`task.md`) suffer from rapid context degradation, formatting errors, and token hallucination during agent handovers.

This epic introduces a structured, SQLite-backed **Agent Memory Bank & Issue Tracker** to preserve execution state deterministically. 

## Architectural Goals

1. **Context Hydration**: The active task status, acceptance criteria, and blocker notes are injected directly into the LLM system prompt via the flow engine, preventing the agent from "forgetting" its objective.
2. **Deterministic Handovers**: When an agent's context window fills, it must execute a `handover` Tool. The state is saved in SQLite, ensuring the next agent picks up exactly where the last one left off.
3. **Multi-Agent Locking**: SQLite row-level locks prevent two agents from modifying the same feature or file concurrently.
4. **Structured Rollbacks**: If a session crashes (Dirty Exit), the Flow Engine orchestrator detects the dead session and safely reverts the active task to an `OPEN` state with a warning flag for the next agent.

## Related Documents

*   **Brainstorming & Strategy**: [Agent Workflow Tracker Brainstorm](../../../../analysis/agent_workflow_tracker_brainstorm.md)

## Implementation Status

*   **Status**: `Pending`
*   **Active Features**: None yet.
