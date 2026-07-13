"""Append-only routing and execution telemetry."""

from __future__ import annotations

import json
import re
import threading
from collections import deque
from pathlib import Path

from .models import ExecutionRecord, OutcomeRecord, to_dict

_SENSITIVE_ERROR_VALUE = re.compile(
    r"(?i)(\b(?:api[-_ ]?key|authorization|token|secret|password|key)\b\s*(?:=|:)\s*)"
    r"(?:bearer\s+)?[^\s,;&]+"
)
_BEARER_TOKEN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]+=*")


def _redact_error(value: str) -> str:
    """Avoid persisting credentials that an upstream exception may include."""
    value = _SENSITIVE_ERROR_VALUE.sub(r"\1[REDACTED]", value)
    return _BEARER_TOKEN.sub("Bearer [REDACTED]", value)


class ExecutionTelemetryStore:
    def __init__(self, path: Path | str | None = None, *, memory_limit: int = 1000) -> None:
        self.path = Path(path) if path else None
        self._records: deque[dict] = deque(maxlen=memory_limit)
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict):
                        self._records.append(payload)
        except OSError:
            return

    def record(self, execution: ExecutionRecord) -> None:
        payload = to_dict(execution)
        if isinstance(payload.get("error"), str):
            payload["error"] = _redact_error(payload["error"])
        with self._lock:
            self._records.append(payload)
            if self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def list(self, *, limit: int = 100) -> list[dict]:
        with self._lock:
            return list(self._records)[-max(0, limit) :][::-1]


class OutcomeTelemetryStore:
    """Append-only store for bounded outcome signals, never prompt content."""

    def __init__(self, path: Path | str | None = None, *, memory_limit: int = 1000) -> None:
        self.path = Path(path) if path else None
        self._records: deque[dict] = deque(maxlen=memory_limit)
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict):
                        self._records.append(payload)
        except OSError:
            return

    def record(self, outcome: OutcomeRecord) -> None:
        payload = to_dict(outcome)
        with self._lock:
            self._records.append(payload)
            if self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def list(self, *, limit: int = 100) -> list[dict]:
        with self._lock:
            return list(self._records)[-max(0, limit) :][::-1]
