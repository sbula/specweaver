# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Project scaffolding — creates the .specweaver/ directory structure.

Creates:
- context.yaml           — root boundary manifest (context.yaml spec)
- .specweaver/           — marker directory (config lives in DB)
- .specweaver/templates/ — spec templates (component_spec.md)
- specs/                 — where specs live
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


_DEFAULT_CONTEXT_YAML = """\
# Root boundary manifest — see docs/architecture/context_yaml_spec.md

name: {project_name}
level: system
purpose: >
  TODO: One sentence describing this project's responsibility.

archetype: orchestrator

consumes: []

exposes: []

owner: TODO
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
    context_file: Path
    constitution_file: Path
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

    # 1. context.yaml — root boundary manifest (only if not present)
    context_file = project_path / "context.yaml"
    if not context_file.exists():
        project_name = project_path.name.lower().replace(" ", "-")
        context_content = _DEFAULT_CONTEXT_YAML.format(project_name=project_name)
        context_file.write_text(context_content, encoding="utf-8")
        created.append("context.yaml")

    # 2. .specweaver/
    sw_dir = project_path / ".specweaver"
    if not sw_dir.exists():
        sw_dir.mkdir(parents=True)
        created.append(".specweaver/")

    # 3. specs/
    specs_dir = project_path / "specs"
    if not specs_dir.exists():
        specs_dir.mkdir(parents=True)
        created.append("specs/")

    # 4. .specweaver/templates/component_spec.md (only if not present)
    templates_dir = sw_dir / "templates"
    if not templates_dir.exists():
        templates_dir.mkdir(parents=True)
        created.append(".specweaver/templates/")

    tmpl_file = templates_dir / "component_spec.md"
    if not tmpl_file.exists():
        tmpl_file.write_text(_DEFAULT_COMPONENT_SPEC, encoding="utf-8")
        created.append(".specweaver/templates/component_spec.md")

    # 5. CONSTITUTION.md (starter template, only if not present)
    from specweaver.project.constitution import generate_constitution

    constitution_path = project_path / "CONSTITUTION.md"
    constitution_existed = constitution_path.exists()
    project_name = project_path.name.lower().replace(" ", "-")
    constitution_file = generate_constitution(project_path, project_name)
    if not constitution_existed:
        created.append("CONSTITUTION.md")

    result = ScaffoldResult(
        project_path=project_path,
        specweaver_dir=sw_dir,
        specs_dir=specs_dir,
        context_file=context_file,
        constitution_file=constitution_file,
        created=created,
    )
    if created:
        logger.info(
            "scaffold_project: created %d item(s) in %s: %s",
            len(created),
            project_path,
            ", ".join(created),
        )
    else:
        logger.debug("scaffold_project: %s already scaffolded", project_path)
    return result
