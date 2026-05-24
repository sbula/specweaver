# Developer Guide: Pluggable Contexts

This guide explains how to use and extend the **Pluggable Context** system in SpecWeaver.

## Overview

To prevent compile-time coupling between domain modules (like `assurance/graph`) and the LLM infrastructure, SpecWeaver uses a duck-typed protocol `PromptContentSource`. 

Domain classes can conform to this protocol natively without importing any LLM/infrastructure modules. This ensures clean boundary isolation and compliance with strict architectural validation (`tach check`).

---

## The `PromptContentSource` Protocol

The core interface is defined in `specweaver.infrastructure.llm.prompt.interfaces.PromptContentSource`:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class PromptContentSource(Protocol):
    """Duck-typed structural protocol for pluggable context sources."""

    def get_prompt_content(self, char_limit: int | None = None) -> str:
        """Return the fully formatted string content (including XML tags and escaping).
        
        If char_limit is provided, the raw payload should be truncated before formatting and escaping.
        """
        ...

    def get_prompt_label(self) -> str:
        """Return the label/name of the context block."""
        ...
```

### Implementing Native Conformance in the Domain

Because Python protocols are structurally resolved, any class that implements `get_prompt_content` and `get_prompt_label` satisfies the protocol *without* any LLM package imports:

```python
# specweaver/assurance/graph/topology.py
# NO LLM IMPORTS HERE

class TopologyContext:
    def __init__(self, name: str, purpose: str):
        self.name = name
        self.purpose = purpose

    def get_prompt_content(self, char_limit: int | None = None) -> str:
        content = f"Topology: {self.name} - {self.purpose}"
        if char_limit is not None:
            content = content[:char_limit] + "\n[truncated]"
        return f"<topology>\n{content}\n</topology>"

    def get_prompt_label(self) -> str:
        return self.name
```

---

## Out-of-the-Box Adapters

For types that do not implement the protocol natively, SpecWeaver provides explicit adapters in `specweaver.infrastructure.llm.prompt.adapter`:

1. **`StringPromptAdapter(content, label, escaping)`**: Wraps a raw string, validates the label, and formats it as `<context label="...">`.
2. **`FilePromptAdapter(path, label, role, escaping, skeleton, skeleton_files)`**: Wraps file paths, validates sizes, optionally extracts AST skeletons, and formats as `<file path="..." language="...">`.
3. **`ProjectMetadataPromptAdapter(metadata)`**: Wraps `ProjectMetadata` models, serializing the safe config parameters as JSON inside `<project_metadata>` tags.

---

## Truncation Safety & CDATA Escaping

When designing custom context sources:
* **Pre-Escaping Truncation**: Truncate raw content inside `get_prompt_content()` *before* wrapping it in XML tags. Slicing raw text guarantees that tag boundaries (e.g. `</context>`, `</file>`, and CDATA blocks `]]>`) remain intact.
* **Escaping**: Always sanitize raw inputs against XML injection using `apply_escaping` and `escape_xml_attribute`.
