from pathlib import Path

from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.filesystem.interfaces.models import ROLE_INTENTS
from specweaver.sandbox.security import ReadOnlyWorkspaceBoundary


class TestDispatcherArbiterRole:
    def test_arbiter_agent_in_role_intents(self):
        assert "arbiter_agent" in ROLE_INTENTS

    def test_arbiter_agent_has_no_write_intents(self):
        intents = ROLE_INTENTS["arbiter_agent"]
        assert "write_file" not in intents
        assert "edit_file" not in intents
        assert "create_file" not in intents
        assert "delete_file" not in intents

    def test_create_standard_set_arbiter_uses_read_only_grants(self, tmp_path: Path):
        parent = tmp_path / "mock_api_path"
        parent.mkdir(parents=True)
        boundary = ReadOnlyWorkspaceBoundary(api_paths=[parent])
        dispatcher = ToolDispatcher.create_standard_set(
            boundary=boundary, role="arbiter_agent", allowed_tools=["fs"]
        )

        fs_interface = dispatcher._interfaces[0]
        # the grants on the fs_interface should only equal the api_path because ReadOnlyWorkspaceBoundary has no roots!
        # _tool._grants is used by FileSystemTool
        assert len(fs_interface._tool._grants) == 1
        assert fs_interface._tool._grants[0].path == str(parent)
        assert fs_interface._tool._grants[0].mode == "read"
