# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Project scaffolding — creates the .specweaver/ directory structure.

Creates:
- .specweaver/           — SpecWeaver config root
- .specweaver/config.yaml — default config (non-secrets)
- .specweaver/templates/ — spec templates (component_spec.md)
- specs/                 — where specs live
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_DEFAULT_CONFIG = """\
# SpecWeaver Configuration
# See: docs/proposals/mvp_implementation_plan.md

# LLM settings
# API key is loaded from GEMINI_API_KEY env var or .env file, NOT from here.
llm:
  # Model to use for LLM-based rules and drafting
  model: gemini-2.5-flash
  # Temperature for generation (0.0 = deterministic, 1.0 = creative)
  temperature: 0.7
  # Maximum output tokens per generation
  max_output_tokens: 4096
  # Response format: "text" or "json"
  response_format: text
"""


_DEFAULT_COMPONENT_SPEC = """\
# {{ component_name }} - Component Spec

> **Status**: DRAFT
> **Date**: {{ date }}
> **Layer**: Component (L2)
> **Parent Feature**: {{ parent_feature | default("N/A") }}

---

## 1. Purpose

_One paragraph. What this component does and why it exists._

{{ purpose | default("TODO: Describe the single responsibility.") }}

---

## 2. Contract

_What this component promises. The public interface._

### 2.1 Data Models

```python
# TODO: Define input/output types
```

### 2.2 Interface

```python
# TODO: Define public functions/methods
```

### 2.3 Examples

**Valid input -> expected output:**
```
Input:  TODO
Output: TODO
```

---

## 3. Protocol

_What steps happen at runtime, and in what order._

1. TODO: Step 1
2. TODO: Step 2

---

## 4. Policy

_Configurable constraints and error handling._

### 4.1 Error Handling

| Error Condition | Behavior |
|:---|:---|
| TODO | TODO |

---

## 5. Boundaries

_What this component does NOT do._

| Concern | Owned By |
|:---|:---|
| TODO | TODO |

---

## Done Definition

- [ ] All public methods have unit tests
- [ ] Coverage >= 70%
- [ ] `sw check --level=component` passes
"""


@dataclass(frozen=True)
class ScaffoldResult:
    """Summary of what scaffold_project created or found."""

    project_path: Path
    specweaver_dir: Path
    specs_dir: Path
    config_file: Path
    created: list[str]


def scaffold_project(project_path: Path) -> ScaffoldResult:
    """Create the .specweaver/ directory structure in a target project.

    Idempotent: existing files are NOT overwritten. Only missing items
    are created.

    Args:
        project_path: Root directory of the target project.

    Returns:
        ScaffoldResult with paths and a list of created items.

    Raises:
        FileNotFoundError: If project_path does not exist.
    """
    if not project_path.exists():
        msg = f"Project path does not exist: {project_path}"
        raise FileNotFoundError(msg)

    created: list[str] = []

    # 1. .specweaver/
    sw_dir = project_path / ".specweaver"
    if not sw_dir.exists():
        sw_dir.mkdir(parents=True)
        created.append(".specweaver/")

    # 2. specs/
    specs_dir = project_path / "specs"
    if not specs_dir.exists():
        specs_dir.mkdir(parents=True)
        created.append("specs/")

    # 3. .specweaver/config.yaml (only if not present)
    config_file = sw_dir / "config.yaml"
    if not config_file.exists():
        config_file.write_text(_DEFAULT_CONFIG, encoding="utf-8")
        created.append(".specweaver/config.yaml")

    # 4. .specweaver/templates/component_spec.md (only if not present)
    templates_dir = sw_dir / "templates"
    if not templates_dir.exists():
        templates_dir.mkdir(parents=True)
        created.append(".specweaver/templates/")

    tmpl_file = templates_dir / "component_spec.md"
    if not tmpl_file.exists():
        tmpl_file.write_text(_DEFAULT_COMPONENT_SPEC, encoding="utf-8")
        created.append(".specweaver/templates/component_spec.md")

    return ScaffoldResult(
        project_path=project_path,
        specweaver_dir=sw_dir,
        specs_dir=specs_dir,
        config_file=config_file,
        created=created,
    )
