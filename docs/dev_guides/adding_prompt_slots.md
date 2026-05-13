# Developer Guide: Adding New Prompt Slots

This guide explains how to add new context elements (slots) to the `PromptBuilder` using the `RenderProfile` system.

## Overview

In SpecWeaver, the rendering sequence of context blocks (instructions, topology, memory, etc.) sent to the LLM is controlled by **Prompt Render Profiles**. This strictly isolates infrastructure mechanisms (XML rendering) from workflow policy (which context goes to which agent).

## Step 1: Define the `PromptSlot`

First, register your new slot in `specweaver/infrastructure/llm/_prompt_profiles.py`.

The `PromptSlot` enum maps logical context boundaries to physical XML tags.

```python
from enum import Enum

class PromptSlot(str, Enum):
    # Existing slots...
    INSTRUCTIONS = "instructions"
    TOPOLOGY = "topology"
    
    # Add your new slot:
    CONSOLIDATED_MEMORY = "consolidated_memory"
```

## Step 2: Register the Slot in `RenderProfiles`

Open `specweaver/core/flow/handlers/_profiles.py`. This is where orchestration policy lives.

Decide which profiles should include your new slot. For example, if it should only go to the `FULL` and `INTERACTIVE` profiles, add it to their `order` tuples:

```python
from specweaver.infrastructure.llm._prompt_profiles import RenderProfile, PromptSlot

FULL = RenderProfile(
    name="FULL",
    active_slots=frozenset([
        # ... other slots
        PromptSlot.CONSOLIDATED_MEMORY,
    ]),
    order=(
        PromptSlot.INSTRUCTIONS,
        # ... other slots in desired order
        PromptSlot.CONSOLIDATED_MEMORY, # Insert where you want it rendered
        PromptSlot.PLAN
    )
)
```

## Step 3: Implement the Rendering Logic (If Custom)

If your slot represents simple tagged text or standard XML attributes, **you do not need to write any rendering code**. The `render_blocks` function in `_prompt_render.py` will automatically render it using `_render_tagged_blocks`.

### When to write a Custom Renderer:
If your slot requires complex formatting (e.g., iterating over specific object structures, building a tree, grouping files), you must add a custom dispatch handler in `_prompt_render.py`:

```python
# specweaver/infrastructure/llm/_prompt_render.py

def _render_consolidated_memory(blocks: Sequence[_ContentBlock]) -> str:
    # Custom rendering logic here
    result = ["<consolidated_memory>"]
    for b in blocks:
        result.append(f"  <item epoch='{b.metadata.get('epoch')}'>{b.content}</item>")
    result.append("</consolidated_memory>")
    return "\n".join(result)

# In render_blocks():
dispatch: dict[PromptSlot, Callable[[Sequence[_ContentBlock]], str]] = {
    PromptSlot.FILE: render_files,
    PromptSlot.MENTIONED: _render_mentioned,
    PromptSlot.CONSOLIDATED_MEMORY: _render_consolidated_memory, # Map your slot
}
```

## Step 4: Inject the Context

Now you can inject content into this slot from anywhere that has a `PromptBuilder` instance.

```python
builder.add_context(
    content="Epoch 5 consolidation...",
    label="memory_compaction",
    slot=PromptSlot.CONSOLIDATED_MEMORY,
    priority=2
)
```

If the active `RenderProfile` does not contain `PromptSlot.CONSOLIDATED_MEMORY` in its `active_slots`, the `add_context` call will safely ignore it, saving token budgets and eliminating unnecessary downstream I/O.
