# Prompt Render Profiles

SpecWeaver utilizes a dynamic **Prompt Rendering Engine** to determine precisely what context is sent to the Large Language Model (LLM) at any given step in a workflow. This mechanism ensures that token budgets are respected, context limits are not breached, and agent performance is optimized by only providing the information strictly necessary for the task at hand.

At the core of this system are **Render Profiles**, which dictate which logical blocks of context (like instructions, project topologies, code files, and test output) are included in the prompt, and in what order.

## How It Works

Instead of hardcoding a monolithic prompt template for every agent, SpecWeaver allows workflows to dynamically request specific rendering profiles via the step configuration in your workflow YAML file. 

The `PromptBuilder` dynamically maps the requested profile to a predefined set of `PromptSlot`s, pulling from the unified Context Hydration system. This strict separation of concerns means infrastructure handles the mechanism of formatting and syntax (e.g., XML tags), while the profile dictates the policy of what context is included.

## Available Profiles

The system provides several core profiles built-in:

*   **`FULL`**: The default heavy-weight profile. It includes comprehensive context: instructions, plan, topology, files, api contracts, MCP context, and tracing. Used for most complex code generation and deep review tasks where the agent needs a holistic view of the project.
*   **`MINIMAL`**: A lightweight profile designed for tasks that require focus and speed, such as feature decomposition or simple planning. It includes only instructions, topology, and files.
*   **`INTERACTIVE`**: A conversational profile tailored for Human-in-the-Loop (HITL) workflows, such as interactive spec drafting. It strips away plans, topology, and execution traces, focusing instead on chat history, instructions, and file context.
*   **`ARBITER`**: A specialized profile exclusively used by the Arbiter component to evaluate test results. It includes instructions, plan, topology, test files, and crucial failure traces.

## Using Profiles in Custom Workflows

You can explicitly override the default rendering profile for any handler by specifying the `render_profile` parameter in your workflow YAML. 

```yaml
steps:
  - action: "generate"
    target: "code"
    params:
      max_retries: 3
      # Override the default FULL profile with MINIMAL
      render_profile: "minimal"
```

### Profile Resolution Rules

1.  **Case Insensitivity**: Profile names are case-insensitive and tolerate leading/trailing whitespace (`minimal`, `MINIMAL`, and `  Minimal ` all resolve correctly).
2.  **Fail-Fast Validation**: SpecWeaver employs a fail-fast validation mechanism. If you request an invalid or unregistered profile name (e.g., `render_profile: "super_fast"`), the step will immediately abort with an explicit error, preventing silent fallback to a default profile and saving token costs.
3.  **Backward Compatibility**: If the `render_profile` parameter is omitted, the handler will automatically use its sensible default profile.

## Further Reading

For developers looking to extend the system by adding new `PromptSlot`s or registering entirely new orchestrator profiles, consult the developer guide: [Adding New Prompt Slots](../dev_guides/adding_prompt_slots.md).
