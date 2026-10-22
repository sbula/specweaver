# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import logging
from pathlib import Path
from typing import Any

from specweaver.sandbox.base import Atom, AtomResult, AtomStatus
from specweaver.sandbox.protocol.core.factory import ProtocolParserFactory
from specweaver.sandbox.protocol.core.protocol_interfaces import ProtocolSchemaError
from specweaver.sandbox.security import WorkspaceBoundary, WorkspaceBoundaryError

logger = logging.getLogger(__name__)


class ProtocolAtom(Atom):
    """
    Atom for extracting data from Protocol files natively (YAML/Protobuf).

    Reads only files its boundary accepts; a relative path is read from the boundary's root.
    """

    def __init__(self, boundary: WorkspaceBoundary) -> None:
        self._boundary = boundary

    def _read_file(self, path: Path, given: str) -> str:
        """Read a checked path; errors name the path as the caller gave it."""
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {given}")
        return path.read_text(encoding="utf-8")

    def run(self, context: dict[str, Any]) -> AtomResult:
        """
        Executes a protocol parsing intent against a file layout.

        Expected context keys:
        - action: 'extract_schema_endpoints' | 'extract_schema_messages'
        - file_path: Path to the schema file
        """
        action = context.get("action")
        file_path = context.get("file_path")

        if not action or not file_path:
            return AtomResult(
                status=AtomStatus.FAILED, message="Missing 'action' or 'file_path' in context"
            )

        try:
            inside = self._boundary.validate_path(Path(file_path))
            payload = self._read_file(inside, file_path)
            parser = ProtocolParserFactory.create_parser(payload)

            if action == "extract_schema_endpoints":
                endpoints = parser.extract_endpoints(payload)
                return AtomResult(
                    status=AtomStatus.SUCCESS,
                    message="Extracted endpoints successfully",
                    exports={"status": "success", "data": [e.model_dump() for e in endpoints]},
                )
            elif action == "extract_schema_messages":
                messages = parser.extract_messages(payload)
                return AtomResult(
                    status=AtomStatus.SUCCESS,
                    message="Extracted messages successfully",
                    exports={"status": "success", "data": [m.model_dump() for m in messages]},
                )
            else:
                return AtomResult(
                    status=AtomStatus.FAILED,
                    message=f"Unknown intent: {action}",
                    exports={"status": "error", "error": f"Unknown intent: {action}"},
                )

        except ProtocolSchemaError as e:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=str(e),
                exports={"status": "error", "error": str(e)},
            )
        except WorkspaceBoundaryError:  # expected: the result says the path is outside
            # The boundary's own message holds the resolved path; answer with the input only.
            msg = f"Path is outside the workspace: {file_path}"
            return AtomResult(
                status=AtomStatus.FAILED,
                message=msg,
                exports={"status": "error", "error": msg},
            )
        except FileNotFoundError as e:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=str(e),
                exports={"status": "error", "error": str(e)},
            )
        except Exception as e:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"Unexpected error during protocol extraction: {e}",
                exports={
                    "status": "error",
                    "error": f"Unexpected error during protocol extraction: {e}",
                },
            )
