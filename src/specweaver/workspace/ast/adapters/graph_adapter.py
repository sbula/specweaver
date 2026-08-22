# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import logging
from pathlib import Path
from typing import Any

from specweaver.workspace.ast.parsers.factory import get_default_parsers

logger = logging.getLogger(__name__)


def parseable_suffixes() -> frozenset[str]:
    """Every file suffix `extract_ast_dict` can resolve a parser for.

    Lives beside the resolution it describes, so a caller deciding WHICH files to hand over and this
    function deciding what to do with one cannot disagree. `GraphBuilder.collect_files` accepted
    `.py` and nothing else while this resolved parsers for ten suffix groups, and a Java file was
    dropped before the mapper ever saw it.

    Exposed here rather than from the parser registry because `specweaver.graph` may depend on this
    adapter and not on `workspace.ast.parsers` — the boundary is the reason the two ended up
    restating each other.
    """
    return frozenset(suffix for group in get_default_parsers() for suffix in group)


def _supertype_records(by_kind: dict[str, list[str]]) -> list[dict[str, str]]:
    """Flatten `{"extends": [...], "implements": [...]}` into records the mapper can walk.

    A list rather than the mapping the parser returns, because `SF-02` declared this field as a list
    and changing a declared empty value's type is a reshape however small it looks. Records also
    carry a third kind later without moving anything again.
    """
    return [
        {"name": name, "kind": kind}
        for kind in ("extends", "implements")
        for name in by_kind.get(kind, [])
    ]


def extract_ast_dict(filepath: str) -> dict[str, Any]:
    """
    Adapter that wraps the polyglot Tree-Sitter parsers to output
    the universal AST dictionary expected by the OntologyMapper.
    """
    logger.debug("extract_ast_dict called for %s", filepath)
    # The seam declares every dependency kind the mapper will ever need, populated or not, so a
    # later sub-feature fills a field rather than reshaping the payload and forcing its siblings to
    # follow. An absent key and an empty one must not mean the same thing to a reader.
    ast_data: dict[str, Any] = {"type": "module", "imports": [], "calls": [], "children": []}

    path = Path(filepath)
    if not path.exists():
        logger.warning("extract_ast_dict: Path does not exist: %s", filepath)
        return ast_data

    if path.is_symlink():
        logger.debug("extract_ast_dict: Skipping symlink: %s", filepath)
        return ast_data

    ext = path.suffix
    parsers = get_default_parsers()

    # Find the matching parser for the extension
    parser = None
    for exts, p in parsers.items():
        if ext in exts:
            parser = p
            break

    if not parser:
        logger.debug("extract_ast_dict: No parser found for extension %s", ext)
        return ast_data

    try:
        code = path.read_text(encoding="utf-8")
    except Exception:
        logger.exception("extract_ast_dict: Failed to read file %s", filepath)
        # A flag, not a collection: its ABSENCE is the ordinary case, so it is set only on a real
        # failure. A warning in a log is invisible to a graph reader and unreadable to a human
        # across thousands of files, which is how "could not open" and "nothing in it" became the
        # same answer.
        ast_data["unparsed"] = "read"
        return ast_data

    try:
        symbols = parser.list_symbols(code)
        markers = parser.extract_framework_markers(code)
        ast_data["imports"] = parser.extract_imports(code)
        supertypes = parser.extract_supertypes(code)
        call_sites = parser.extract_call_sites(code)
        # Module-level code has no enclosing declaration, so no child owns it. The file does — the
        # same reason `imports` sits here rather than on a child.
        ast_data["calls"] = call_sites.get("", [])
    except Exception:
        logger.exception("extract_ast_dict: Parser failed on %s", filepath)
        ast_data["unparsed"] = "parse"
        return ast_data

    for symbol in symbols:
        # If 'extends' is present, the parser identified it as a class
        is_class = "extends" in markers.get(symbol, {})
        node_type = "class_definition" if is_class else "function_definition"
        ast_data["children"].append(
            {
                "type": node_type,
                "name": symbol,
                "supertypes": _supertype_records(supertypes.get(symbol, {})),
                "calls": call_sites.get(symbol, []),
            }
        )

    return ast_data
