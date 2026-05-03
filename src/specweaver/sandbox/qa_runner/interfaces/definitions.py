from __future__ import annotations

from specweaver.infrastructure.llm.models import ToolDefinition, ToolParameter

INTENT_DEFINITIONS: dict[str, ToolDefinition] = {
    "role": ToolDefinition(
        name="role",
        description="The agent's role.",
    ),
    "run_tests": ToolDefinition(
        name="run_tests",
        description="Run tests (requires run_tests intent).",
        parameters=[
            ToolParameter(name="target", type="string", description="target"),
            ToolParameter(name="kind", type="string", description="kind"),
            ToolParameter(name="scope", type="string", description="scope"),
            ToolParameter(name="timeout", type="string", description="timeout"),
            ToolParameter(name="coverage", type="string", description="coverage"),
        ],
    ),
    "run_linter": ToolDefinition(
        name="run_linter",
        description="Run linter (requires run_linter; fix=True requires run_linter_fix).",
        parameters=[
            ToolParameter(name="target", type="string", description="target"),
            ToolParameter(name="fix", type="string", description="fix"),
        ],
    ),
    "run_complexity": ToolDefinition(
        name="run_complexity",
        description="Run complexity checks (requires run_complexity intent).",
        parameters=[
            ToolParameter(name="target", type="string", description="target"),
            ToolParameter(name="max_complexity", type="string", description="max_complexity"),
        ],
    ),
    "run_architecture": ToolDefinition(
        name="run_architecture",
        description="Run architectural boundary checks (requires run_architecture intent).",
        parameters=[
            ToolParameter(name="target", type="string", description="target"),
        ],
    ),
}
