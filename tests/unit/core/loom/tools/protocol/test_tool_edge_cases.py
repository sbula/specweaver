
from specweaver.core.loom.tools.protocol.tool import ProtocolTool


def test_tool_endpoints_generic_exception(monkeypatch):
    """Story 3: Tool explicitly handles unhandled exceptions from extract_schema_endpoints."""

    def mock_run(*args, **kwargs):
        raise ValueError("OS Level Fault")

    monkeypatch.setattr("specweaver.core.loom.atoms.protocol.atom.ProtocolAtom.run", mock_run)

    tool = ProtocolTool()
    result = tool.extract_schema_endpoints("dummy.proto")

    assert "error" in result["status"]
    assert "OS Level Fault" in result["error"]
    assert "Tool boundary exception" in result["error"]


def test_tool_messages_generic_exception(monkeypatch):
    """Story 4: Tool explicitly handles unhandled exceptions from extract_schema_messages."""

    def mock_run(*args, **kwargs):
        raise RuntimeError("Runtime Crash")

    monkeypatch.setattr("specweaver.core.loom.atoms.protocol.atom.ProtocolAtom.run", mock_run)

    tool = ProtocolTool()
    result = tool.extract_schema_messages("dummy.yaml")

    assert "error" in result["status"]
    assert "Runtime Crash" in result["error"]
    assert "Tool boundary exception" in result["error"]
