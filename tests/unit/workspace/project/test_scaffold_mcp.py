from pathlib import Path

import pytest

from specweaver.workspace.project.scaffold import scaffold_project


class TestScaffoldMCP:
    def test_creates_mcp_postgres_tree(self, tmp_path: Path) -> None:
        """mcp_target='postgres' generates the .specweaver_mcp/postgres/context.yaml file."""
        scaffold_project(tmp_path, mcp_target="postgres")
        mcp_context = tmp_path / ".specweaver_mcp" / "postgres" / "context.yaml"
        assert mcp_context.is_file()
        content = mcp_context.read_text(encoding="utf-8")
        assert "docker" in content
        assert "server-postgres" in content

    def test_creates_vault_env(self, tmp_path: Path) -> None:
        """mcp_target='postgres' generates .specweaver/vault.env with NFR-2 restrictions."""
        scaffold_project(tmp_path, mcp_target="postgres")
        vault_env = tmp_path / ".specweaver" / "vault.env"
        assert vault_env.is_file()
        content = vault_env.read_text(encoding="utf-8")
        assert "POSTGRES_USER=" in content
        assert "restricted read-only account" in content

    def test_appends_to_gitignore(self, tmp_path: Path) -> None:
        """mcp_target='postgres' ensures .specweaver/vault.env is securely gitignored."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("existing_rule\n", encoding="utf-8")
        scaffold_project(tmp_path, mcp_target="postgres")
        content = gitignore.read_text(encoding="utf-8")
        assert ".specweaver/vault.env" in content
        assert "existing_rule" in content

    def test_mcp_target_invalid_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unsupported MCP target"):
            scaffold_project(tmp_path, mcp_target="unknown")
