# User Handbook 4: Interactive HITL Gates & Dictator Overrides

Use when: a run is parked at a Human-In-The-Loop (HITL) gate, or you need to override an agent's
decision.

Changes made by generation agents pass a **HITL** gate before any Git operation runs.

## 1. The Dual-Agent Pipeline Wait (`GateType.HITL`)

When `sw implement` or `sw review` hits a problem the agent cannot fix from the linter output, the
run pauses and hands control to the CLI:

```bash
Execution Halted - GateType: HITL
Path: src/controller.py >> Reason: Lacking domain schema boundaries
```

The run is now **Parked**. You can leave the terminal running.

**Interactive vs. headless drafting (INT-US-02):** when a pipeline reaches a `draft_spec` step and the
spec does not exist yet:

| Where you run it | What happens |
|---|---|
| **Interactive terminal** | `sw run new_feature <name>` (and `sw resume`) co-author the spec with you; the interactive provider is attached automatically |
| **Headless** (CI, scripts, piped input) | The run **parks** and tells you how to continue |

A parked run exits with code `0`: parking is a normal outcome, not an error.

## 2. Using `<dictator-overrides>`

Use this when an agent keeps changing an architectural decision the wrong way during a feedback
loop. In your review feedback, wrap the commands in an XML block. The `PromptBuilder` gives it
priority over the standard instructions:

```xml
<dictator-overrides>
DO NOT IMPORT FROM `commons/*`. You must mock the payload locally instead.
IGNORE PyTest Warning C04 coverage for this explicit module.
</dictator-overrides>
```

The agent receives these overrides as non-negotiable commands at the top of its generation context.

## 3. Resuming the System

SpecWeaver saves run state in the database. After an interrupted run, continue where it stopped:

```bash
sw resume
# OR explicit resume bounds:
sw resume <run_id>
```

### Resuming a review gate **is** approving it

When a run is parked at a HITL gate on a step that **passed**, `sw resume` means *"I looked at
this and I approve it."* The step completes from its stored result and the pipeline advances. It
is **not** re-run, so no LLM tokens are spent re-doing reviewed work.

Everything else re-executes on resume, which is the safe direction:

| Why it parked | What `sw resume` does |
|---|---|
| A **HITL gate** on a step that **passed** | **Approves it** — advances without re-running the step |
| A HITL gate on a step that **failed** | Re-runs the step (you resumed a failure, so that's a retry) |
| The step itself asked for input (e.g. a spec doesn't exist yet) | Re-runs the step, now that you've done what it asked |
| A resource was locked by another run | Re-tries the reservation |

Rules:

- Each distinct park costs exactly one `sw resume`. A journey that parks twice (e.g. review a draft,
  then review a decomposition) takes two resumes. A reviewer rejection that loops back adds another
  park.
- Parked runs always exit with code `0`. Check the reported status, not the exit code, to tell
  "waiting for you" from "finished".
- The park message names the step and the artifact, so you can inspect what you approve.
- Nothing is auto-approved: a fresh `sw run` never consumes an approval, and one `sw resume`
  approves at most one gate.
