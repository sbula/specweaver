# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

import pytest

from specweaver.validation.drift_detector import detect_drift
from specweaver.validation.models import Severity

# Attempt to import tree-sitter to ensure it's available
try:
    import tree_sitter
    import tree_sitter_python

    HAS_TREE_SITTER = True
except Exception as e:
    import builtins

    builtins.print(f"IMPORT ERROR: {e}")
    HAS_TREE_SITTER = False


class MockMethodSignature:
    def __init__(self, name: str, parameters: list[str] | None = None, return_type: str = ""):
        self.name = name
        self.parameters = parameters or []
        self.return_type = return_type


class MockImplementationTask:
    def __init__(
        self,
        sequence_number: int,
        name: str,
        files: list[str],
        expected_signatures: dict[str, list[MockMethodSignature]],
    ):
        self.sequence_number = sequence_number
        self.name = name
        self.files = files
        self.expected_signatures = expected_signatures


class MockPlanArtifact:
    def __init__(self, tasks: list[MockImplementationTask], file_layout: list | None = None):
        self.tasks = tasks
        self.file_layout = file_layout or []


@pytest.mark.skipif(not HAS_TREE_SITTER, reason="Requires tree-sitter-python")
def test_real_tree_sitter_integration() -> None:
    # 1. Provide a real Python source code snippet simulating an AST
    source_code = b"""
import os

def simple_function(a_param):
    pass

async def my_async_func(x, y):
    pass

class MyClass:
    def __init__(self, c_param):
        self._private_member = True

    def public_method(self, data: dict) -> None:
        def inner_function():
            pass
        pass

    def _private_method(self):
        pass

def splat_func(*args, **kwargs):
    pass

@staticmethod
def decorated_func():
    pass
"""

    parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_python.language()))
    tree = parser.parse(source_code)

    # 2. Build a PlanArtifact that expects some drift and some perfect matches
    plan = MockPlanArtifact(
        tasks=[
            MockImplementationTask(
                sequence_number=1,
                name="Integration Task",
                files=["src/app.py"],
                expected_signatures={
                    "src/app.py": [
                        MockMethodSignature(name="simple_function", parameters=["a_param"]),
                        MockMethodSignature(
                            name="my_async_func", parameters=["x", "z"]
                        ),  # 'z' instead of 'y' to cause drift WARNING
                        MockMethodSignature(name="MyClass"),
                        MockMethodSignature(name="public_method", parameters=["data: dict"]),
                        MockMethodSignature(
                            name="missing_function", parameters=[]
                        ),  # Missing ERROR
                        MockMethodSignature(
                            name="splat_func", parameters=["*args: list", "**kwargs: dict"]
                        ),
                        MockMethodSignature(name="decorated_func", parameters=[]),
                    ]
                },
            )
        ],
    )

    # 3. Detect Drift
    report = detect_drift(tree, plan, "src/app.py")

    # 4. Verify outputs
    assert report.is_drifted  # Because of missing_function
    findings = report.findings

    # We expect:
    # 1. Missing expected method missing_function (ERROR)
    # 2. Parameter drift in my_async_func: Expected ['x', 'z'], Actual ['x', 'y'] (WARNING)
    # And NO unauthorized methods because:
    # - __init__, _private_method are filtered by starting with '_'
    # - inner_function is NOT extracted (we stopped at boundaries)

    error_findings = [f for f in findings if f.severity == Severity.ERROR]
    warning_findings = [f for f in findings if f.severity == Severity.WARNING]

    # Verify ERROR
    # Wait, 'MyClass' might be flagged as unauthorized if not matched correctly?
    # No, 'MyClass' is expected!
    # Let's check error findings
    assert len(error_findings) == 1
    assert "missing_function" in error_findings[0].description

    # Verify WARNING
    assert len(warning_findings) == 1
    assert "Parameter drift" in warning_findings[0].description
    assert "my_async_func" in warning_findings[0].description
    assert "z" in warning_findings[0].description

    # Since splat_func didn't issue a warning, it means args and kwargs matched cleanly!
    # And since decorated_func didn't issue an ERROR, it means it was extracted perfectly!
