# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tool executor — dispatches LLM tool calls to implementations.

Provider-agnostic: accepts (name, args) pairs. Each LLM adapter
extracts (name, args) from its provider's response format.

Uses a registry pattern instead of if/elif chains.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specweaver.llm.models import ToolDefinition
    from specweaver.loom.commons.research.boundaries import WorkspaceBoundary

from specweaver.loom.commons.research.definitions import FILE_TOOLS, WEB_TOOLS

logger = logging.getLogger(__name__)

# Type alias for tool handler functions
ToolHandler = Callable[..., dict[str, Any]]


class ToolExecutor:
    """Dispatches tool calls from the LLM to tool implementations.

    Provider-agnostic: accepts (name, args) pairs, not provider-specific types.
    Each adapter extracts (name, args) from its provider's response format.

    Args:
        boundary: WorkspaceBoundary for path validation.
        web_enabled: Whether web tools are available.
    """

    def __init__(
        self,
        boundary: WorkspaceBoundary,
        *,
        web_enabled: bool = False,
    ) -> None:
        self.boundary = boundary
        self.web_enabled = web_enabled
        self._root = boundary.roots[0]  # Primary root for tool invocations
        self._handlers: dict[str, ToolHandler] = self._build_registry()

    def _build_registry(self) -> dict[str, ToolHandler]:
        """Build the tool name → handler function mapping."""
        registry: dict[str, ToolHandler] = {
            "grep": self._handle_grep,
            "find_files": self._handle_find_files,
            "read_file": self._handle_read_file,
            "list_directory": self._handle_list_directory,
        }
        if self.web_enabled:
            registry["web_search"] = self._handle_web_search
            registry["read_url"] = self._handle_read_url
        return registry

    async def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a single tool call by name with arguments.

        Args:
            name: Tool function name (e.g., 'grep', 'read_file').
            args: Tool arguments as a dict.

        Returns:
            Tool result as a dict (or error dict on failure).
        """
        logger.debug("Tool call: %s(%s)", name, args)

        handler = self._handlers.get(name)
        if handler is None:
            return {"error": f"Unknown tool: {name}"}

        try:
            return handler(args)
        except Exception as exc:
            logger.warning("Tool %s failed: %s", name, exc)
            return {"error": f"Tool execution failed: {exc}"}

    def available_tools(self) -> list[ToolDefinition]:
        """Return tool definitions for tools available in this executor.

        Excludes web tools if web_enabled=False.
        """
        tools = list(FILE_TOOLS)
        if self.web_enabled:
            tools.extend(WEB_TOOLS)
        return tools

    # ----- File tool handlers -----

    def _handle_grep(self, args: dict[str, Any]) -> dict[str, Any]:
        from specweaver.loom.commons.filesystem.search import grep_content

        search_dir = (self._root / args.get("path", ".")).resolve()
        return {"results": grep_content(
            search_dir,
            args["pattern"],
            context_lines=args.get("context_lines", 3),
            case_sensitive=args.get("case_sensitive", False),
            max_results=args.get("max_results", 20),
        )}

    def _handle_find_files(self, args: dict[str, Any]) -> dict[str, Any]:
        from specweaver.loom.commons.filesystem.search import find_by_glob

        search_dir = (self._root / args.get("path", ".")).resolve()
        return {"results": find_by_glob(
            search_dir,
            args["pattern"],
            file_type=args.get("type", "any"),
            max_results=args.get("max_results", 30),
        )}

    def _handle_read_file(self, args: dict[str, Any]) -> dict[str, Any]:
        from specweaver.loom.commons.filesystem.search import READ_FILE_LINE_CAP

        file_path = (self._root / args["path"]).resolve()
        if not file_path.is_file():
            return {"error": f"File not found: {args['path']}"}

        try:
            all_lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            return {"error": str(exc)}

        total_lines = len(all_lines)
        start = (args.get("start_line") or 1) - 1
        end = args.get("end_line") or total_lines
        start = max(0, start)
        end = min(total_lines, end)

        truncated = False
        if (end - start) > READ_FILE_LINE_CAP:
            end = start + READ_FILE_LINE_CAP
            truncated = True

        content = "\n".join(all_lines[start:end])
        result: dict[str, Any] = {
            "path": args["path"],
            "content": content,
            "total_lines": total_lines,
            "showing_lines": f"{start + 1}-{end}",
        }
        if truncated:
            result["truncated"] = True
            result["warning"] = (
                f"Capped at {READ_FILE_LINE_CAP} lines. "
                "Call again with different start_line/end_line to read more."
            )
        return result

    def _handle_list_directory(self, args: dict[str, Any]) -> dict[str, Any]:
        target = (self._root / args.get("path", ".")).resolve()
        if not target.is_dir():
            return {"error": f"Not a directory: {args.get('path', '.')}"}

        depth = args.get("depth", 2)
        max_entries = args.get("max_entries", 50)
        count = 0

        def _walk(dir_path: Any, current_depth: int) -> list[dict[str, Any]]:
            nonlocal count
            items: list[dict[str, Any]] = []
            if current_depth > depth:
                return items
            try:
                children = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
            except OSError:
                return items
            for child in children:
                if count >= max_entries:
                    items.append({"truncated": True, "warning": f"Limited to {max_entries} entries"})
                    return items
                if child.name.startswith(".") or child.name == "__pycache__":
                    continue
                try:
                    rel = str(child.relative_to(target))
                except ValueError:
                    rel = child.name
                entry: dict[str, Any] = {
                    "path": rel,
                    "type": "directory" if child.is_dir() else "file",
                }
                count += 1
                if child.is_dir() and current_depth < depth:
                    entry["children"] = _walk(child, current_depth + 1)
                items.append(entry)
            return items

        tree = _walk(target, 1)
        return {"path": args.get("path", "."), "type": "directory", "children": tree}

    # ----- Web tool handlers -----

    def _handle_web_search(self, args: dict[str, Any]) -> dict[str, Any]:
        from specweaver.loom.tools.web.tool import WebTool

        api_key = os.environ.get("SEARCH_API_KEY", "")
        engine_id = os.environ.get("SEARCH_ENGINE_ID", "")
        tool = WebTool(role="planner", api_key=api_key, engine_id=engine_id)
        result = tool.web_search(
            args["query"],
            max_results=args.get("max_results", 5),
        )
        if result.status == "success":
            return {"results": result.data}
        return {"error": result.message}

    def _handle_read_url(self, args: dict[str, Any]) -> dict[str, Any]:
        from specweaver.loom.tools.web.tool import WebTool

        api_key = os.environ.get("SEARCH_API_KEY", "")
        engine_id = os.environ.get("SEARCH_ENGINE_ID", "")
        tool = WebTool(role="planner", api_key=api_key, engine_id=engine_id)
        result = tool.read_url(
            args["url"],
            max_chars=args.get("max_chars", 10000),
        )
        if result.status == "success":
            return dict(result.data)
        return {"error": result.message}
