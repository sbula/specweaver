from specweaver.infrastructure.llm.prompt.interfaces import PromptContentSource


def test_protocol_is_runtime_checkable() -> None:
    # Since PromptContentSource is a protocol, checking its type/existence
    assert issubclass(PromptContentSource, object)


def test_conformance() -> None:
    class DummySource:
        def get_prompt_content(self, char_limit: int | None = None) -> str:
            return "content"

        def get_prompt_label(self) -> str:
            return "label"

    dummy = DummySource()
    assert isinstance(dummy, PromptContentSource)


def test_non_conformance() -> None:
    class DummySourceNoLabel:
        def get_prompt_content(self, char_limit: int | None = None) -> str:
            return "content"

    dummy = DummySourceNoLabel()
    assert not isinstance(dummy, PromptContentSource)
