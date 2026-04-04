# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Spec validation rules (S01-S11).

Structure tests and completeness tests from the 11-test battery.
Auto-registers all built-in spec rules in the global RuleRegistry.
"""

from specweaver.validation.registry import get_registry

from .s01_one_sentence import OneSentenceRule
from .s02_single_setup import SingleSetupRule
from .s03_stranger import StrangerTestRule
from .s04_dependency_dir import DependencyDirectionRule
from .s05_day_test import DayTestRule
from .s06_concrete_example import ConcreteExampleRule
from .s07_test_first import TestFirstRule
from .s08_ambiguity import AmbiguityRule
from .s09_error_path import ErrorPathRule
from .s10_done_definition import DoneDefinitionRule
from .s11_terminology import TerminologyRule

_reg = get_registry()
_reg.register("S01", OneSentenceRule, "spec")
_reg.register("S02", SingleSetupRule, "spec")
_reg.register("S03", StrangerTestRule, "spec")
_reg.register("S04", DependencyDirectionRule, "spec")
_reg.register("S05", DayTestRule, "spec")
_reg.register("S06", ConcreteExampleRule, "spec")
_reg.register("S07", TestFirstRule, "spec")
_reg.register("S08", AmbiguityRule, "spec")
_reg.register("S09", ErrorPathRule, "spec")
_reg.register("S10", DoneDefinitionRule, "spec")
_reg.register("S11", TerminologyRule, "spec")
