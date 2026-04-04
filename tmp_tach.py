import subprocess
import os
import sys
import tempfile
from pathlib import Path

def run():
    with tempfile.TemporaryDirectory() as tempd:
        tmp_path = Path(tempd)
        subprocess.run(["git", "init"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp_path), check=True)

        src = tmp_path / "src" / "my_project"
        src.mkdir(parents=True)
        (src / "__init__.py").touch()
        
        core = src / "core"
        core.mkdir()
        (core / "__init__.py").touch()
        core_main = core / "engine.py"
        core_main.write_text("def run(): pass\n")
        
        ui = src / "ui"
        ui.mkdir()
        (ui / "__init__.py").touch()
        ui_main = ui / "cli.py"
        ui_main.write_text("def display(): pass\n")
        
        bad_core = core / "bad.py"
        bad_core.write_text("from my_project.ui.cli import display\n")
        
        tach_toml = tmp_path / "tach.toml"
        tach_toml.write_text("""
[options]
exact = true
source_roots = ["src"]

[[modules]]
path = "<root>"
depends_on = ["my_project.core", "my_project.ui"]

[[modules]]
path = "my_project.core"
depends_on = [] 

[[modules]]
path = "my_project.ui"
depends_on = ["my_project.core"]
""")
        cmd = [sys.executable, "-m", "tach", "check", "--output", "json"]
        proc = subprocess.run(cmd, cwd=str(tmp_path), capture_output=True, text=True)
        print("STDOUT:", repr(proc.stdout))
        print("STDERR:", repr(proc.stderr))
run()
