# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Validation pipeline models -- defines which rules run and their config.

This is a sub-pipeline internal to validation handlers. It does NOT use
the orchestration PipelineStep/PipelineDefinition models. Each step is
a rule-atom: action is always 'check', target is the spec/code.

Architecture:
    Orchestration pipeline (PipelineDefinition / PipelineStep)
        draft -> validate -> review -> generate -> ...
                    |
        ValidateSpecHandler internally runs rule sub-pipeline
                    |
    Validation sub-pipeline (ValidationPipeline / ValidationStep)
        S01 -> S02 -> S06 -> S05 -> S08 -> D01 -> ...
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ValidationStep(BaseModel):
    """A single rule in the validation sub-pipeline.

    Attributes:
        name: Human-readable step identifier (e.g. 's01_one_sentence').
        rule: Rule ID to look up in the registry (e.g. 'S01', 'D01').
        params: Threshold and config kwargs passed to the rule constructor.
        path: Path to custom rule .py file (D-prefix rules only).
    """

    name: str
    rule: str
    params: dict[str, Any] = Field(default_factory=dict)
    path: str | None = None


class ValidationPipeline(BaseModel):
    """A named set of rules with ordering and configuration.

    Can be a standalone pipeline (steps fully specified) or an inheriting
    pipeline (extends a base, with override/remove/add operations).

    Attributes:
        name: Pipeline identifier (e.g. 'validation_spec_default').
        description: Human-readable description.
        version: Schema version for compatibility.
        steps: Ordered list of validation steps.
        extends: Name of base pipeline to inherit from.
        override: Step-name -> config overrides (params, etc.).
        remove: Step names to remove from the base.
        add: New steps to insert (with optional after/before placement).
    """

    name: str
    description: str = ""
    version: str = "1.0"
    steps: list[ValidationStep] = Field(default_factory=list)

    # Inheritance fields (resolved before execution)
    extends: str | None = None
    override: dict[str, dict[str, Any]] | None = None
    remove: list[str] | None = None
    add: list[dict[str, Any]] | None = None

    def get_step(self, name: str) -> ValidationStep | None:
        """Find a step by name, or None if not found."""
        for step in self.steps:
            if step.name == name:
                return step
        return None
