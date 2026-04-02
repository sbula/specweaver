import os
import subprocess

file_replacements = [
    ("feature_3_14a", "feature_3_18"),
    ("feature_3_14", "feature_3_17"),
    ("feature_3_13a", "feature_3_16"),
    ("feature_3_13", "feature_3_15"),
    ("feature_3_12b", "feature_3_14"),
    ("feature_3_12a", "feature_3_13"),
]

docs_dir = r"c:\development\pitbula\specweaver\docs\proposals"

# 1. Rename files using git mv (sorted to avoid collisions)
for old_str, new_str in file_replacements:
    for root, dirs, files in os.walk(docs_dir):
        for filename in files:
            if not filename.endswith(".md"):
                continue
                
            if old_str in filename:
                new_filename = filename.replace(old_str, new_str)
                old_path = os.path.join(root, filename)
                new_path = os.path.join(root, new_filename)
                
                # Check if target exists; if it does, it's a critical error we shouldn't hit now.
                if os.path.exists(new_path):
                    print(f"ERROR: Target exists! {new_path}")
                    continue
                    
                print(f"Renaming {filename} -> {new_filename}")
                try:
                    subprocess.run(["git", "mv", old_path, new_path], check=True, cwd=docs_dir)
                except Exception as e:
                    print(f"Git mv failed, using os.rename: {e}")
                    os.rename(old_path, new_path)

# 2. Update contents of all markdown files with URI updates in ONE PASS per file 
# BUT we must apply replacements in reverse order of length or simply trust our top-down list
for root, dirs, files in os.walk(docs_dir):
    for filename in files:
        if not filename.endswith(".md"):
            continue
            
        filepath = os.path.join(root, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        new_content = content
        for old_str, new_str in file_replacements:
            new_content = new_content.replace(old_str, new_str)
            
        if new_content != content:
            print(f"Updating links in {filename}")
            with open(filepath, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_content)
