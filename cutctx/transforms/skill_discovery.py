"""Discover installed agent skills on this machine.

Discovery is deliberately *not* wired into compression. The obvious wiring —
feed each skill's ``name`` in as an extra substring marker — is unsafe: real
installs yield names like ``pdf``, ``docx``, ``run``, and ``review``, and a
substring match on those exempts most ordinary traffic from compression. Skill
bodies are recognised structurally instead (front matter, ``SKILL.md`` /
``# AGENTS`` / ``# CLAUDE.md`` headings) in ``skill_preserve``.
"""

from __future__ import annotations

import re
from pathlib import Path

_NAME_RE = re.compile(r"(?m)^name:\s*(.+?)\s*$")


def _skill_dirs_under(root: Path) -> list[Path]:
    skills_root = root / "skills"
    if not skills_root.is_dir():
        return []
    found: list[Path] = []
    for child in sorted(skills_root.iterdir()):
        if child.is_dir() and (child / "SKILL.md").is_file():
            found.append(child)
    return found


def discover_skill_paths(
    home: Path | None = None,
    *,
    project_root: Path | None = None,
) -> list[Path]:
    """Return skill package directories that contain SKILL.md.

    Search order (first-present wins per path; duplicates skipped):
    - ``~/.claude/skills/*/SKILL.md``
    - ``~/.codex/skills/*/SKILL.md``
    - ``<project>/.claude/skills/*/SKILL.md``
    - ``<project>/.agents/skills/*/SKILL.md``
    """
    home_path = Path(home) if home is not None else Path.home()
    roots: list[Path] = [
        home_path / ".claude",
        home_path / ".codex",
    ]
    if project_root is not None:
        roots.extend(
            [
                Path(project_root) / ".claude",
                Path(project_root) / ".agents",
            ]
        )

    seen: set[Path] = set()
    paths: list[Path] = []
    for root in roots:
        for skill_dir in _skill_dirs_under(root):
            resolved = skill_dir.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            paths.append(skill_dir)
    return paths


def load_skill_preserve_markers(paths: list[Path]) -> tuple[str, ...]:
    """Extract skill ``name:`` values from SKILL.md front matter.

    Reporting/diagnostics only. See the module docstring for why these names
    must not be used as compression preserve markers.
    """
    markers: list[str] = []
    seen: set[str] = set()
    for path in paths:
        skill_md = path / "SKILL.md"
        try:
            text = skill_md.read_text(encoding="utf-8")
        except OSError:
            continue
        match = _NAME_RE.search(text[:500])
        if not match:
            # Fall back to directory name so discovery still yields a marker.
            name = path.name
        else:
            name = match.group(1).strip().strip("\"'")
        if not name or name in seen:
            continue
        seen.add(name)
        markers.append(name)
    return tuple(markers)
