# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Code validation rules (C01-C08).

Static analysis rules for generated code quality.
Auto-registers all built-in code rules in the global RuleRegistry.
"""

from specweaver.assurance.validation.registry import get_registry

from .c01_syntax_valid import SyntaxValidRule
from .c02_tests_exist import TestsExistRule
from .c03_tests_pass import TestsPassRule
from .c04_coverage import CoverageRule
from .c05_import_direction import ImportDirectionRule
from .c06_no_bare_except import NoBareExceptRule
from .c07_no_orphan_todo import NoOrphanTodoRule
from .c08_type_hints import TypeHintsRule
from .c09_traceability import TraceabilityRule

_reg = get_registry()
_reg.register("C01", SyntaxValidRule, "code")
_reg.register("C02", TestsExistRule, "code")
_reg.register("C03", TestsPassRule, "code")
_reg.register("C04", CoverageRule, "code")
_reg.register("C05", ImportDirectionRule, "code")
_reg.register("C06", NoBareExceptRule, "code")
_reg.register("C07", NoOrphanTodoRule, "code")
_reg.register("C08", TypeHintsRule, "code")
_reg.register("C09", TraceabilityRule, "code")
