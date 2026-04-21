# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""E2E flow engine integrations testing the Pre-fetch Context Assembler (SF-3)."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from specweaver.assurance.graph.topology import TopologyContext
from specweaver.core.config.settings import LLMSettings, SpecWeaverSettings
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.generation import GenerateCodeHandler


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


class TestMCPFlowE2E:
    @pytest.mark.asyncio
    @patch("specweaver.workflows.implementation.generator.Generator.generate_code")
    @patch("specweaver.core.loom.commons.git.executor.GitExecutor.run")
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

        ctx = RunContext(
            project_path=tmp_path,
            spec_path=spec,
            topology=topology,
            llm=AsyncMock(),
            output_dir=src_dir,
            config=SpecWeaverSettings(llm=LLMSettings(model="gemini-test")),
        )
        ctx.run_id = "test-run"
        ctx.db = AsyncMock()

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
            project_path=tmp_path,
            spec_path=spec,
            topology=topology,
            llm=AsyncMock(),
            config=SpecWeaverSettings(llm=LLMSettings(model="gemini-test")),
            output_dir=tmp_path,
        )
        ctx.run_id = "test-run"
        ctx.db = AsyncMock()
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
    @patch("specweaver.core.loom.commons.git.executor.GitExecutor.run")
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
            project_path=tmp_path,
            spec_path=spec,
            topology=topology,
            llm=AsyncMock(),
            config=SpecWeaverSettings(llm=LLMSettings(model="gemini-test")),
            output_dir=tmp_path,
        )
        ctx.run_id = "test-run"
        ctx.db = AsyncMock()
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
