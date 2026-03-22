import os

paths = ["src", "tests"]
for root in paths:
    for dirpath, dirnames, filenames in os.walk(root):
        for filename in filenames:
            if not filename.endswith(".py"): continue
            filepath = os.path.join(dirpath, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = content.replace("gemini-2.5-flash", "gemini-3-flash-preview").replace("gemini-2.5-pro", "gemini-3-pro-preview")
            if content != new_content:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Updated {filepath}")
