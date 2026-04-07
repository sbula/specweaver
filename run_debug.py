import textwrap
from pathlib import Path

from specweaver.standards.languages.python.analyzer import PythonStandardsAnalyzer

analyzer = PythonStandardsAnalyzer()
tmp_path = Path("tester_tmp")
tmp_path.mkdir(exist_ok=True)
ns_root = tmp_path / "deep" / "implicit" / "namespace" / "pkg"
ns_root.mkdir(parents=True, exist_ok=True)
nested_file = ns_root / "style.py"
nested_file.write_text(textwrap.dedent("""\
def generate_data():
    \"\"\"Generate some data.\"\"\"
    try:
        return 1
    except ValueError:
        return 2
"""))

discovered_files = list(tmp_path.rglob("*.py"))
results = analyzer.extract_all(discovered_files, 180)
for r in results:
    if r.category == 'naming':
        print(f"Naming sample size: {r.sample_size}, dominant: {r.dominant}")
        break
