# User Handbook 4: Interactive HITL Gates & Dictator Overrides

SpecWeaver assumes LLMs are intelligent but unpredictable. Every sequence of changes executed by generation agents must route formally through a **Human-In-The-Loop (HITL)** interception gate prior to executing Git operations.

## 1. The Dual-Agent Pipeline Wait (`GateType.HITL`)
When `sw implement` or `sw review` hits an evaluation dead-end (the Agent encounters a bug it cannot systematically fix via the linter outputs), it immediately pauses execution and yields to the CLI.
```bash
Execution Halted - GateType: HITL
Path: src/controller.py >> Reason: Lacking domain schema boundaries
```
You can leave the terminal running safely. The workflow is formally **Parked**.

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
