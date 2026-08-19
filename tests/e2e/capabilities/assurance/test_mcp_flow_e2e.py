# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""E2E flow engine integrations testing the Pre-fetch Context Assembler (SF-3).

Proves: C-INTL-02 FR-2, C-INTL-02 FR-3, C-INTL-02 FR-4

A real MCP server is booted as a subprocess and answered over real JSON-RPC on stdio; what it
returns is asserted inside the `environment_context` the generator is handed. That is the whole
chain — boot, fetch, inject — and no unit test crosses it, because each side of it is a process
boundary.

The tag was missing, not the coverage, so `check_fr_coverage.py C-INTL-02` saw unit tests only and
US-23 read as owing an integration proof it already had. Verified by mutation before being written
down here:

* FR-2/FR-3 — the assembler's `if not servers or not resources` guard forced true, so no server is
  ever booted: 3 of 4 fail.
* FR-3 — the fetched `content` replaced by `""`, so the boot happens and returns nothing: 3 fail.
* FR-4 — `environment_context=mcp_env` replaced by `""` in the generation handler, so the fetch
  succeeds and the prompt never carries it: 2 fail.

**FR-1 is deliberately not claimed here.** These tests hand the assembler a `TopologyContext`
directly; reading the `mcp_servers` block out of a `context.yaml` is a different step, and it stays
cited at unit tier until something drives it from a file.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from specweaver.assurance.graph.topology import TopologyContext
from specweaver.core.config.settings import LLMSettings, SpecWeaverSettings
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.generation import GenerateCodeHandler
from specweaver.core.flow.handlers.run_context import GraphContext, ModelAccess, RunContext


@pytest.fixture
def dummy_mcp_script(tmp_path: Path) -> str:
    """Creates a dummy python script mimicking an MCP server."""
    script_path = tmp_path / "dummy_mcp.py"
    script_content = """import sys, json

def main():
    while True:
        line = sys.stdin.readline()
        if not line: break
        try:
            req = json.loads(line)
            method = req.get("method")
            msg_id = req.get("id", 1)

            if method == "initialize":
                resp = {"jsonrpc": "2.0", "id": msg_id, "result": {"protocolVersion": "1.0", "capabilities": {}, "serverInfo": {"name": "dummy", "version": "1.0"}}}
            elif method == "resources/read":
                uri = req.get("params", {}).get("uri", "")
                resp = {"jsonrpc": "2.0", "id": msg_id, "result": {"contents": [{"uri": uri, "mimeType": "text/plain", "text": "e2e_db_schema_mock"}]}}
            else:
                resp = {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": "Method not found"}}

            sys.stdout.write(json.dumps(resp) + "\\n")
            sys.stdout.flush()
        except Exception:
            pass

if __name__ == "__main__":
    main()
"""
    script_path.write_text(script_content)
    return str(script_path)


@pytest.fixture(autouse=True)
def _allow_interpreter_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """The dummy MCP server is a Python script, and the boundary refuses a bare interpreter.

    That refusal is the fix for a real bypass: a `context.yaml` naming the exact interpreter path got
    arbitrary code while the boundary reported compliance. The seam is opened in test scope, where it
    takes in-process code execution to reach — which is exactly what a `context.yaml` does not have.

    A container would need an image, a registry and a network to prove the same chain, none of which
    belong in this test's cost.
    """
    monkeypatch.setattr("specweaver.sandbox.mcp.core.atom._ALLOW_INTERPRETER", True)


class TestMCPFlowE2E:
    @pytest.mark.asyncio
    @patch("specweaver.workflows.implementation.generator.Generator.generate_code")
    @patch("specweaver.sandbox.git.core.executor.GitExecutor.run")
    async def test_mcp_flow_e2e_fetch(
        self, mock_git, mock_generate_code, dummy_mcp_script: str, tmp_path: Path
    ) -> None:
        """Story: L3 SpecWeaver Flow CLI executes generate against a real MCP proxy."""
        # Arrange configuration and boundaries
        topology = TopologyContext(
            name="demo_node",
            purpose="DB.",
            archetype="pure-logic",
            relationship="self",
            mcp_servers={
                "dummy": {"command": [sys.executable], "args": [dummy_mcp_script]},
            },
            consumes_resources=["mcp://dummy/users_table"],
        )

        spec = tmp_path / "spec.md"
        spec.write_text("# Test Spec\\n")
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        from unittest.mock import MagicMock

        mock_db = MagicMock()
        import contextlib

        mock_db = MagicMock()

        @contextlib.asynccontextmanager
        async def mock_session_scope():
            yield AsyncMock()

        mock_db.async_session_scope = mock_session_scope

        ctx = RunContext(
            model=ModelAccess(
                llm=AsyncMock(), config=SpecWeaverSettings(llm=LLMSettings(model="gemini-test"))
            ),
            project_path=tmp_path,
            spec_path=spec,
            output_dir=src_dir,
            db=mock_db,
            graph=GraphContext(topology=topology),
        )
        ctx.run = ctx.run.model_copy(update={"run_id": "test-run"})

        mock_generate_code.return_value = tmp_path / "src" / "test.py"
        mock_git.return_value = (0, "", "")

        step = PipelineStep(name="gen", action=StepAction.GENERATE, target=StepTarget.CODE)
        handler = GenerateCodeHandler()

        # Act
        result = await handler.execute(step, ctx)

        # Assert
        assert result.status.name == "PASSED"
        mock_generate_code.assert_called_once()

        # Verify Generator payload correctly extracted the standard IO JSON-RPC envelope
        kwargs = mock_generate_code.call_args.kwargs
        assert "e2e_db_schema_mock" in kwargs.get("environment_context", "")
        assert "mcp://dummy/users_table:" in kwargs.get("environment_context", "")

    @pytest.mark.asyncio
    @patch("specweaver.workflows.review.reviewer.Reviewer.review_code")
    async def test_mcp_flow_e2e_review_code_fetch(
        self, mock_review_code, dummy_mcp_script: str, tmp_path: Path
    ) -> None:
        """Story: L3 SpecWeaver Flow CLI executes review code against a real MCP proxy."""
        topology = TopologyContext(
            name="demo_node",
            purpose="DB.",
            archetype="pure-logic",
            relationship="self",
            mcp_servers={
                "dummy": {"command": [sys.executable], "args": [dummy_mcp_script]},
            },
            consumes_resources=["mcp://dummy/users_table"],
        )

        spec = tmp_path / "spec.md"
        spec.write_text("# Test Spec\\n")

        ctx = RunContext(
            model=ModelAccess(
                llm=AsyncMock(), config=SpecWeaverSettings(llm=LLMSettings(model="gemini-test"))
            ),
            project_path=tmp_path,
            spec_path=spec,
            output_dir=tmp_path,
            graph=GraphContext(topology=topology),
        )
        ctx.run = ctx.run.model_copy(update={"run_id": "test-run"})
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        import contextlib

        @contextlib.asynccontextmanager
        async def mock_session_scope():
            yield AsyncMock()

        mock_db.async_session_scope = mock_session_scope
        ctx.db = mock_db
        (tmp_path / "test.py").write_text("x = 1")

        from specweaver.core.flow.handlers.review import ReviewCodeHandler
        from specweaver.workflows.review.reviewer import ReviewResult, ReviewVerdict

        mock_review_code.return_value = ReviewResult(
            verdict=ReviewVerdict.ACCEPTED,
            remarks="LGTM",
            findings=[],
        )

        step = PipelineStep(name="rev", action=StepAction.REVIEW, target=StepTarget.CODE)
        handler = ReviewCodeHandler()

        # Act
        result = await handler.execute(step, ctx)

        # Assert
        assert result.status.name == "PASSED"
        mock_review_code.assert_called_once()

        kwargs = mock_review_code.call_args.kwargs
        env_ctx = kwargs.get("environment_context", "")
        assert "e2e_db_schema_mock" in env_ctx
        assert "mcp://dummy/users_table:" in env_ctx

    @pytest.mark.asyncio
    @patch("specweaver.workflows.implementation.generator.Generator.generate_code")
    @patch("specweaver.sandbox.git.core.executor.GitExecutor.run")
    async def test_mcp_flow_e2e_fault_tolerance(
        self, mock_git, mock_generate_code, tmp_path: Path
    ) -> None:
        """Story: Subprocess crash during MCP Fetching injects formatted error string into Context silently."""
        crash_script = tmp_path / "crash_mcp.py"
        crash_script.write_text("import sys; sys.exit(1)\\n")

        topology = TopologyContext(
            name="demo_node",
            purpose="DB.",
            archetype="pure-logic",
            relationship="self",
            mcp_servers={
                "dummy": {"command": [sys.executable], "args": [str(crash_script)]},
            },
            consumes_resources=["mcp://dummy/users_table"],
        )

        spec = tmp_path / "spec.md"
        spec.write_text("# Test Spec\\n")

        ctx = RunContext(
            model=ModelAccess(
                llm=AsyncMock(), config=SpecWeaverSettings(llm=LLMSettings(model="gemini-test"))
            ),
            project_path=tmp_path,
            spec_path=spec,
            output_dir=tmp_path,
            graph=GraphContext(topology=topology),
        )
        ctx.run = ctx.run.model_copy(update={"run_id": "test-run"})
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        import contextlib

        @contextlib.asynccontextmanager
        async def mock_session_scope():
            yield AsyncMock()

        mock_db.async_session_scope = mock_session_scope
        ctx.db = mock_db
        (tmp_path / "test.py").write_text("x = 1")

        mock_generate_code.return_value = tmp_path / "src" / "test.py"
        mock_git.return_value = (0, "", "")

        step = PipelineStep(name="gen", action=StepAction.GENERATE, target=StepTarget.CODE)
        handler = GenerateCodeHandler()

        # Act
        result = await handler.execute(step, ctx)

        # Assert
        assert result.status.name == "PASSED"
        mock_generate_code.assert_called_once()

        kwargs = mock_generate_code.call_args.kwargs
        env_ctx = kwargs.get("environment_context", "")
        assert "ERROR init resource" in env_ctx

    @pytest.mark.asyncio
    async def test_mcp_flow_e2e_tool_dispatcher_architect(
        self, dummy_mcp_script: str, tmp_path: Path
    ) -> None:
        """Story: E2E Tool Flow: Architect agent invokes ToolDispatcher which calls the proxy."""
        import sys

        from specweaver.sandbox.dispatcher import ToolDispatcher
        from specweaver.sandbox.security import WorkspaceBoundary

        topology = TopologyContext(
            name="demo_node",
            purpose="DB.",
            archetype="pure-logic",
            relationship="self",
            mcp_servers={
                "dummy": {"command": [sys.executable], "args": [dummy_mcp_script]},
            },
            consumes_resources=["mcp://dummy/users_table"],
        )
        boundary = WorkspaceBoundary(roots=[tmp_path], api_paths=[tmp_path])

        dispatcher = ToolDispatcher.create_standard_set(
            boundary=boundary, role="architect", allowed_tools=["mcp"], topology=topology
        )

        # Test tool registry execution
        result_list = await dispatcher.execute("list_resources", {"server_name": "dummy"})
        assert "result" in result_list
        result_list["result"]

        # The dummy returns NO contents during list, but in our dummy it doesn't even implement list
        # Actually our dummy proxy returns Method not found for anything besides read/initialize!
        # Wait, the dummy script in test_mcp_flow_e2e.py returns:
        # else: resp = {"error": "Method not found"}
        # So "list_resources" will return error.

        result_read = await dispatcher.execute(
            "read_resource", {"server_name": "dummy", "uri": "mcp://dummy/users_table"}
        )
        assert "result" in result_read
        assert "e2e_db_schema_mock" in result_read["result"]
