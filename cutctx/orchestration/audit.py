"""Tamper-evident orchestration receipt audit storage."""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from pathlib import Path
from typing import Any

from .models import RoutingDecision, to_dict


class ReceiptAuditStore:
    """Append-only HMAC chain over decision receipts, never raw requests."""

    def __init__(self, path: Path | str, *, key: str) -> None:
        if not key.strip():
            raise ValueError("Receipt audit key is required")
        self.path = Path(path)
        self.key = key.encode()
        self._lock = threading.RLock()

    def append(self, decision: RoutingDecision, *, execution_id: str) -> dict[str, Any]:
        with self._lock:
            if self.path.exists() and not self.verify():
                raise ValueError("Receipt audit chain is invalid; refusing to append")
            prior = self._last_hash()
            payload = {
                "audit_version": 1,
                "execution_id": execution_id,
                "request_id": decision.request_id,
                "receipt": to_dict(decision),
                "previous_hash": prior,
            }
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            payload["event_hash"] = hmac.new(self.key, canonical, hashlib.sha256).hexdigest()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, sort_keys=True) + "\n")
            return payload

    def verify(self) -> bool:
        previous: str | None = None
        if not self.path.exists():
            return True
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    event = json.loads(line)
                    actual = event.pop("event_hash", None)
                    if event.get("previous_hash") != previous or not isinstance(actual, str):
                        return False
                    canonical = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
                    expected = hmac.new(self.key, canonical, hashlib.sha256).hexdigest()
                    if not hmac.compare_digest(actual, expected):
                        return False
                    previous = actual
        except (OSError, json.JSONDecodeError):
            return False
        return True

    def export_jsonl(self) -> str:
        return self.path.read_text(encoding="utf-8") if self.path.exists() else ""

    def _last_hash(self) -> str | None:
        if not self.path.exists():
            return None
        try:
            last = ""
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    last = line
            return json.loads(last).get("event_hash") if last else None
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Receipt audit log cannot be read") from exc


__all__ = ["ReceiptAuditStore"]
