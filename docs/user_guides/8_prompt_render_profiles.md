# Prompt Render Profiles

Use when: you want a workflow step to send the LLM more or less context than its default.

SpecWeaver's **Prompt Rendering Engine** decides what context goes to the LLM at each step. A **Render
Profile** names which context blocks (`PromptSlot`s: instructions, topology, files, test output ...)
are included, and in what order. The aim: stay within token budgets and context limits, and send
only what the task needs.

## How it works

- A workflow step can request a profile in its YAML config. There is no fixed prompt template per
  agent.
- The `PromptBuilder` maps the profile to its set of `PromptSlot`s, filled from the Context
  Hydration system.
- Split of concerns: infrastructure owns formatting and syntax (e.g. XML tags); the profile owns
  what is included.

## Available profiles

| Profile | Slots | Used by |
|---|---|---|
| **`FULL`** | All slots. The default. | Code generation and review |
| **`MINIMAL`** | Instructions, metadata, topology | Feature decomposition, planning |
| **`INTERACTIVE`** | All slots except constitution and standards | Human-in-the-Loop (HITL) work such as interactive spec drafting |
| **`ARBITER`** | Instructions, context | The Arbiter only, to judge test results |

Slot sets are defined in `src/specweaver/core/flow/handlers/_profiles.py`.

## Override a profile in a workflow

Set `render_profile` in the step's `params`:

```yaml
steps:
  - action: "generate"
    target: "code"
    params:
      max_retries: 3
      # Override the default FULL profile with MINIMAL
      render_profile: "minimal"
```

## Rules

1. **Case-insensitive.** Surrounding (leading/trailing) whitespace is ignored: `minimal`, `MINIMAL` and
   `  Minimal ` all resolve.
2. **Fail fast.** An unknown name (e.g. `render_profile: "super_fast"`) aborts the step with an
   explicit error. There is no silent fallback to a default, so no tokens are spent on a wrong
   prompt.
3. **Omitted = default.** Without `render_profile`, the handler uses its own default profile.

## Further reading

To add new `PromptSlot`s or register new profiles:
[Adding New Prompt Slots](../dev_guides/adding_prompt_slots.md).
