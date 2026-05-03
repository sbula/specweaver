from specweaver.core.loom.atoms.base import AtomStatus
from specweaver.core.loom.atoms.protocol.atom import ProtocolAtom


def test_atom_missing_context_keys():
    """Story 1: Atom fails predictably when action or file_path is missing."""
    atom = ProtocolAtom()
    result = atom.run(context={"action": "extract_schema_endpoints"})  # missing file_path
    assert result.status == AtomStatus.FAILED
    assert "Missing" in result.message

    result2 = atom.run(context={"file_path": "dummy.yaml"})  # missing action
    assert result2.status == AtomStatus.FAILED
    assert "Missing" in result2.message


def test_atom_generic_exception(monkeypatch):
    """Story 2: Atom gracefully catches generic, completely unexpected exceptions."""

    def mock_read_file(*args, **kwargs):
        raise ValueError("Kaboom!")

    monkeypatch.setattr(
        "specweaver.core.loom.atoms.protocol.atom.ProtocolAtom._read_file", mock_read_file
    )
    atom = ProtocolAtom()
    result = atom.run(context={"action": "extract_schema_endpoints", "file_path": "dummy.yaml"})

    assert result.status == AtomStatus.FAILED
    assert "Unexpected error during protocol extraction: Kaboom!" in result.message
    assert result.exports["status"] == "error"
    assert "Kaboom!" in result.exports["error"]
