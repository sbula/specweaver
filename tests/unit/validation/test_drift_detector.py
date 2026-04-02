# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

from specweaver.validation.drift_detector import detect_drift, detect_workspace_drift


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


class MockFileChange:
    def __init__(self, path: str, action: str):
        self.path = path
        self.action = action


class MockPlanArtifact:
    def __init__(
        self, tasks: list[MockImplementationTask], file_layout: list[MockFileChange] | None = None
    ):
        self.tasks = tasks
        self.file_layout = file_layout or []


class MockNode:
    def __init__(
        self,
        type_: str,
        text: bytes,
        children: list["MockNode"] | None = None,
        field_children: dict | None = None,
    ):
        self.type = type_
        self.text = text
        self.children = children or []
        self._field_children = field_children or {}

    def child_by_field_name(self, name: str) -> "MockNode | None":
        return self._field_children.get(name)


def test_perfect_match() -> None:
    plan = MockPlanArtifact(
        tasks=[
            MockImplementationTask(
                sequence_number=1,
                name="t1",
                files=["test.py"],
                expected_signatures={
                    "test.py": [MockMethodSignature(name="my_func", parameters=["user_id"])]
                },
            )
        ],
    )

    name_node = MockNode("identifier", b"my_func")
    id_node = MockNode("identifier", b"user_id")
    params_node = MockNode("parameters", b"", children=[id_node])

    func_node = MockNode(
        "function_definition",
        b"def my_func(user_id): pass",
        field_children={"name": name_node, "parameters": params_node},
    )
    root = MockNode("module", b"", children=[func_node])

    class MockTree:
        @property
        def root_node(self):
            return root

    report = detect_drift(MockTree(), plan, "test.py")
    assert not report.is_drifted
    assert len(report.findings) == 0


def test_missing_method_gap() -> None:
    plan = MockPlanArtifact(
        tasks=[
            MockImplementationTask(
                sequence_number=1,
                name="t1",
                files=["test.py"],
                expected_signatures={"test.py": [MockMethodSignature(name="expected_func")]},
            )
        ],
    )

    root = MockNode("module", b"")

    class MockTree:
        @property
        def root_node(self):
            return root

    report = detect_drift(MockTree(), plan, "test.py")
    assert report.is_drifted
    assert len(report.findings) == 1
    assert "expected_func" in report.findings[0].description


def test_added_unauthorized_method_drift() -> None:
    plan = MockPlanArtifact(
        tasks=[
            MockImplementationTask(
                sequence_number=1,
                name="t1",
                files=["test.py"],
                expected_signatures={"test.py": [MockMethodSignature(name="expected_func")]},
            )
        ],
    )

    name_node1 = MockNode("identifier", b"expected_func")
    func_node1 = MockNode(
        "function_definition", b"def expected_func(): pass", field_children={"name": name_node1}
    )

    name_node2 = MockNode("identifier", b"unauthorized_func")
    func_node2 = MockNode(
        "function_definition", b"def unauthorized_func(): pass", field_children={"name": name_node2}
    )

    name_node3 = MockNode("identifier", b"_private_func")
    func_node3 = MockNode(
        "function_definition", b"def _private_func(): pass", field_children={"name": name_node3}
    )

    root = MockNode("module", b"", children=[func_node1, func_node2, func_node3])

    class MockTree:
        @property
        def root_node(self):
            return root

    report = detect_drift(MockTree(), plan, "test.py")
    assert report.is_drifted
    # Should only find 'unauthorized_func', completely ignore '_private_func'
    assert len(report.findings) == 1
    assert "unauthorized_func" in report.findings[0].description
    assert report.findings[0].actual_signature == "unauthorized_func"


def test_parameter_drift() -> None:
    plan = MockPlanArtifact(
        tasks=[
            MockImplementationTask(
                sequence_number=1,
                name="t1",
                files=["test.py"],
                expected_signatures={
                    "test.py": [
                        # Plan expects parameters (ast, plan) and cleans it up natively
                        MockMethodSignature(
                            name="detect",
                            parameters=["ast: tree_sitter.Tree", "plan: PlanArtifactProtocol"],
                        )
                    ]
                },
            )
        ],
    )

    name_node = MockNode("identifier", b"detect")
    # Developer implemented detect(ast) missing 'plan'
    id_node = MockNode("identifier", b"ast")
    params_node = MockNode("parameters", b"", children=[id_node])

    func_node = MockNode(
        "function_definition",
        b"def detect(ast): pass",
        field_children={"name": name_node, "parameters": params_node},
    )
    root = MockNode("module", b"", children=[func_node])

    class MockTree:
        @property
        def root_node(self):
            return root

    report = detect_drift(MockTree(), plan, "test.py")
    # Parameter drift issues WARNING, so is_drifted might be False if no ERROR, let's keep it robust
    assert not report.is_drifted
    assert len(report.findings) == 1
    assert "Parameter drift" in report.findings[0].description
    assert "Expected ['ast', 'plan']" in report.findings[0].description


def test_detect_workspace_drift() -> None:
    plan = MockPlanArtifact(
        tasks=[],
        file_layout=[
            MockFileChange(path="src/app.py", action="create"),
            MockFileChange(path="src/utils.py", action="modify"),
            MockFileChange(path="src/old.py", action="delete"),
        ],
    )

    # Simulate src/utils.py exists, but src/app.py is completely missing
    present_files = {"src/utils.py"}

    findings = detect_workspace_drift(plan, present_files)
    assert len(findings) == 1
    assert "src/app.py" in findings[0].description


def test_detect_drift_none_ast() -> None:
    plan = MockPlanArtifact(tasks=[])
    report = detect_drift(None, plan, "test.py")
    assert not report.is_drifted
    assert len(report.findings) == 0
