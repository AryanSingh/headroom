"""Cursor IDE plugin for cutctx learn.

Reads agent transcripts from ``~/.cursor/projects/<encoded-path>/agent-transcripts/``.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path, PureWindowsPath

from .._shared import classify_error, is_error_content, normalize_tool_name
from ..base import ConversationScanner, LearnPlugin
from ..models import (
    ErrorCategory,
    ProjectInfo,
    SessionData,
    SessionEvent,
    ToolCall,
)
from ..writer import ContextWriter, CursorWriter

logger = logging.getLogger(__name__)


class CursorPlugin(LearnPlugin, ConversationScanner):
    """Reads Cursor agent transcripts from ~/.cursor/projects/."""

    def __init__(self, cursor_dir: Path | None = None):
        self.cursor_dir = cursor_dir or Path.home() / ".cursor"
        self.projects_dir = self.cursor_dir / "projects"

    @property
    def name(self) -> str:
        return "cursor"

    @property
    def display_name(self) -> str:
        return "Cursor"

    @property
    def description(self) -> str:
        return "Cursor IDE (~/.cursor/projects/)"

    def detect(self) -> bool:
        if not self.projects_dir.exists():
            return False
        return any(self.projects_dir.rglob("agent-transcripts/*/*.jsonl"))

    def create_writer(self) -> ContextWriter:
        return CursorWriter()

    def discover_projects(self) -> list[ProjectInfo]:
        if not self.projects_dir.exists():
            return []

        projects: list[ProjectInfo] = []
        for entry in sorted(self.projects_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            transcripts = list(entry.rglob("agent-transcripts/*/*.jsonl"))
            if not transcripts:
                continue

            project_path = _decode_project_path(entry.name) or Path.cwd()
            context_file = project_path / ".cursorrules" if project_path.exists() else None
            projects.append(
                ProjectInfo(
                    name=_project_display_name(project_path, entry.name),
                    project_path=project_path,
                    data_path=entry,
                    context_file=context_file if context_file and context_file.exists() else None,
                )
            )
        return projects

    def scan_project(self, project: ProjectInfo, max_workers: int = 1) -> list[SessionData]:
        del max_workers
        sessions: list[SessionData] = []
        for transcript in sorted(project.data_path.rglob("agent-transcripts/*/*.jsonl")):
            session = self._scan_transcript(transcript, project)
            if session.tool_calls:
                sessions.append(session)
        return sessions

    def _scan_transcript(self, path: Path, project: ProjectInfo) -> SessionData:
        session_id = path.stem
        tool_calls: list[ToolCall] = []
        events: list[SessionEvent] = []
        msg_index = 0

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return SessionData(session_id=session_id, tool_calls=[], events=[])

        for line in lines:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue

            if payload.get("type") == "turn_ended":
                continue

            role = payload.get("role")
            message = payload.get("message", {})
            content = message.get("content", []) if isinstance(message, dict) else []
            if role == "user":
                self._extract_user_events(content, events, msg_index)
            elif role == "assistant":
                self._extract_assistant_events(content, tool_calls, events, msg_index)
            msg_index += 1

        return SessionData(
            session_id=session_id,
            tool_calls=tool_calls,
            events=events,
        )

    def _extract_user_events(
        self,
        content: list | str,
        events: list[SessionEvent],
        msg_index: int,
    ) -> None:
        if isinstance(content, str) and content.strip():
            events.append(
                SessionEvent(type="user_message", msg_index=msg_index, text=content[:500])
            )
            return
        if not isinstance(content, list):
            return
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            text = block.get("text", "")
            if text.strip():
                events.append(
                    SessionEvent(type="user_message", msg_index=msg_index, text=text[:500])
                )

    def _extract_assistant_events(
        self,
        content: list,
        tool_calls: list[ToolCall],
        events: list[SessionEvent],
        msg_index: int,
    ) -> None:
        if not isinstance(content, list):
            return
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                text = block.get("text", "")
                if is_error_content(text):
                    category = classify_error(text)
                    events.append(
                        SessionEvent(
                            type="error",
                            msg_index=msg_index,
                            text=text[:500],
                            error_category=category,
                        )
                    )
            if block.get("type") != "tool_use":
                continue
            tool_name = normalize_tool_name(str(block.get("name", "unknown")))
            tool_input = block.get("input", {})
            if not isinstance(tool_input, dict):
                tool_input = {}
            output = json.dumps(tool_input)[:1000]
            is_err = is_error_content(output)
            category = classify_error(output) if is_err else ErrorCategory.UNKNOWN
            tool_calls.append(
                ToolCall(
                    name=tool_name,
                    tool_call_id=str(block.get("id", f"{msg_index}:{tool_name}")),
                    input_data=tool_input,
                    output=output,
                    is_error=is_err,
                    error_category=category,
                    msg_index=msg_index,
                    output_bytes=len(output.encode("utf-8")),
                )
            )


def _decode_project_path(encoded_name: str) -> Path | None:
    parts = encoded_name.split("-")
    if len(parts) >= 3 and parts[0] in {"Users", "home"}:
        candidate = Path("/" + "/".join(parts))
        if candidate.exists():
            return candidate
    simple = Path("/" + encoded_name.replace("-", "/"))
    if simple.exists():
        return simple
    return None


def _project_display_name(project_path: Path, fallback: str) -> str:
    rendered = str(project_path)
    if re.match(r"^[A-Za-z]:[\\/]", rendered):
        return PureWindowsPath(rendered).name or fallback
    return project_path.name or fallback


plugin = CursorPlugin()
