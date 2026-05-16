import os

TEST_DIR = r"c:\development\pitbula\specweaver\tests\unit\workflows\drafting"

for root, _, files in os.walk(TEST_DIR):
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            with open(filepath, encoding="utf-8") as f:
                content = f.read()

            new_content = content
            changed = False

            # Remove the illegal import
            if "from specweaver.core.flow.handlers._profiles import INTERACTIVE\n" in new_content:
                new_content = new_content.replace("from specweaver.core.flow.handlers._profiles import INTERACTIVE\n", "")
                changed = True

            # Replace PromptBuilder(profile=INTERACTIVE) with PromptBuilder()
            if "PromptBuilder(profile=INTERACTIVE)" in new_content:
                new_content = new_content.replace("PromptBuilder(profile=INTERACTIVE)", "PromptBuilder()")
                changed = True

            if changed:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Reverted imports in {filepath}")
