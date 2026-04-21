import json
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.loom.tools.mcp.tool import MCPExplorerTool


class TestMCPExplorerTool:

    @pytest.fixture
    def mock_context(self) -> MagicMock:
        ctx = MagicMock()
        ctx.topology.mcp_servers = {
            "test-db": {
                "command": "docker",
                "args": ["run", "-i", "db-mcp"],
                "env": {},
            }
        }
        return ctx

    def test_list_servers(self, mock_context: MagicMock) -> None:
        tool = MCPExplorerTool(mock_context)
        result = tool._intent_list_servers({})
        assert result.status == "success"
        parsed = json.loads(result.data)
        assert parsed == ["test-db"]

    @patch("specweaver.core.loom.tools.mcp.tool.MCPExecutor")
    def test_list_resources(self, mock_executor_class: MagicMock, mock_context: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_executor_class.return_value = mock_instance

        # Mock 3 rpc calls: initialize, notifications/initialized, resources/list
        mock_instance.call_rpc.side_effect = [
            {"result": {"version": "v1"}},  # init
            None,                           # notifications
            {"result": {"resources": [{"uri": "test://my-uri"}]}}, # list
        ]

        tool = MCPExplorerTool(mock_context)
        result = tool._intent_list_resources({"server_name": "test-db"})

        assert result.status == "success"

        parsed = json.loads(result.data)
        assert "resources" in parsed
        assert parsed["resources"][0]["uri"] == "test://my-uri"

        # Ensure cleanup happened
        mock_instance.close.assert_called_once()

    @patch("specweaver.core.loom.tools.mcp.tool.MCPExecutor")
    def test_read_resource(self, mock_executor_class: MagicMock, mock_context: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_executor_class.return_value = mock_instance

        mock_instance.call_rpc.side_effect = [
            {"result": {}},  # init
            None,            # notifications
            {"result": {"contents": [{"text": "DB SCHEMA..."}]}}, # read
        ]

        tool = MCPExplorerTool(mock_context)
        result = tool._intent_read_resource({"server_name": "test-db", "uri": "test://my-uri"})

        assert result.status == "success"
        parsed = json.loads(result.data)
        assert "contents" in parsed

        # Verify the uri was passed
        last_call_args = mock_instance.call_rpc.call_args_list[-1]
        assert last_call_args.kwargs.get("method") == "resources/read"
        assert last_call_args.kwargs.get("params", {}).get("uri") == "test://my-uri"

    def test_missing_server_name(self, mock_context: MagicMock) -> None:
        tool = MCPExplorerTool(mock_context)
        result = tool._intent_list_resources({})
        assert result.status == "error"
        assert "Missing" in result.message

    def test_unknown_server_name(self, mock_context: MagicMock) -> None:
        tool = MCPExplorerTool(mock_context)
        result = tool._intent_list_resources({"server_name": "non-existent"})
        assert result.status == "error"
        assert "Unknown MCP" in result.message

    def test_execute_mcp_query_missing_topology(self) -> None:
        ctx = MagicMock()
        del ctx.topology
        tool = MCPExplorerTool(ctx)
        result = tool._execute_mcp_query("test-db", "resources/list", {})
        assert result.status == "error"
        assert "Context Topology missing" in result.message

    @patch("specweaver.core.loom.tools.mcp.tool.MCPExecutor")
    def test_execute_mcp_query_executor_error(self, mock_executor_class: MagicMock, mock_context: MagicMock) -> None:
        from specweaver.core.loom.commons.mcp.executor import MCPExecutorError

        mock_instance = MagicMock()
        mock_executor_class.return_value = mock_instance
        mock_instance.call_rpc.side_effect = MCPExecutorError("Failed to run dummy")

        tool = MCPExplorerTool(mock_context)
        result = tool._execute_mcp_query("test-db", "resources/list", {})
        assert result.status == "error"
        assert "Execution Error against test-db" in result.message
        assert "Failed to run dummy" in result.message

    def test_execute_mcp_query_missing_command(self) -> None:
        ctx = MagicMock()
        ctx.topology.mcp_servers = {"test-db": {"args": ["just_args"]}}
        tool = MCPExplorerTool(ctx)
        result = tool._execute_mcp_query("test-db", "resources/list", {})
        assert result.status == "error"
        assert "missing target executable command bounds" in result.message

class TestArchitectMCPInterface:
    def test_requires_architect_role(self) -> None:
        from specweaver.core.loom.tools.mcp.interfaces import ArchitectMCPInterface
        from specweaver.core.loom.tools.mcp.models import MCPToolError

        tool = MagicMock()
        tool.ROLE_INTENTS = {"reviewer": frozenset()}

        with pytest.raises(MCPToolError, match=r"Architect role not configured on tool."):
            ArchitectMCPInterface(tool)

    def test_definitions(self) -> None:
        from specweaver.core.loom.tools.mcp.interfaces import ArchitectMCPInterface

        ctx = MagicMock()
        ctx.topology.mcp_servers = {"test-db": {}}
        tool = MCPExplorerTool(ctx)
        interface = ArchitectMCPInterface(tool)

        defs = interface.definitions()
        assert len(defs) == 3
        # Should contain ToolDefinition objects for list_servers, list_resources, read_resource
        names = [d.name for d in defs]
        assert "list_servers" in names
        assert "list_resources" in names
        assert "read_resource" in names
        assert interface.is_visible() is True
