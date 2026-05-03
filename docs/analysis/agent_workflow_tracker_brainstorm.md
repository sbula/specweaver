# Brainstorm: Agent Workflow Tracker & Memory Bank

This document outlines the architectural brainstorm for building a local, SQLite-backed issue tracker specifically designed to manage AI Agent workflows, prevent context loss, and handle complex multi-agent execution safely.

## 1. Entities (What We Track)

To keep context windows small and execution focused, we must break work down hierarchically.

*   **Epic / Feature**: High-level business or technical goal (e.g., `TECH-01`). Managed by the Human or a Manager Agent.
*   **Sub-Feature (SF)**: A logical grouping of work (e.g., `TECH-01 SF-3`).
*   **Task**: The atomic unit of work designed for a *single agent session*.
*   **Defect / Bug**: An unexpected blocker found during execution. Can be linked to a Task or Epic.
*   **Handover Note**: A required payload generated when an agent finishes a session or switches contexts, preserving state for the next agent.

## 2. State Machine (The Lifecycle)

A strict state machine prevents agents from skipping steps or leaving things half-done.

*   `OPEN`: Ready for an agent to claim.
*   `IN_PROGRESS`: Locked to a specific Agent `session_id`. No other agent can touch it.
*   `BLOCKED`: Execution halted. Requires human intervention or resolution of a dependency.
*   `REVIEW`: Worker agent thinks it's done; requires Manager Agent or Human to run the `/pre-commit` gate.
*   `RESOLVED`: Verified and closed.

## 3. Views and Roles (Who Sees What)

Different agents need different context scopes to prevent token hallucination.

*   **Worker Agent View**: Highly restricted. "I only see my active Task, its acceptance criteria, and the Handover Note from the last agent. I do not see the entire roadmap."
*   **Manager Agent View**: Broad scope. "I see the Epic, the dependency graph of Tasks, and the statuses. My job is to break Epics into Tasks and unblock Worker Agents."
*   **SpecWeaver Clean-Up / Housekeeping**: Automated background tasks that identify orphaned `IN_PROGRESS` tasks from crashed sessions and revert them.

## 4. Dependencies & Relationships

The database must enforce strict relational constraints:
*   `Blocks`: Task A blocks Task B. The system *physically prevents* an agent from claiming Task B until Task A is `RESOLVED`.
*   `Relates_To`: Informational linking.
*   `Found_During`: If a bug is found while executing Task A, it is linked. The agent can decide to fix it immediately (if small) or spin it off into a new Bug entity (if large) and mark Task A as `BLOCKED`.

## 5. Strategies for Complex Scenarios

### A. Agent Tries to Skip Steps
*   **Strategy**: The `mark_resolved` Tool requires a checklist of verifications (e.g., "Did you run the test suite?"). The SQLite Atom intercepts the tool call and rejects it if the required `Artifacts` (like test gap analysis) do not exist in the session context.

### B. Finding an Issue and "Going Back"
*   **Strategy**: If an agent working on Task C discovers that Task A (which is `RESOLVED`) was done incorrectly, the agent uses the `reopen_task` Tool. This immediately cascades: Task C is put on `HOLD`, Task A goes back to `OPEN` with a mandatory "Reopen Reason" injected into its context.

### C. Session Handover (Graceful vs. Dirty)
*   **Graceful Exit (Context Window Full)**: Before shutting down, the agent MUST call `create_handover(notes="...")`. The next agent boots up, reads the note, and continues seamlessly.
*   **Dirty Exit (Crash/API Failure)**: The Task is stuck in `IN_PROGRESS`. The Orchestrator detects the dead session, reverts the Task to `OPEN`, and prepends a warning to the next agent: *"WARNING: Previous session crashed unexpectedly. Audit current file state before proceeding."*

### D. Parallel Execution (Multi-Agent)
*   **Strategy**: Row-level locking in SQLite. When Agent 1 calls `claim_task(task_id=10)`, the DB records Agent 1's `session_id`. If Agent 2 tries to claim or modify Task 10, the Tool returns a hard error: `Task locked by active session.` This prevents two agents from writing to the same file simultaneously.

## Open Questions for You:
1. Do you agree with the separation of **Manager Agent** vs. **Worker Agent** views, or should all agents share the same context?
2. For "Dirty Exits" (crashes), should the system automatically try to revert the codebase to the last git commit before the crash, or leave the half-finished code for the next agent to clean up?
