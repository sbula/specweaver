# Implementation Plan: PromptBuilder Input Escaping & Pluggable Context Architecture [SF-2: Pluggable Context Architecture (Structural Protocol)]
- **Feature ID**: TECH-06
- **Sub-Feature**: SF-2 — Pluggable Context Architecture (Structural Protocol)
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-06/TECH-06_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-06/TECH-06_sf2_implementation_plan.md
- **Status**: DRAFT

---

## 1. Goal & Overview
Implement the pluggable context loading architecture using a duck-typed structural protocol `PromptContentSource`. This decouples domain models and context objects from the LLM infrastructure. 

Following user feedback & Red/Blue team analysis:
* **Adapters are the Single Place of Formatting**: Adapters are responsible for transforming specific input types into the exact output format (including XML tag wrapping, escaping, and validation) used 1:1 by the prompt builder.
* **Truncation Safety**: To prevent slicing pre-rendered XML tags/boundaries during prompt truncation, the `PromptContentSource` protocol and adapters accept an optional `char_limit` parameter. Truncation happens on the raw payload *before* formatting/escaping, guaranteeing well-formed XML closures (e.g. `]]>`, `</file>`).
* **Option B (Explicit Builder API)**: Introduce explicit strongly-typed methods on `PromptBuilder` to map directly to each adapter, removing generic runtime type checking.
* **Security & Injection Mitigation**: Enforce XML attribute escaping, label character validation (regex), and CDATA block wrapping inside the adapters to prevent attribute injection and semantic spoofing.
* **Native Conformance**: Dataclasses like `TopologyContext` natively implement the protocol to avoid unnecessary wrapping.

---

## 2. Proposed Changes

### [Component: LLM Infrastructure]

#### [NEW] [interfaces.py](file:///c:/development/pitbula/specweaver/src/specweaver/infrastructure/llm/prompt/interfaces.py)
Define the `PromptContentSource` protocol with truncation support:
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

#### [NEW] [adapter.py](file:///c:/development/pitbula/specweaver/src/specweaver/infrastructure/llm/prompt/adapter.py)
Consolidate all prompt adapters:
```python
import re
from pathlib import Path
from specweaver.infrastructure.llm.escaping import apply_escaping, escape_xml_attribute
from specweaver.infrastructure.llm.prompt.constants import detect_language
from specweaver.infrastructure.llm.models import ProjectMetadata

# Only allow alphanumeric, dashes, underscores, dots, and slashes in labels to prevent injection/spoofing
LABEL_REGEX = re.compile(r"^[a-zA-Z0-9_\-\./]+$")

def validate_label(label: str) -> None:
    stripped = label.strip()
    if not stripped:
        raise ValueError("Label cannot be empty or whitespace-only.")
    if not LABEL_REGEX.match(stripped):
        raise ValueError(
            f"Invalid label format: '{label}'. "
            "Must contain only alphanumeric characters, dashes, underscores, dots, or slashes."
        )

class StringPromptAdapter:
    def __init__(self, content: str, label: str, escaping: str = "cdata"):
        validate_label(label)
        self._content = content
        self._label = label.strip()
        self._escaping = escaping

    def get_prompt_content(self, char_limit: int | None = None) -> str:
        escaped_label = escape_xml_attribute(self._label)
        payload = self._content
        if char_limit is not None:
            payload = payload[:char_limit] + "\n[truncated]"
        escaped_text = apply_escaping(payload, self._escaping)
        return f'<context label="{escaped_label}">\n{escaped_text}\n</context>'

    def get_prompt_label(self) -> str:
        return self._label


class FilePromptAdapter:
    def __init__(
        self,
        path: Path,
        label: str = "",
        role: str = "",
        escaping: str = "cdata",
        skeleton: bool = False,
        skeleton_files: dict[str, str] | None = None,
    ):
        test_label = label or path.name
        validate_label(test_label)
        self._path = path
        self._label = test_label.strip()
        self._role = role
        self._escaping = escaping
        self._skeleton = skeleton
        self._skeleton_files = skeleton_files or {}

    def get_prompt_content(self, char_limit: int | None = None) -> str:
        # Enforce reasonable size limit on path to prevent AST parser resource abuse
        if self._path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError(f"File too large: {self._path.name} exceeds 10MB limit.")

        content = self._path.read_text(encoding="utf-8")
        if self._skeleton:
            path_str = str(self._path)
            if path_str in self._skeleton_files:
                content = self._skeleton_files[path_str]
            else:
                try:
                    from specweaver.infrastructure.llm._skeleton import extract_ast_skeleton
                    content = extract_ast_skeleton(self._path, content)
                except Exception:
                    pass  # Graceful fallback to raw file content if AST parser fails

        if char_limit is not None:
            content = content[:char_limit] + "\n[truncated]"

        lang = detect_language(self._path)
        escaped_path = escape_xml_attribute(self._label)
        escaped_lang = escape_xml_attribute(lang)
        attrs = f'path="{escaped_path}" language="{escaped_lang}"'
        if self._role:
            escaped_role = escape_xml_attribute(self._role)
            attrs += f' role="{escaped_role}"'
        escaped_text = apply_escaping(content, self._escaping)
        return f'<file {attrs}>\n{escaped_text}\n</file>'

    def get_prompt_label(self) -> str:
        return self._label


class ProjectMetadataPromptAdapter:
    def __init__(self, metadata: ProjectMetadata):
        self._metadata = metadata

    def get_prompt_content(self, char_limit: int | None = None) -> str:
        from specweaver.commons import json
        raw_dict = self._metadata.model_dump()
        yaml_content = f"project_metadata:\n{json.dumps(raw_dict, indent=2)}"
        if char_limit is not None:
            yaml_content = yaml_content[:char_limit] + "\n[truncated]"
        return f"<project_metadata>\n{yaml_content}\n</project_metadata>"

    def get_prompt_label(self) -> str:
        return "project_metadata"
```

#### [MODIFY] [prompt_builder.py](file:///c:/development/pitbula/specweaver/src/specweaver/infrastructure/llm/prompt_builder.py) (to be moved to `prompt/builder.py`)
- Update `_ContentBlock` to store a reference to the source adapter:
```python
@dataclass
class _ContentBlock:
    text: str
    priority: int
    label: str = ""
    kind: str = "context"
    language: str = "text"
    file_path: str = ""
    role: str = ""
    tokens: int = 0
    truncated: bool = False
    escaping: str = "raw"
    source: PromptContentSource | None = None  # Track the adapter source for safe truncation
```
- Define explicit methods for context injection:
```python
    def add_context(
        self,
        source: PromptContentSource,
        *,
        priority: int = 3,
        slot: PromptSlot = PromptSlot.CONTEXT,
    ) -> PromptBuilder:
        """Add any context source implementing PromptContentSource."""
        if not self._is_slot_active(slot):
            return self
        
        if not (hasattr(source, "get_prompt_content") and hasattr(source, "get_prompt_label")):
            raise TypeError("Source must conform to PromptContentSource protocol")

        content = source.get_prompt_content()
        tokens = self._count(content)
        
        self._blocks.append(
            _ContentBlock(
                text=content,
                priority=max(1, priority),
                kind=slot.value,
                label=source.get_prompt_label(),
                tokens=tokens,
                escaping="raw",
                source=source,
            )
        )
        return self

    def add_string_context(
        self,
        content: str,
        label: str,
        *,
        priority: int = 3,
        slot: PromptSlot = PromptSlot.CONTEXT,
        escaping: str | None = None,
    ) -> PromptBuilder:
        """Add raw string context wrapped in StringPromptAdapter."""
        actual_escaping = escaping if escaping is not None else "cdata"
        adapter = StringPromptAdapter(content, label, escaping=actual_escaping)
        return self.add_context(adapter, priority=priority, slot=slot)

    def add_file_context(
        self,
        path: Path,
        *,
        priority: int = 2,
        label: str = "",
        role: str = "",
        skeleton: bool = False,
        escaping: str | None = None,
    ) -> PromptBuilder:
        """Add file context wrapped in FilePromptAdapter."""
        actual_escaping = escaping if escaping is not None else "cdata"
        adapter = FilePromptAdapter(
            path,
            label=label,
            role=role,
            escaping=actual_escaping,
            skeleton=skeleton,
            skeleton_files=self._skeleton_files,
        )
        return self.add_context(adapter, priority=priority, slot=PromptSlot.FILE)

    def add_project_metadata_context(
        self,
        metadata: ProjectMetadata | None,
        *,
        priority: int = 1,
    ) -> PromptBuilder:
        """Add project metadata wrapped in ProjectMetadataPromptAdapter."""
        if not metadata:
            return self
        adapter = ProjectMetadataPromptAdapter(metadata)
        return self.add_context(adapter, priority=priority, slot=PromptSlot.METADATA)
```
- Update `_truncate_group` to request safe truncation from adapters:
```python
    def _truncate_group(
        self,
        group: list[_ContentBlock],
        available: int,
    ) -> list[_ContentBlock]:
        if available <= 0:
            return []

        total = sum(b.tokens for b in group)
        if total == 0:
            return group

        result: list[_ContentBlock] = []
        shares = {i: int((b.tokens / total) * available) for i, b in enumerate(group)}

        for i, block in enumerate(group):
            share = shares[i]
            if block.tokens <= share:
                result.append(block)
            elif share > 0:
                char_limit = share * 4
                if block.source is not None:
                    try:
                        truncated_text = block.source.get_prompt_content(char_limit=char_limit)
                    except TypeError:
                        # Fallback for adapters without char_limit support
                        truncated_text = block.text[:char_limit] + "\n[truncated]"
                    tokens = self._count(truncated_text)
                    result.append(
                        _ContentBlock(
                            text=truncated_text,
                            priority=block.priority,
                            kind=block.kind,
                            label=block.label,
                            language=block.language,
                            file_path=block.file_path,
                            tokens=tokens,
                            truncated=True,
                            escaping="raw",
                            source=block.source,
                        )
                    )
                else:
                    truncated_text = block.text[:char_limit] + "\n[truncated]"
                    escaped_text = apply_escaping(truncated_text, block.escaping)
                    tokens = self._count(escaped_text)
                    result.append(
                        _ContentBlock(
                            text=truncated_text,
                            priority=block.priority,
                            kind=block.kind,
                            label=block.label,
                            language=block.language,
                            file_path=block.file_path,
                            tokens=tokens,
                            truncated=True,
                            escaping=block.escaping,
                        )
                    )
        return result
```
- Refactor existing legacy methods to delegate internally:
```python
    def add_file(self, path: Path, **kwargs: Any) -> PromptBuilder:
        return self.add_file_context(path, **kwargs)

    def add_project_metadata(self, metadata: ProjectMetadata | None, **kwargs: Any) -> PromptBuilder:
        return self.add_project_metadata_context(metadata, **kwargs)

    def add_context(self, text: Any, label: str = "", **kwargs: Any) -> PromptBuilder:
        if hasattr(text, "get_prompt_content") and hasattr(text, "get_prompt_label"):
            return self.add_context(text, **kwargs)
        return self.add_string_context(text, label, **kwargs)
```

#### [MODIFY] [_prompt_render.py](file:///c:/development/pitbula/specweaver/src/specweaver/infrastructure/llm/_prompt_render.py) (to be moved to `prompt/render.py`)
Update renderer functions to detect pre-formatted XML blocks:
```python
def render_files(blocks: list[_ContentBlock]) -> str | None:
    files = [b for b in blocks if b.kind == "file"]
    if not files:
        return None
    file_parts: list[str] = []
    for f in files:
        if f.text.startswith("<file"):
            file_parts.append(f.text)
        else:
            escaped_path = escape_xml_attribute(f.label)
            escaped_lang = escape_xml_attribute(f.language)
            attrs = f'path="{escaped_path}" language="{escaped_lang}"'
            if f.role:
                escaped_role = escape_xml_attribute(f.role)
                attrs += f' role="{escaped_role}"'
            escaped_text = apply_escaping(f.text, f.escaping)
            file_parts.append(f"<file {attrs}>\n{escaped_text}\n</file>")
    inner = "\n".join(file_parts)
    return f"<file_contents>\n{inner}\n</file_contents>"

def _render_contexts(blocks: list[_ContentBlock]) -> str | None:
    contexts = [b for b in blocks if b.kind == "context"]
    if not contexts:
        return None
    parts: list[str] = []
    for ctx in contexts:
        if ctx.text.startswith("<context"):
            parts.append(ctx.text)
        else:
            escaped_label = escape_xml_attribute(ctx.label)
            escaped_text = apply_escaping(ctx.text, ctx.escaping)
            parts.append(f'<context label="{escaped_label}">\n{escaped_text}\n</context>')
    return "\n\n".join(parts)

def _render_topology(blocks: list[_ContentBlock]) -> str | None:
    topology = [b for b in blocks if b.kind == "topology"]
    if not topology:
        return None
    parts: list[str] = []
    for topo in topology:
        if topo.text.startswith("<topology"):
            parts.append(topo.text)
        else:
            escaped_text = apply_escaping(topo.text, topo.escaping)
            parts.append(f"<topology>\n{escaped_text}\n</topology>")
    return "\n\n".join(parts)
```

### [Component: Graph Module]

#### [MODIFY] [topology.py](file:///c:/development/pitbula/specweaver/src/specweaver/assurance/graph/topology.py)
- Implement `get_prompt_content(self, char_limit: int | None = None)` and `get_prompt_label()` on the `TopologyContext` dataclass natively so it acts as its own duck-typed adapter:
```python
  def get_prompt_content(self, char_limit: int | None = None) -> str:
      constraints_str = ", ".join(self.constraints) if self.constraints else "none"
      content = (
          f"  - {self.name} ({self.relationship}): "
          f"{self.purpose} [archetype={self.archetype}, "
          f"constraints={constraints_str}]"
      )
      if char_limit is not None:
          content = content[:char_limit] + "\n[truncated]"
      return f"<topology>\n{content}\n</topology>"

  def get_prompt_label(self) -> str:
      return self.name
```
- No imports of LLM modules in `topology.py`.

---

## 3. Verification Plan

### Automated Tests
1. **Unit tests for adapters**:
   - Verify `StringPromptAdapter` produces correct XML tags and CDATA escaping.
   - Verify `StringPromptAdapter` raises `ValueError` on malformed or empty label input.
   - Verify `FilePromptAdapter` correctly reads files, validates labels, and formats `<file>` attributes.
   - Verify `ProjectMetadataPromptAdapter` serializes and outputs `<project_metadata>` block.
2. **Unit tests for Truncation Safety**:
   - Verify `StringPromptAdapter` and `FilePromptAdapter` truncate raw payload before escaping/wrapping, ensuring complete tag boundaries (e.g. CDATA and XML tags are closed properly).
3. **Integration tests**:
   - Verify that calling the new strongly-typed methods on `PromptBuilder` formats and builds correctly.
   - Verify that `TopologyContext` works seamlessly when passed to `add_context()`.
4. **Tach constraints**:
   - Verify `tach check` passes (no LLM imports in `topology.py`).
