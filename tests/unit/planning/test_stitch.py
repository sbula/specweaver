# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.


from specweaver.planning.stitch import StitchClient


def test_stitch_client_without_api_key(monkeypatch):
    monkeypatch.delenv("STITCH_API_KEY", raising=False)
    client = StitchClient(api_key=None)
    assert not client.is_available()

    result = client.generate_mockup("Some UI")
    assert len(result.references) == 0


def test_stitch_client_with_api_key():
    client = StitchClient(api_key="fake-key")
    assert client.is_available()

    result = client.generate_mockup("Create a nice dashboard")
    assert len(result.references) == 1
    assert result.references[0].screen_name == "Generated UI"
    assert "placeholder" in result.references[0].preview_url


def test_stitch_client_without_api_key_logs_warning(monkeypatch, caplog):
    monkeypatch.delenv("STITCH_API_KEY", raising=False)
    client = StitchClient(api_key=None)
    with caplog.at_level("WARNING"):
        client.generate_mockup("Some UI")
    assert "Stitch SDK missing or STITCH_API_KEY not configured" in caplog.text


def test_stitch_client_generate_mockup_exception(monkeypatch, caplog):
    client = StitchClient(api_key="fake-key")

    # Force MockupResult creation to fail to simulate exception
    import specweaver.planning.models
    def raise_err(*args, **kwargs):
        raise ValueError("Simulated network error")
    monkeypatch.setattr(specweaver.planning.models, "MockupReference", raise_err)

    with caplog.at_level("WARNING"):
        result = client.generate_mockup("UI")

    assert "Stitch mockup generation failed" in caplog.text
    assert len(result.references) == 0
