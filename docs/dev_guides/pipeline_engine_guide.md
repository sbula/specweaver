# Developer Guide: Creating New Flow Pipelines

The SpecWeaver engine defines system behaviors strictly through orchestrations called "Pipelines." A pipeline seamlessly manages State, Step executions, and Gates (human or automated). 

This guide demonstrates how to build and route new workflows through the Flow Engine.

---

## 1. Declarative Architecture (`pipelines/*.yaml`)

Pipelines are data, not code. You define the logical execution sequence structurally inside the `pipelines/` directory.

### Example Pipeline YAML:
```yaml
name: "security_audit_flow"
steps:
  - name: generate_audit_plan
    action: plan
    target: code
    gate:
      type: auto
      condition: completed

  - name: review_security_issues
    action: review
    target: code
    gate:
      type: hitl
      on_fail: loop_back
      loop_target: generate_audit_plan
      max_retries: 3
```

- **action/target tuple**: Drives the routing framework dynamically.
- **gate**: Halts the `PipelineRunner`. `auto` requires static validation to pass. `hitl` yields execution and demands human database confirmation. 

---

## 2. Designing Handlers (`flow/handlers.py`)

When the runner evaluates the `action: review` over `target: code`, it references the `StepHandlerRegistry`. 

To implement the logical behaviors behind a step, you construct a specific **Handler**. 
- **Location**: `src/specweaver/flow/_<domain>.py`

### Constructing the Handler:
```python
from specweaver.flow.models import StepResult

class ReviewCodeHandler:
    def execute(self, context: RunContext) -> StepResult:
        # Load the configuration bounds
        # Spin up LLM / Exec Tools 
        # Evaluate Logic
        return StepResult(status="pass", artifacts={"feedback": result.feedback})
```

Once the handler returns natively, the internal DB wrapper `StateStore` checkpoints the execution. This ensures interrupted or aborted loops can autonomously `resume(run_id)`.

---

## 3. Dynamic Single-Step Pipelines

Typically, YAML represents massive system loops (Draft → Plan → Code → Test). What happens if a User hits the CLI with a generic command like `sw standards scan`?

Instead of bypassing Flow and manually wiring a CLI module to an LLM, SpecWeaver enforces 100% routing consistency leveraging **Single-Step Pipelines**.

```python
# Reusable helper from flow/runner.py
from specweaver.flow.runner import create_single_step

# Dynamic runtime generation
pipe = create_single_step(action="scan", target="standards")
runner.execute(pipe)
```
This forces all commands—no matter how small—to persist their context, inherit active telemetry, and utilize the robust handler engine symmetrically.

---

## 4. Dynamic Risk-Based Rulesets (DAL Integration)

When validation boundaries restrict capabilities based on runtime architecture (e.g. Flight Critical Data vs Backend Internal), the Pipeline leverages the **Fractal Resolution Engine (SF-2)**.

Instead of overriding global settings, Handlers like `ValidateSpecHandler` and `ValidateCodeHandler` transparently extract the architectural boundary by locating the target module's `context.yaml`. 
They read the `.operational.dal_level` context and deep-merge the global standard threshold parameters against the specific architectural assurance matrix bounds safely at runtime.

```python
# Extract the target architecture baseline
dal = dal_resolver.resolve(target.path) or context.db.get_default_dal()

# Map bounding thresholds locally and merge
if dal_settings := context.settings.dal_matrix.matrix.get(dal):
    from pydantic.utils import deep_update # equivalent
    resolved = deep_merge_dict(base_config, dal_settings.dict(exclude_unset=True))
    
apply_settings_to_pipeline(pipeline, ValidationSettings(**resolved))
```
