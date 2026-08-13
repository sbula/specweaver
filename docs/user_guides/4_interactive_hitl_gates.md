# User Handbook 4: Interactive HITL Gates & Dictator Overrides

SpecWeaver assumes LLMs are intelligent but unpredictable. Every sequence of changes executed by
generation agents must route formally through a **Human-In-The-Loop (HITL)** interception gate prior
to executing Git operations.

## 1. The Dual-Agent Pipeline Wait (`GateType.HITL`)
When `sw implement` or `sw review` hits an evaluation dead-end (the Agent encounters a bug it cannot systematically fix via the linter outputs), it immediately pauses execution and yields to the CLI.
```bash
Execution Halted - GateType: HITL
Path: src/controller.py >> Reason: Lacking domain schema boundaries
```
You can leave the terminal running safely. The workflow is formally **Parked**.

**Interactive vs. headless drafting (INT-US-02):** when a pipeline reaches a `draft_spec` step and the
spec doesn't exist yet, the behavior depends on where you run it. In an **interactive terminal**,
`sw run new_feature <name>` (and `sw resume`) now co-author the spec with you directly — the interactive
provider is attached automatically. **Headless** (CI, scripts, piped input), the run **parks** exactly as
before and tells you how to continue; a parked run exits with code `0` (parking is a normal outcome, not
an error).

## 2. Using `<dictator-overrides>` 
If a SpecWeaver Agent insists on altering an architectural decision incorrectly during a feedback loop, you have the authority to bypass its logical deduction context entirely.

Within your review interface, wrap explicit commands inside an XML boundary. This physically weighs higher mathematically inside the `PromptBuilder` engine above standard execution logic:
```xml
<dictator-overrides>
DO NOT IMPORT FROM `commons/*`. You must mock the payload locally instead.
IGNORE PyTest Warning C04 coverage for this explicit module.
</dictator-overrides>
```
The agent receives these overrides as un-arguable commands injected precisely at the top of its generation execution contexts.

## 3. Resuming the System
If you exited your execution loop forcefully, SpecWeaver saves your process states to database rows. You can boot it back up logically where it failed:
```bash
sw resume
# OR explicit resume bounds:
sw resume <run_id>
```

### Resuming a review gate **is** approving it

When a run is parked at a HITL gate on a step that **passed**, `sw resume` means *"I looked at
this and I approve it."* The step is completed from its stored result and the pipeline advances —
it is **not** re-run, so no LLM tokens are spent re-doing work you already reviewed.

Everything else re-executes on resume, which is the safe direction:

| Why it parked | What `sw resume` does |
|---|---|
| A **HITL gate** on a step that **passed** | **Approves it** — advances without re-running the step |
| A HITL gate on a step that **failed** | Re-runs the step (you resumed a failure, so that's a retry) |
| The step itself asked for input (e.g. a spec doesn't exist yet) | Re-runs the step, now that you've done what it asked |
| A resource was locked by another run | Re-tries the reservation |

**Practical consequence:** each distinct park costs you exactly one `sw resume`. A journey that
parks twice — say, once to review a draft and once to review a decomposition — takes two resumes.
If a reviewer rejects and the pipeline loops back, that adds another park to acknowledge. Parked
runs always exit with code `0`; check the reported status, not the exit code, to tell "waiting for
you" apart from "finished".

> To inspect what you are approving before you approve it, the park message names the step and the
> artifact involved. Nothing is auto-approved: a fresh `sw run` never consumes an approval, and one
> `sw resume` approves at most one gate.
