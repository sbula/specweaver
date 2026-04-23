f = "tests/unit/infrastructure/llm/test_prompt_builder_skeleton.py"
with open(f) as file:
    c = file.read()
c = c.replace(
    'patch("specweaver.infrastructure.llm.prompt_builder.extract_ast_skeleton")',
    'patch("specweaver.infrastructure.llm._skeleton.extract_ast_skeleton")',
)
c = c.replace(
    'ResolvedMention(original="dep1", resolved_path=f1)',
    'ResolvedMention(original="dep1", resolved_path=f1, kind="import")',
)
c = c.replace(
    'ResolvedMention(original="dep2", resolved_path=f2)',
    'ResolvedMention(original="dep2", resolved_path=f2, kind="import")',
)
with open(f, "w") as file:
    file.write(c)

files2 = [
    "tests/unit/workflows/implementation/test_generator_skeleton.py",
    "tests/unit/workflows/review/test_reviewer_skeleton.py",
]
for f in files2:
    with open(f) as file:
        c = file.read()
    c = c.replace("MagicMock()", "AsyncMock()")
    if "from unittest.mock import" in c and "AsyncMock" not in c:
        c = c.replace(
            "from unittest.mock import MagicMock, patch",
            "from unittest.mock import MagicMock, AsyncMock, patch",
        )
    with open(f, "w") as file:
        file.write(c)

f3 = "tests/unit/core/flow/handlers/test_skeleton_wiring.py"
with open(f3) as file:
    c = file.read()
if "from unittest.mock import" in c and "MagicMock" not in c:
    c = c.replace(
        "from unittest.mock import AsyncMock, patch",
        "from unittest.mock import AsyncMock, MagicMock, patch",
    )
with open(f3, "w") as file:
    file.write(c)

print("Done fixing!")
