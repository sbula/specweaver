import os

import pytest

from specweaver.workflows.planning.stitch import StitchClient


@pytest.mark.live
def test_stitch_live_mcp_connection():
    """Manual test to connect to the real Google Stitch MCP."""
    api_key = os.environ.get("STITCH_API_KEY")
    if not api_key:
        pytest.skip("STITCH_API_KEY not set. Cannot run live test.")

    client = StitchClient(api_key=api_key)
    assert client.is_available(), "Stitch client should be available with key"

    # Actually run the real generation logic
    result = client.generate_mockup("Create a futuristic dashboard for a quantum reactor")

    # Assert we get a payload back
    assert result.references
    assert len(result.references) > 0
    ref = result.references[0]
    assert ref.preview_url
    assert "http" in ref.preview_url
