from __future__ import annotations

from specweaver.llm.models import ToolDefinition, ToolParameter

INTENT_DEFINITIONS: dict[str, ToolDefinition] = {
    "role": ToolDefinition(
        name="role",
        description="The agent's role.",
    ),
    "allowed_intents": ToolDefinition(
        name="allowed_intents",
        description="Intents available for this role.",
    ),
    "commit": ToolDefinition(
        name="commit",
        description="Stage all changes and commit with a conventional commit message.",
        parameters=[ToolParameter(name="message", type="string", description="message")],
    ),
    "inspect_changes": ToolDefinition(
        name="inspect_changes",
        description="Show current status and diff.",
    ),
    "discard": ToolDefinition(
        name="discard",
        description="Discard working tree changes for a specific file.",
        parameters=[ToolParameter(name="file", type="string", description="file")],
    ),
    "uncommit": ToolDefinition(
        name="uncommit",
        description="Undo the last commit, keeping changes staged.",
    ),
    "start_branch": ToolDefinition(
        name="start_branch",
        description="Create and switch to a new branch with enforced naming.",
        parameters=[ToolParameter(name="name", type="string", description="name")],
    ),
    "switch_branch": ToolDefinition(
        name="switch_branch",
        description="Switch to an existing branch with auto-stash.",
        parameters=[ToolParameter(name="name", type="string", description="name")],
    ),
    "history": ToolDefinition(
        name="history",
        description="Show recent commit history.",
        parameters=[ToolParameter(name="n", type="string", description="n")],
    ),
    "show_commit": ToolDefinition(
        name="show_commit",
        description="Show the contents of a specific commit.",
        parameters=[ToolParameter(name="commit_hash", type="string", description="commit_hash")],
    ),
    "blame": ToolDefinition(
        name="blame",
        description="Show line-by-line authorship of a file.",
        parameters=[ToolParameter(name="file", type="string", description="file")],
    ),
    "compare": ToolDefinition(
        name="compare",
        description="Compare two branches or commits.",
        parameters=[
            ToolParameter(name="base", type="string", description="base"),
            ToolParameter(name="head", type="string", description="head"),
        ],
    ),
    "list_branches": ToolDefinition(
        name="list_branches",
        description="List all branches.",
    ),
    "file_history": ToolDefinition(
        name="file_history",
        description="Show recent commits that touched a specific file.",
        parameters=[
            ToolParameter(name="file", type="string", description="file"),
            ToolParameter(name="n", type="string", description="n"),
        ],
    ),
    "show_old": ToolDefinition(
        name="show_old",
        description="Show a previous version of a file.",
        parameters=[
            ToolParameter(name="file", type="string", description="file"),
            ToolParameter(name="rev", type="string", description="rev"),
        ],
    ),
    "search_history": ToolDefinition(
        name="search_history",
        description="Find commits where a text string was added or removed.",
        parameters=[ToolParameter(name="text", type="string", description="text")],
    ),
    "reflog": ToolDefinition(
        name="reflog",
        description="Show the reflog (recovery history).",
        parameters=[ToolParameter(name="n", type="string", description="n")],
    ),
    "list_conflicts": ToolDefinition(
        name="list_conflicts",
        description="List files with merge conflicts.",
    ),
    "show_conflict": ToolDefinition(
        name="show_conflict",
        description="Show conflict markers for a specific file.",
        parameters=[ToolParameter(name="file", type="string", description="file")],
    ),
    "mark_resolved": ToolDefinition(
        name="mark_resolved",
        description="Stage a resolved file during conflict resolution.",
        parameters=[ToolParameter(name="file", type="string", description="file")],
    ),
    "abort_merge": ToolDefinition(
        name="abort_merge",
        description="Abort the current merge and restore clean state.",
    ),
    "complete_merge": ToolDefinition(
        name="complete_merge",
        description="Complete the merge after all conflicts are resolved.",
    ),
}
