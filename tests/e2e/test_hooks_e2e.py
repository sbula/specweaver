import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.e2e
def test_hooks_e2e_native_git_commit(tmp_path: Path):
    """
    E2E test that validates the physical git hooks.
    This creates an actual dummy git repo in a temp dir,
    installs the speculative weaver hook, creates a file,
    and calls 'git commit'. We assert that the native Bash script executes
    correctly and the python Spec Rot interceptor works.
    """
    project_dir = tmp_path / "dummy_project"
    project_dir.mkdir()
    
    # Init git repo
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
    
    # Configure git locally just in case CI doesn't have it
    subprocess.run(["git", "config", "user.email", "e2e@example.com"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.name", "E2E Test"], cwd=project_dir, check=True)

    import sys
    # Use the current python executable to act as 'sw' to install the hook
    # We must ensure we're installing the hook for the dummy project
    install_cmd = [sys.executable, "-m", "specweaver.cli.main", "hooks", "install", "--project", str(project_dir)]
    res = subprocess.run(install_cmd, cwd=project_dir, capture_output=True, text=True, encoding="utf-8")
    
    assert res.returncode == 0
    assert "installed successfully" in res.stdout, f"STDOUT: {res.stdout} STDERR: {res.stderr}"

    # Now make a change and commit it
    dummy_file = project_dir / "foo.py"
    dummy_file.write_text("x = 1\n")
    
    subprocess.run(["git", "add", "foo.py"], cwd=project_dir, check=True)
    
    # Try locking the commit. Since we don't have a plan.yml, the drift script might fail
    # or it might actually resolve our default SF-1 behavior (stub).
    # Wait, SF-1 check-rot stub exits cleanly (returncode 0).
    # So the commit SHOULD SUCCEED in SF-1.
    res_commit = subprocess.run(
        ["git", "commit", "-m", "test commit"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    
    # Since SF-1 returns exit code 0 natively, the hook allows it
    assert res_commit.returncode == 0, f"STDOUT: {res_commit.stdout}\nSTDERR: {res_commit.stderr}"
    assert "Bi-Directional Spec Rot Interceptor" in res_commit.stderr
    assert "Checking AST drift for staged files" in res_commit.stderr

    # But what if we simulate check-rot failing with 42?
    # We can hack the hook temporarily to test the bash template's branching
    hook_file = project_dir / ".git" / "hooks" / "pre-commit"
    content = hook_file.read_text(encoding="utf-8")
    
    # Change the captured exit code to `42` to simulate drift
    content_42 = content.replace("exit_code=$?", "exit_code=42")
    hook_file.write_text(content_42, encoding="utf-8")
    
    dummy_file.write_text("x = 2\n")
    subprocess.run(["git", "add", "foo.py"], cwd=project_dir, check=True)
    
    res_fail = subprocess.run(
        ["git", "commit", "-m", "should fail 42"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    
    assert res_fail.returncode == 1
    assert "ERROR: SpecWeaver detected structural drift between Spec and Code!" in res_fail.stderr

    # Finally simulate a crash (simulate exit code 1)
    content_1 = content.replace("exit_code=$?", "exit_code=1")
    hook_file.write_text(content_1, encoding="utf-8")
    
    res_crash = subprocess.run(
        ["git", "commit", "-m", "should fail crash"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    
    assert res_crash.returncode == 1
    assert "ERROR: The SpecWeaver pipeline crashed (1)." in res_crash.stderr
