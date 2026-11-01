"""Regression test for disabled-skill gate bypass via '.' path segment.

The gate in read_file/_is_disabled_skill_path was broken: inserting a '.'
segment (e.g. /mnt/skills/public/./foo/SKILL.md) yielded '.' as the skill name,
which was treated as enabled, and realpath then collapsed the path to the real file.

This test uses the real read_file_tool and _is_disabled_skill_path functions
against a temp skills directory and a real LocalSandbox, verifying that both the
normal path and the '.'-segment variant are now correctly rejected.
"""

import tempfile
from pathlib import Path

import pytest

from deerflow.sandbox.local.local_sandbox import LocalSandbox
from deerflow.sandbox.tools import read_file_tool, _is_disabled_skill_path, _extract_skill_name_from_skills_path


def test_disabled_skill_dot_segment_bypass(monkeypatch):
    """Verify that a '.' path segment doesn't bypass the disabled-skill gate."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_root = Path(tmpdir) / "skills"
        public = skills_root / "public"
        public.mkdir(parents=True)
        (public / "foo").mkdir()
        (public / "foo" / "SKILL.md").write_text("SECRET DISABLED SKILL BODY", encoding="utf-8")

        # Mock the skills root path and user_id
        monkeypatch.setattr("deerflow.sandbox.tools._get_skills_container_path", lambda: "/mnt/skills")
        monkeypatch.setattr("deerflow.sandbox.tools.resolve_runtime_user_id", lambda _: "test_user")
        monkeypatch.setattr("deerflow.sandbox.tools.ensure_sandbox_initialized", lambda _: None)
        monkeypatch.setattr("deerflow.sandbox.tools.is_local_sandbox", lambda _: True)
        monkeypatch.setattr("deerflow.sandbox.tools.get_thread_data", lambda _: None)

        # Mock extensions_config to mark skill 'foo' as disabled
        def mock_is_skill_enabled(self, name, category=None):
            return name != "foo"

        from deerflow.config import extensions_config as ext_cfg_mod

        monkeypatch.setattr(ext_cfg_mod, "ExtensionsConfig", type("MockConfig", (), {"from_file": lambda: type("C", (), {"is_skill_enabled": mock_is_skill_enabled})()}))

        # Create a real LocalSandbox with path mapping
        sandbox = LocalSandbox(
            id="test_thread",
            path_mappings=[("/mnt/skills", str(skills_root))],
        )

        # Test extraction and disabled check
        normal_path = "/mnt/skills/public/foo/SKILL.md"
        dot_path = "/mnt/skills/public/./foo/SKILL.md"

        # Both paths should now extract 'foo' as the skill name (not '.')
        assert _extract_skill_name_from_skills_path(normal_path) == "foo"
        assert _extract_skill_name_from_skills_path(dot_path) == "foo", "normpath should collapse '.' before extraction"

        # Both paths should be recognized as disabled
        assert _is_disabled_skill_path(normal_path, user_id="test_user") is True
        assert _is_disabled_skill_path(dot_path, user_id="test_user") is True, "dot segment must not bypass the gate"

        # read_file should reject both
        result_normal = read_file_tool.func(sandbox, normal_path)
        assert "Skill 'foo' is disabled" in result_normal, f"Expected rejection for normal path, got: {result_normal}"

        result_dot = read_file_tool.func(sandbox, dot_path)
        assert "Skill 'foo' is disabled" in result_dot, f"Expected rejection for dot path, got: {result_dot}"


def test_disabled_skill_dot_at_category_level(monkeypatch):
    """Verify that '/mnt/skills/./public/foo/...' is also normalized and rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_root = Path(tmpdir) / "skills"
        public = skills_root / "public"
        public.mkdir(parents=True)
        (public / "bar").mkdir()
        (public / "bar" / "SKILL.md").write_text("ANOTHER SECRET", encoding="utf-8")

        monkeypatch.setattr("deerflow.sandbox.tools._get_skills_container_path", lambda: "/mnt/skills")
        monkeypatch.setattr("deerflow.sandbox.tools.resolve_runtime_user_id", lambda _: "test_user")
        monkeypatch.setattr("deerflow.sandbox.tools.ensure_sandbox_initialized", lambda _: None)
        monkeypatch.setattr("deerflow.sandbox.tools.is_local_sandbox", lambda _: True)
        monkeypatch.setattr("deerflow.sandbox.tools.get_thread_data", lambda _: None)

        def mock_is_skill_enabled(self, name, category=None):
            return name != "bar"

        from deerflow.config import extensions_config as ext_cfg_mod

        monkeypatch.setattr(ext_cfg_mod, "ExtensionsConfig", type("MockConfig", (), {"from_file": lambda: type("C", (), {"is_skill_enabled": mock_is_skill_enabled})()}))

        sandbox = LocalSandbox(
            id="test_thread2",
            path_mappings=[("/mnt/skills", str(skills_root))],
        )

        dot_at_category = "/mnt/skills/./public/bar/SKILL.md"
        assert _extract_skill_name_from_skills_path(dot_at_category) == "bar"
        assert _is_disabled_skill_path(dot_at_category, user_id="test_user") is True

        result = read_file_tool.func(sandbox, dot_at_category)
        assert "Skill 'bar' is disabled" in result, f"Expected rejection, got: {result}"
