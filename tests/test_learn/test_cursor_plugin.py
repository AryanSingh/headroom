"""Tests for the Cursor learn plugin."""

from __future__ import annotations

import json
from pathlib import Path

from cutctx.learn.plugins.cursor import CursorPlugin


def _write_transcript(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "role": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "name": "Shell",
                                    "input": {"command": "false"},
                                }
                            ]
                        },
                    }
                ),
                json.dumps({"type": "turn_ended", "status": "success"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_cursor_plugin_detects_transcripts(tmp_path: Path) -> None:
    cursor_home = tmp_path / ".cursor"
    transcript = (
        cursor_home
        / "projects"
        / "tmp-project"
        / "agent-transcripts"
        / "session-1"
        / "session-1.jsonl"
    )
    _write_transcript(transcript)

    plugin = CursorPlugin(cursor_dir=cursor_home)
    assert plugin.detect() is True


def test_cursor_plugin_scans_tool_calls(tmp_path: Path) -> None:
    cursor_home = tmp_path / ".cursor"
    project_dir = cursor_home / "projects" / "tmp-project"
    transcript = project_dir / "agent-transcripts" / "session-1" / "session-1.jsonl"
    _write_transcript(transcript)

    plugin = CursorPlugin(cursor_dir=cursor_home)
    projects = plugin.discover_projects()
    assert len(projects) == 1

    sessions = plugin.scan_project(projects[0])
    assert len(sessions) == 1
    assert sessions[0].tool_calls[0].name == "Bash"
