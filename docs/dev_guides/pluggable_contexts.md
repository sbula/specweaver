# Pluggable Contexts

Use when: a domain object must appear in an LLM prompt, or you add a new kind of prompt context.

SpecWeaver's duck-typed protocol `PromptContentSource` lets domain modules (like `assurance/graph`)
supply prompt content without importing any LLM/infrastructure module. No compile-time coupling, and
the boundaries pass `tach check`.

## The protocol

Defined in `specweaver.infrastructure.llm.prompt.interfaces.PromptContentSource`:

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

## Conforming from the domain

Protocols resolve structurally: any class with `get_prompt_content` and `get_prompt_label`
conforms, with no LLM package imports.

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

## Built-in adapters

For types that do not conform themselves, `specweaver.infrastructure.llm.prompt.adapter` provides:

| Adapter | Wraps | Output |
|---|---|---|
| **`StringPromptAdapter(content, label, escaping)`** | a raw string; validates the label | `<context label="...">` |
| **`FilePromptAdapter(path, label, role, escaping, skeleton, skeleton_files)`** | file paths; validates sizes, optionally extracts AST skeletons | `<file path="..." language="...">` |
| **`ProjectMetadataPromptAdapter(metadata)`** | `ProjectMetadata` models; the safe config parameters as JSON | `<project_metadata>` tags |

## Rules for custom sources

- **Truncate before escaping.** Cut the raw content inside `get_prompt_content()` *before* wrapping
  it in XML tags, so tag boundaries (e.g. `</context>`, `</file>`, and CDATA blocks `]]>`) stay
  intact.
- **Escape.** Sanitize raw inputs against XML injection with `apply_escaping` and
  `escape_xml_attribute`.
