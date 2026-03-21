import re
from pathlib import Path

path = Path(r"c:\development\pitbula\specweaver\src\specweaver\standards\languages\python\analyzer.py")
content = path.read_text("utf-8")

# 1. Replace the signature of all extractors
extractors = [
    "_extract_naming",
    "_extract_error_handling",
    "_extract_type_hints",
    "_extract_docstrings",
    "_extract_imports",
    "_extract_test_patterns"
]
for ext in extractors:
    old_sig = f"def {ext}(\n        self, files: list[Path], half_life_days: float,\n    ) -> CategoryResult:"
    new_sig = f"def {ext}(\n        self, parsed_files: list[tuple[Path, float, ast.Module]],\n    ) -> CategoryResult:"
    content = content.replace(old_sig, new_sig)

# 2. Replace the tree = self._parse_file loop in the normal extractors
old_loop_with_weight = re.compile(
    r"for path in files:\n\s*tree = self\._parse_file\(path\)\n\s*if tree is None:\n\s*continue\n\s*w = self\._file_weight\(path, half_life_days\)"
)
content = old_loop_with_weight.sub(r"for path, w, tree in parsed_files:", content)

old_loop_no_weight = re.compile(
    r"for path in files:\n\s*tree = self\._parse_file\(path\)\n\s*if tree is None:\n\s*continue"
)
content = old_loop_no_weight.sub(r"for path, w, tree in parsed_files:", content)

# 3. Replace the tree = self._parse_file in the test_patterns extractor
old_loop_test = re.compile(
    r"for path in files:\n\s*if not path\.name\.startswith.*?continue\n\n\s*tree = self\._parse_file\(path\)\n\s*if tree is None:\n\s*continue(?:\n\s*w = self\._file_weight\(path, half_life_days\))?",
    re.DOTALL
)
content = old_loop_test.sub(r'for path, w, tree in parsed_files:\n            if not path.name.startswith("test_") and not path.name.endswith("_test.py"):\n                continue', content)


# 4. Replace extract with extract_all
old_extract = re.compile(r"def extract\(.*?\) -> CategoryResult:.*?return extractors\[category\]\(files, half_life_days\)", re.DOTALL)

new_extract = """def extract_all(
        self,
        files: list[Path],
        half_life_days: float,
    ) -> list[CategoryResult]:
        parsed_files: list[tuple[Path, float, ast.Module]] = []
        for path in files:
            tree = self._parse_file(path)
            if tree is None:
                continue
            w = self._file_weight(path, half_life_days)
            parsed_files.append((path, w, tree))

        extractors = [
            self._extract_naming,
            self._extract_error_handling,
            self._extract_type_hints,
            self._extract_docstrings,
            self._extract_imports,
            self._extract_test_patterns,
        ]

        results = []
        for ext in extractors:
            try:
                results.append(ext(parsed_files))
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to extract with {ext.__name__}: {e}")
                
        return results"""

content = old_extract.sub(new_extract, content)

path.write_text(content, "utf-8")
print("Done")
