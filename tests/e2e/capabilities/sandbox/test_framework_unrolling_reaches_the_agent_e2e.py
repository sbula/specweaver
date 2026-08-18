# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An agent reading a framework codebase is told what the annotations *do*.

Proves: INT-US-05 P-4

`INT-US-05` P-2 proves the seam — an agent's `read_unrolled_symbol` intent reaches the evaluator
through the code-structure atom. This is the journey on top of it: a **shipped** framework schema, a
real Java source file, and the role-gated tool an agent actually holds. The point of the capability is
that a model reading `@RestController` is told it means `@Controller` + `@ResponseBody`, rather than
being left to know Spring Boot.

Nothing here is a fixture schema. `load_evaluator_schemas()` returns the five that ship in the wheel —
`spring-boot`, `quarkus`, `nestjs`, `fastapi`, `actix-web` — and this drives the packaged `spring-boot`
one. A schema that ships and is never wired to the tool would pass every unit test in the capability.

**A defect surfaced while writing this, and it is NOT pinned here yet.** An annotation carrying
arguments is extracted with them attached — the Java parser yields `GetMapping("/orders/{id}")`, the
Rust parser `get("/orders")` — while every schema key is a bare name (`GetMapping:`, `get:`). So no
parameterised annotation can ever match, and routing annotations nearly always carry a path.
Argument-less ones (`@RestController`, `@Transactional`, JAX-RS `@GET`) work; the rest are unreachable.

The failing test for it is written and held back rather than committed against the wrong blocker.
`TECH-064` covers polyglot *architecture checks* returning success while doing nothing, which is a
different subject in a different capability, and attaching this to it would pass
`check_xfail_blockers.py` mechanically while being wrong. It needs its own ticket, and minting one is
not a decision to take mid-test.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom
from specweaver.sandbox.code_structure.interfaces.tool import CodeStructureTool
from specweaver.sandbox.security import AccessMode, FolderGrant
from specweaver.workflows.evaluators.loader import load_evaluator_schemas

if TYPE_CHECKING:
    from pathlib import Path

_CONTROLLER = """package com.acme.api;

import org.springframework.web.bind.annotation.*;

@RestController
public class OrderController {
    @GetMapping("/orders/{id}")
    public String find(String id) { return id; }
}
"""


def _tool(project: Path, archetype: str) -> CodeStructureTool:
    """The tool as an agent gets it: packaged schemas, a role, and a folder grant."""
    atom = CodeStructureAtom(
        cwd=project, evaluator_schemas=load_evaluator_schemas(), active_archetype=archetype
    )
    return CodeStructureTool(
        atom=atom,
        role="implementer",
        grants=[FolderGrant("src", AccessMode.READ, recursive=True)],
        hidden_intents=[],
    )


@pytest.fixture
def spring_project(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "OrderController.java").write_text(_CONTROLLER, encoding="utf-8")
    return tmp_path


def test_a_shipped_schema_unrolls_a_real_annotation_for_the_agent(spring_project: Path) -> None:
    """The packaged `spring-boot` schema reaches an agent's tool call against real Java."""
    result = _tool(spring_project, "spring-boot").read_unrolled_symbol(
        "src/OrderController.java", "OrderController"
    )

    assert result.status == "success", result.message
    symbol = (result.data or {}).get("symbol", "")

    # The class body must still be there — unrolling adds meaning, it does not replace the source.
    assert "public class OrderController" in symbol, symbol
    # And the annotation's meaning must be there, which is the whole capability.
    assert "@Controller" in symbol and "@ResponseBody" in symbol, (
        "`@RestController` reached the agent unexplained — the shipped spring-boot schema says it "
        f"means @Controller + @ResponseBody, and that never arrived:\n{symbol}"
    )


def test_the_same_file_without_the_schema_is_left_raw(spring_project: Path) -> None:
    """The control. Without it, 'the annotation appears' proves nothing — it is in the source already.

    `generic` is the atom's default archetype and carries no framework knowledge, so the same call
    returns the source untouched. That is what makes the assertion above about *unrolling* rather than
    about a file being read.
    """
    result = _tool(spring_project, "generic").read_unrolled_symbol(
        "src/OrderController.java", "OrderController"
    )

    assert result.status == "success", result.message
    symbol = (result.data or {}).get("symbol", "")
    assert "public class OrderController" in symbol
    assert "@ResponseBody" not in symbol, (
        f"the generic archetype invented framework meaning it has no schema for:\n{symbol}"
    )
