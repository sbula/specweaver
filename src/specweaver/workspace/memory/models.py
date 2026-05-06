"""Agent Memory Bank — Pydantic validation models.

Defines HandoverContext for strict JSON schema validation
of the handover_context field (NFR-5, NFR-6).
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator

_MAX_CONTEXT_BYTES = 8192  # 8KB hard limit (NFR-6)
_MAX_STACK_TRACE_CHARS = 2000  # Truncation limit for stack traces
_ALLOWED_PRIMITIVE_TYPES = (str, int, float, bool)


class HandoverContext(BaseModel):
    """Strict schema for task handover context.

    Bounded to factual telemetry to prevent hallucination transfer (NFR-5).
    Total serialized size must not exceed 8KB (NFR-6).
    """

    files_touched: list[str] = Field(
        default_factory=list, description="Files modified during this task"
    )
    errors_encountered: list[str] = Field(
        default_factory=list, description="Error messages hit during execution"
    )
    stack_trace: str | None = Field(
        default=None, description="Last stack trace, truncated to 2000 chars"
    )
    summary: str | None = Field(
        default=None, max_length=2000, description="Free-form summary of progress"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional key-value telemetry"
    )

    @field_validator("stack_trace", mode="after")
    @classmethod
    def truncate_stack_trace(cls, v: str | None) -> str | None:
        """Truncate stack traces to last 2000 characters (NFR-6)."""
        if v is not None and len(v) > _MAX_STACK_TRACE_CHARS:
            return v[-_MAX_STACK_TRACE_CHARS:]
        return v

    @field_validator("metadata", mode="after")
    @classmethod
    def validate_metadata_primitives(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Reject non-primitive values to prevent deeply nested hallucination payloads."""
        for key, val in v.items():
            if isinstance(val, list):
                if not all(isinstance(item, _ALLOWED_PRIMITIVE_TYPES) for item in val):
                    raise ValueError(
                        f"metadata['{key}'] contains a list with non-primitive elements"
                    )
            elif not isinstance(val, _ALLOWED_PRIMITIVE_TYPES):
                raise ValueError(
                    f"metadata['{key}'] must be a primitive (str, int, float, bool) "
                    f"or a flat list of primitives, got {type(val).__name__}"
                )
        return v

    def to_json_str(self) -> str:
        """Serialize to JSON string, enforcing 8KB limit and stripping None values.

        Raises:
            ValueError: If serialized context exceeds 8KB.
        """
        serialized = self.model_dump_json(exclude_none=True)
        if len(serialized.encode("utf-8")) > _MAX_CONTEXT_BYTES:
            raise ValueError(
                f"Serialized handover context exceeds {_MAX_CONTEXT_BYTES} byte limit "
                f"({len(serialized.encode('utf-8'))} bytes)"
            )
        return serialized

    @classmethod
    def from_json_str(cls, json_str: str) -> "HandoverContext":
        """Deserialize from JSON string with validation."""
        return cls.model_validate_json(json_str)
