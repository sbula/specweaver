import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

from specweaver.flow._base import RunContext
from specweaver.flow._review import ReviewSpecHandler
from specweaver.llm.models import ProjectMetadata, PromptSafeConfig, LLMResponse

async def main():
    try:
        tmp_path = Path("tmp_test_dir")
        tmp_path.mkdir(exist_ok=True)
        (tmp_path / "test.md").write_text("# Target Spec", encoding="utf-8")
        
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = LLMResponse(text="VERDICT: ACCEPTED\n", model="test")
        
        metadata = ProjectMetadata(
            project_name="integ-test-metadata",
            archetype="pure-logic",
            language_target="python",
            date_iso="now",
            safe_config=PromptSafeConfig(llm_provider="test", llm_model="test", validation_rules={})
        )
        context = RunContext(
            llm=mock_llm,
            project_path=tmp_path, 
            spec_path=tmp_path / "test.md", 
            project_metadata=metadata
        )
        
        handler = ReviewSpecHandler()
        res = await handler.execute(None, context)
        print("RESULT", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
