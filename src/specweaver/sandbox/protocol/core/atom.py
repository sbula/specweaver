from pathlib import Path
from typing import Any

from specweaver.sandbox.base import Atom, AtomResult, AtomStatus
from specweaver.sandbox.protocol.core.factory import ProtocolParserFactory
from specweaver.sandbox.protocol.core.protocol_interfaces import ProtocolSchemaError


class ProtocolAtom(Atom):
    """
    Atom for extracting data from Protocol files natively (YAML/Protobuf).
    """

    def _read_file(self, file_path: str) -> str:
        """Helper to read files safely."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
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
            payload = self._read_file(file_path)
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
