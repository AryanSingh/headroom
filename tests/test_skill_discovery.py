"""Tests for wrap-time skill directory discovery."""

from __future__ import annotations

from pathlib import Path

from cutctx.transforms.skill_discovery import discover_skill_paths, load_skill_preserve_markers


def test_discovers_claude_and_codex_skill_dirs(tmp_path: Path, monkeypatch) -> None:
    claude = tmp_path / ".claude" / "skills" / "db-safety"
    claude.mkdir(parents=True)
    (claude / "SKILL.md").write_text(
        "---\nname: db-safety\ndescription: safe sql\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    paths = discover_skill_paths(home=tmp_path)
    assert any(p.name == "db-safety" for p in paths)
    markers = load_skill_preserve_markers(paths)
    assert any("db-safety" in m for m in markers)


def test_discovers_project_agents_skills(tmp_path: Path) -> None:
    skill = tmp_path / ".agents" / "skills" / "rtk-prefix"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: rtk-prefix\ndescription: always use rtk\n---\n",
        encoding="utf-8",
    )
    paths = discover_skill_paths(home=tmp_path / "nouser", project_root=tmp_path)
    assert any(p.name == "rtk-prefix" for p in paths)
