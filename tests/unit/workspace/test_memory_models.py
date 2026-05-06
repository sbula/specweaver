import pytest
from pydantic import ValidationError

from specweaver.workspace.memory.models import HandoverContext


def test_handover_context_model_defaults() -> None:
    """M-1: Default empty lists and None fields"""
    ctx = HandoverContext()
    assert ctx.files_touched == []
    assert ctx.errors_encountered == []
    assert ctx.stack_trace is None
    assert ctx.summary is None
    assert ctx.metadata == {}


def test_handover_context_model_full() -> None:
    """M-2: All fields populated correctly"""
    ctx = HandoverContext(
        files_touched=["foo.py"],
        errors_encountered=["ImportError"],
        stack_trace="Traceback...",
        summary="Working on it",
        metadata={"attempts": 1, "retry": True, "worker": "agent-1", "score": 0.95}
    )
    assert ctx.files_touched == ["foo.py"]
    assert ctx.errors_encountered == ["ImportError"]
    assert ctx.stack_trace == "Traceback..."
    assert ctx.summary == "Working on it"
    assert ctx.metadata == {"attempts": 1, "retry": True, "worker": "agent-1", "score": 0.95}


def test_handover_context_to_json_str() -> None:
    """M-3: Serialization produces valid JSON without None values"""
    ctx = HandoverContext(files_touched=["foo.py"], summary="Done")
    json_str = ctx.to_json_str()
    # It should not contain 'stack_trace' or 'errors_encountered' keys if we use exclude_none?
    # Wait, errors_encountered is a list, so it's not None, it will be included.
    # stack_trace is None, so it should be excluded.
    assert "foo.py" in json_str
    assert "Done" in json_str
    assert "stack_trace" not in json_str


def test_handover_context_from_json_str() -> None:
    """M-4: Deserialization roundtrip"""
    original = HandoverContext(files_touched=["foo.py"])
    json_str = original.to_json_str()
    restored = HandoverContext.from_json_str(json_str)
    assert restored.files_touched == ["foo.py"]
    assert restored.metadata == {}


def test_handover_context_truncation() -> None:
    """M-5: Stack trace exactly 2000 chars, and 2001 chars truncated to last 2000"""
    exact_2000 = "x" * 2000
    ctx1 = HandoverContext(stack_trace=exact_2000)
    assert len(ctx1.stack_trace) == 2000

    over_2000 = "A" + "B" * 2000
    ctx2 = HandoverContext(stack_trace=over_2000)
    assert len(ctx2.stack_trace) == 2000
    assert ctx2.stack_trace == "B" * 2000
    assert ctx2.stack_trace[0] == "B"


def test_handover_context_size_limit_exceeded() -> None:
    """M-6: to_json_str raises ValueError for oversized context > 8192 bytes"""
    # Create a string that pushes the JSON representation over 8192 bytes
    large_summary = "x" * 8000
    ctx = HandoverContext(summary=large_summary[:2000], metadata={"large": "x" * 7000})
    with pytest.raises(ValueError, match="Serialized handover context exceeds 8192 byte limit"):
        ctx.to_json_str()


def test_handover_context_metadata_primitives_only() -> None:
    """M-7: Dict values must be primitives or flat lists; nested dicts/objects rejected"""
    # Valid primitives
    HandoverContext(metadata={"a": 1, "b": "str", "c": True, "d": 1.5, "e": ["a", "b", 1]})

    # Invalid: nested dict
    with pytest.raises(ValidationError, match="must be a primitive"):
        HandoverContext(metadata={"nested": {"foo": "bar"}})

    # Invalid: list with non-primitive
    with pytest.raises(ValidationError, match="contains a list with non-primitive elements"):
        HandoverContext(metadata={"nested_list": [{"foo": "bar"}]})


def test_handover_context_exclude_none_roundtrip() -> None:
    """M-8: to_json_str(exclude_none=True) -> from_json_str() preserves model equality"""
    ctx = HandoverContext(files_touched=["a.txt"])
    # stack_trace and summary are None
    json_str = ctx.to_json_str()
    restored = HandoverContext.from_json_str(json_str)
    assert restored == ctx
    assert restored.stack_trace is None
    assert restored.summary is None


def test_handover_context_from_json_str_malformed() -> None:
    """[Hostile/Wrong Input] from_json_str correctly rejects completely malformed JSON strings."""
    with pytest.raises(ValidationError):
        HandoverContext.from_json_str("{malformed json")


def test_handover_context_from_json_str_type_violation() -> None:
    """[Hostile/Wrong Input] from_json_str rejects JSON payloads with strict type violations."""
    # files_touched expects a list of strings, providing an int will fail validation
    invalid_json = '{"files_touched": 42}'
    with pytest.raises(ValidationError):
        HandoverContext.from_json_str(invalid_json)


def test_handover_context_truncate_empty_string() -> None:
    """[Boundary/Edge Case] truncate_stack_trace correctly handles empty strings without error."""
    ctx = HandoverContext(stack_trace="")
    assert ctx.stack_trace == ""

