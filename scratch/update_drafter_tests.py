import os

TEST_DIR = r"c:\development\pitbula\specweaver\tests\unit\workflows\drafting"

import_statement = "from specweaver.core.flow.handlers._profiles import INTERACTIVE\n"

for root, _, files in os.walk(TEST_DIR):
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            with open(filepath, encoding="utf-8") as f:
                content = f.read()

            new_content = content
            changed = False

            # We already changed Drafter( -> Drafter(base_prompt=PromptBuilder(profile=INTERACTIVE),
            # but we need to ensure INTERACTIVE is imported if missing.
            if 'INTERACTIVE' in new_content and 'from specweaver.core.flow.handlers._profiles import INTERACTIVE' not in new_content:
                import_idx = new_content.rfind('import pytest')
                if import_idx != -1:
                    # insert after pytest
                    insert_pos = new_content.find('\n', import_idx) + 1
                    new_content = new_content[:insert_pos] + import_statement + new_content[insert_pos:]
                else:
                    new_content = import_statement + new_content
                changed = True

                # Ensure PromptBuilder is imported too, just in case
                if 'PromptBuilder' in new_content and 'from specweaver.infrastructure.llm.prompt_builder import PromptBuilder' not in new_content:
                    new_content = "from specweaver.infrastructure.llm.prompt_builder import PromptBuilder\n" + new_content

            if changed:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Updated imports in {filepath}")
