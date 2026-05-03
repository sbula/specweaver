import logging
from pathlib import Path
from typing import Any

from specweaver.workspace.ast.parsers.factory import get_default_parsers

logger = logging.getLogger(__name__)


def extract_ast_dict(filepath: str) -> dict[str, Any]:
    """
    Adapter that wraps the polyglot Tree-Sitter parsers to output
    the universal AST dictionary expected by the OntologyMapper.
    """
    logger.debug("extract_ast_dict called for %s", filepath)
    ast_data: dict[str, Any] = {"type": "module", "children": []}

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
        return ast_data

    try:
        symbols = parser.list_symbols(code)
        markers = parser.extract_framework_markers(code)
    except Exception:
        logger.exception("extract_ast_dict: Parser failed on %s", filepath)
        return ast_data

    for symbol in symbols:
        # If 'extends' is present, the parser identified it as a class
        is_class = "extends" in markers.get(symbol, {})
        node_type = "class_definition" if is_class else "function_definition"
        ast_data["children"].append({"type": node_type, "name": symbol})

    return ast_data
