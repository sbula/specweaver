# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for specweaver.llm.mention_scanner.scanner — extract_mentions()."""

from __future__ import annotations

from specweaver.llm.mention_scanner.scanner import extract_mentions

# ===========================================================================
# Backtick-quoted paths
# ===========================================================================


class TestBacktickPaths:
    """Extract file references inside backticks."""

    def test_single_backtick_path(self) -> None:
        text = "See `src/auth/handler.py` for details."
        assert "src/auth/handler.py" in extract_mentions(text)

    def test_spec_in_backticks(self) -> None:
        text = "Refer to `auth_service_spec.md` for the contract."
        assert "auth_service_spec.md" in extract_mentions(text)

    def test_multiple_backtick_paths(self) -> None:
        text = "Files `foo.py` and `bar/baz.py` are relevant."
        result = extract_mentions(text)
        assert "foo.py" in result
        assert "bar/baz.py" in result

    def test_backtick_with_extension(self) -> None:
        text = "Check `config.yaml` for settings."
        assert "config.yaml" in extract_mentions(text)


# ===========================================================================
# Quoted paths
# ===========================================================================


class TestQuotedPaths:
    """Extract file references inside quotes."""

    def test_double_quoted_path(self) -> None:
        text = 'The file "src/models/user.py" contains the model.'
        assert "src/models/user.py" in extract_mentions(text)

    def test_single_quoted_path(self) -> None:
        text = "Look at 'utils/helpers.py' for shared code."
        assert "utils/helpers.py" in extract_mentions(text)


# ===========================================================================
# Bare spec names
# ===========================================================================


class TestBareSpecNames:
    """Extract _spec.md and _spec.yaml without quotes/backticks."""

    def test_bare_spec_md(self) -> None:
        text = "The auth_service_spec.md defines the contract."
        assert "auth_service_spec.md" in extract_mentions(text)

    def test_bare_spec_yaml(self) -> None:
        text = "See the pipeline_spec.yaml for steps."
        assert "pipeline_spec.yaml" in extract_mentions(text)


# ===========================================================================
# Relative paths
# ===========================================================================


class TestRelativePaths:
    """Extract paths with directory separators."""

    def test_relative_py_path(self) -> None:
        text = "The implementation in src/models/user.py is correct."
        assert "src/models/user.py" in extract_mentions(text)

    def test_deep_relative_path(self) -> None:
        text = "Check src/specweaver/loom/tools/filesystem/tool.py for details."
        assert "src/specweaver/loom/tools/filesystem/tool.py" in extract_mentions(text)


# ===========================================================================
# Filtering
# ===========================================================================


class TestFiltering:
    """URL, __init__.py, and other false-positive filtering."""

    def test_url_filtered(self) -> None:
        text = "See https://example.com/path/file.py for docs."
        result = extract_mentions(text)
        assert not any("example.com" in r for r in result)

    def test_http_url_filtered(self) -> None:
        text = "Reference: http://docs.python.org/lib.html"
        result = extract_mentions(text)
        assert not any("python.org" in r for r in result)

    def test_bare_init_filtered(self) -> None:
        text = "The __init__.py exports the public API."
        assert "__init__.py" not in extract_mentions(text)

    def test_full_path_init_included(self) -> None:
        text = "Check `src/models/__init__.py` for exports."
        assert "src/models/__init__.py" in extract_mentions(text)

    def test_short_candidates_filtered(self) -> None:
        text = "Use `x.y` as the key."
        # Too short (< 4 chars) — should not match as file
        result = extract_mentions(text)
        assert not any(r == "x.y" for r in result)


# ===========================================================================
# Deduplication
# ===========================================================================


class TestDeduplication:
    """Same file mentioned multiple times → single entry."""

    def test_dedup_same_mention(self) -> None:
        text = "See `foo.py` and also `foo.py` again."
        result = extract_mentions(text)
        assert result.count("foo.py") == 1

    def test_dedup_across_patterns(self) -> None:
        text = 'The file `auth_spec.md` is also mentioned as "auth_spec.md".'
        result = extract_mentions(text)
        assert result.count("auth_spec.md") == 1

    def test_preserves_first_seen_order(self) -> None:
        text = "See `beta.py`, `alpha.py`, then `beta.py` again."
        result = extract_mentions(text)
        assert result == ["beta.py", "alpha.py"]


# ===========================================================================
# Large code block stripping
# ===========================================================================


class TestCodeBlockStripping:
    """Large fenced code blocks should be skipped."""

    def test_large_block_skipped(self) -> None:
        lines = [
            "Before the block.",
            "```python",
            "import os",
            "import sys",
            "from pathlib import Path",
            "from specweaver.llm import adapter",
            "x = fake_module.py",
            "y = another_file.py",
            "```",
            "After the block, see `real_file.py`.",
        ]
        text = "\n".join(lines)
        result = extract_mentions(text)
        assert "real_file.py" in result
        # Files inside the 6-line block should be skipped
        assert "fake_module.py" not in result
        assert "another_file.py" not in result

    def test_small_block_with_backtick_path_kept(self) -> None:
        lines = [
            "```",
            "See `config.yaml` here",
            "```",
        ]
        text = "\n".join(lines)
        result = extract_mentions(text)
        assert "config.yaml" in result

    def test_small_block_with_relative_path_kept(self) -> None:
        lines = [
            "```",
            "Edit src/config.yaml",
            "```",
        ]
        text = "\n".join(lines)
        result = extract_mentions(text)
        assert "src/config.yaml" in result

    def test_unclosed_block_with_path_included(self) -> None:
        lines = [
            "```python",
            "See `helper.py` for details",
        ]
        text = "\n".join(lines)
        result = extract_mentions(text)
        assert "helper.py" in result


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    """Boundary conditions and unusual inputs."""

    def test_empty_string(self) -> None:
        assert extract_mentions("") == []

    def test_no_mentions(self) -> None:
        assert extract_mentions("This is a plain text response.") == []

    def test_newlines_in_backticks_not_matched(self) -> None:
        text = "`multi\nline.py`"
        # Backtick pattern should not cross newlines
        assert "multi\nline.py" not in extract_mentions(text)
