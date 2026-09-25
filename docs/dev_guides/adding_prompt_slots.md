# Adding Prompt Slots

Use when: you add a context element (slot) to what SpecWeaver's `PromptBuilder` sends the LLM.

**Prompt Render Profiles** (`RenderProfile`) decide which context blocks (instructions, topology,
memory, etc.) reach which agent and in what order. XML rendering stays infrastructure; the choice of
context per agent is workflow policy.

Since moved (2026-09-25): `PromptSlot` and `RenderProfile` live in
`infrastructure/llm/prompt/profiles.py`, rendering in `infrastructure/llm/prompt/render.py`.
`_prompt_profiles.py` and `_prompt_render.py` are backward-compatibility facades.

## Steps

1. **Define the `PromptSlot`** in `specweaver/infrastructure/llm/_prompt_profiles.py`. The enum maps
   logical context boundaries to XML tags.

```python
from enum import Enum

class PromptSlot(str, Enum):
    # Existing slots...
    INSTRUCTIONS = "instructions"
    TOPOLOGY = "topology"
    
    # Add your new slot:
    CONSOLIDATED_MEMORY = "consolidated_memory"
```

2. **Register it in `RenderProfiles`** in `specweaver/core/flow/handlers/_profiles.py`, where orchestration policy
   lives. Add the slot to `active_slots` and to the `order` tuple of each profile that should get it
   (e.g. only `FULL` and `INTERACTIVE`):

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

3. **Rendering, only if custom.** Simple tagged text or standard XML attributes need no code:
   `render_blocks` in `_prompt_render.py` falls back to `_render_tagged_blocks`. Complex formatting
   (iterating object structures, building a tree, grouping files) needs a dispatch handler:

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

   Today the dispatch table is `_SLOT_RENDERERS` in `prompt/render.py`, keyed by tag string.

4. **Inject content** from anywhere with a `PromptBuilder`:

```python
builder.add_context(
    content="Epoch 5 consolidation...",
    label="memory_compaction",
    slot=PromptSlot.CONSOLIDATED_MEMORY,
    priority=2
)
```

   If the active `RenderProfile` lacks `PromptSlot.CONSOLIDATED_MEMORY` in its `active_slots`,
   `add_context` ignores the call: no tokens spent, no downstream I/O.

## New profiles

A profile selectable from YAML must be in `PROFILE_REGISTRY`.

1. Create the `RenderProfile` in `specweaver/core/flow/handlers/_profiles.py`.
2. Add it to the `PROFILE_REGISTRY` tuple at the bottom of the file.

```python
# specweaver/core/flow/handlers/_profiles.py
from types import MappingProxyType

MY_NEW_PROFILE = RenderProfile(
    name="MY_NEW_PROFILE",
    active_slots=frozenset([PromptSlot.INSTRUCTIONS, PromptSlot.PLAN]),
    order=(PromptSlot.INSTRUCTIONS, PromptSlot.PLAN)
)

PROFILE_REGISTRY = MappingProxyType(
    {p.name.lower(): p for p in (
        FULL,
        MINIMAL,
        # ...
        MY_NEW_PROFILE, # Add it here!
    )}
)
```

Select it in a YAML step:
```yaml
- action: "generate"
  target: "code"
  params:
    render_profile: "my_new_profile"
```
