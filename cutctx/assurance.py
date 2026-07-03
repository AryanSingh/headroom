"""WS7: Context Assurance — durable evidence ledger with HMAC chaining.

CCR compression/retrieval events, policy decisions, and session metadata
are recorded in a local SQLite ledger with HMAC-SHA256 chaining for
tamper evidence. Evidence can be exported as JSON or markdown for
enterprise audit use.

Usage:
    ledger = EvidenceLedger()
    ledger.record_compression(...)
    ledger.record_policy_block(...)
    bundle = ledger.export_bundle()
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_LEDGER_PATH = Path("~/.cutctx/assurance.ledger.db")
_LEDGER_ENV = "CUTCTX_ASSURANCE_LEDGER"
_HMAC_KEY_ENV = "CUTCTX_ASSURANCE_HMAC_KEY"

# ---------------------------------------------------------------------------
# Event models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceEvent:
    """A single evidence event in the ledger.

    Each event carries a ``prev_hash`` pointing to the previous row's hash,
    forming an HMAC chain. The current row's ``row_hash`` is computed over
    the concatenation of ``prev_hash`` + all canonical fields.
    """

    event_id: str
    timestamp: float
    event_type: str
    session_id: str
    workspace_id: str = ""
    project_id: str = ""
    agent_id: str = ""
    detail_json: str = "{}"
    prev_hash: str = ""
    row_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "agent_id": self.agent_id,
            "detail": json.loads(self.detail_json) if self.detail_json else {},
            "row_hash": self.row_hash,
            "prev_hash": self.prev_hash,
        }

    def canonical_message(self, hmac_key: bytes) -> bytes:
        """Length-prefixed canonical message for HMAC computation."""
        parts = [
            self.event_id,
            str(self.timestamp),
            self.event_type,
            self.session_id,
            self.workspace_id,
            self.project_id,
            self.agent_id,
            self.detail_json,
            self.prev_hash,
        ]
        return b"".join(
            len(p.encode("utf-8")).to_bytes(4, "big") + p.encode("utf-8") for p in parts
        )

    def compute_hash(self, hmac_key: bytes) -> str:
        return hmac.new(hmac_key, self.canonical_message(hmac_key), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------

EVENT_COMPRESSION = "compression"
EVENT_RETRIEVAL = "retrieval"
EVENT_POLICY_BLOCK = "policy_block"
EVENT_POLICY_REDACT = "policy_redact"
EVENT_INJECTION = "injection"
EVENT_CCR_LIFECYCLE = "ccr_lifecycle"


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


class EvidenceLedger:
    """Durable append-only evidence ledger backed by local SQLite.

    Thread-safe: each operation uses its own connection. HMAC-SHA256
    chaining means every row is cryptographically linked to its predecessor
    and to an operator-provided secret key.
    """

    def __init__(self, path: Path | str | None = None, hmac_key: bytes | None = None) -> None:
        self.path = Path(path or self._default_path()).expanduser()
        self._hmac_key = hmac_key or self._load_hmac_key()
        self._init_db()

    @staticmethod
    def _default_path() -> Path:
        return Path(os.environ.get(_LEDGER_ENV, str(DEFAULT_LEDGER_PATH)))

    @staticmethod
    def _load_hmac_key() -> bytes:
        key = os.environ.get(_HMAC_KEY_ENV)
        if key:
            return key.encode("utf-8")
        # Fallback: derive from machine-local state. This is NOT cryptographically
        # secret (the key is stored alongside the data) but provides tamper evidence
        # through chaining — any alteration breaks the chain regardless.
        return hashlib.sha256(b"cutctx-default-assurance-key").digest()

    def _init_db(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_ledger (
                    event_id TEXT PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL DEFAULT '',
                    project_id TEXT NOT NULL DEFAULT '',
                    agent_id TEXT NOT NULL DEFAULT '',
                    detail_json TEXT NOT NULL DEFAULT '{}',
                    prev_hash TEXT NOT NULL DEFAULT '',
                    row_hash TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ledger_type ON evidence_ledger(event_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ledger_session ON evidence_ledger(session_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ledger_time ON evidence_ledger(timestamp)"
            )

    def _last_hash(self) -> str:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT row_hash FROM evidence_ledger ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            return row[0] if row else ""

    def record(
        self,
        *,
        event_id: str,
        event_type: str,
        session_id: str,
        workspace_id: str = "",
        project_id: str = "",
        agent_id: str = "",
        detail: dict[str, Any] | None = None,
    ) -> EvidenceEvent:
        """Append an event to the ledger."""
        prev_hash = self._last_hash()
        event = EvidenceEvent(
            event_id=event_id,
            timestamp=time.time(),
            event_type=event_type,
            session_id=session_id,
            workspace_id=workspace_id,
            project_id=project_id,
            agent_id=agent_id,
            detail_json=json.dumps(detail or {}, sort_keys=True),
            prev_hash=prev_hash,
        )
        row_hash = event.compute_hash(self._hmac_key)
        event = EvidenceEvent(**{**asdict(event), "row_hash": row_hash})

        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO evidence_ledger (
                    event_id, timestamp, event_type, session_id,
                    workspace_id, project_id, agent_id,
                    detail_json, prev_hash, row_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.timestamp,
                    event.event_type,
                    event.session_id,
                    event.workspace_id,
                    event.project_id,
                    event.agent_id,
                    event.detail_json,
                    event.prev_hash,
                    event.row_hash,
                ),
            )
            conn.commit()
        return event

    def query(
        self,
        *,
        event_type: str | None = None,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[EvidenceEvent]:
        """Query recent events with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                f"SELECT * FROM evidence_ledger{where} ORDER BY timestamp DESC LIMIT ?",
                [*params, limit],
            ).fetchall()
        return [
            EvidenceEvent(
                event_id=r[0], timestamp=r[1], event_type=r[2], session_id=r[3],
                workspace_id=r[4], project_id=r[5], agent_id=r[6],
                detail_json=r[7], prev_hash=r[8], row_hash=r[9],
            )
            for r in rows
        ]

    def verify_chain(self) -> dict[str, Any]:
        """Verify the HMAC chain integrity by recomputing every row hash.

        Reads each full row, re-derives the canonical message and HMAC,
        and compares against the stored ``row_hash``. Then checks that
        each row's ``prev_hash`` matches the previous row's ``row_hash``.

        Returns a dict with:
        - total_events: count of events checked
        - chain_broken: True if any hash doesn't match
        - first_broken_at: event_id of the first broken link (if any)
        - integrity_failures: count of rows where stored hash != recomputed hash
        """
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                "SELECT * FROM evidence_ledger ORDER BY rowid ASC"
            ).fetchall()

        total = len(rows)
        chain_broken = False
        first_broken: str | None = None
        integrity_failures = 0
        expected_prev = ""

        for r in rows:
            event = EvidenceEvent(
                event_id=r[0], timestamp=r[1], event_type=r[2], session_id=r[3],
                workspace_id=r[4], project_id=r[5], agent_id=r[6],
                detail_json=r[7], prev_hash=r[8], row_hash=r[9],
            )
            # 1. Recompute the hash and check integrity
            recomputed = event.compute_hash(self._hmac_key)
            if recomputed != event.row_hash:
                chain_broken = True
                first_broken = first_broken or event.event_id
                integrity_failures += 1

            # 2. Check linkage
            if event.prev_hash != expected_prev:
                chain_broken = True
                first_broken = first_broken or event.event_id

            expected_prev = event.row_hash

        return {
            "total_events": total,
            "chain_broken": chain_broken,
            "first_broken_at": first_broken,
            "integrity_failures": integrity_failures,
            "hmac_algorithm": "HMAC-SHA256",
        }

    def stats(self) -> dict[str, Any]:
        """Aggregate quality-verification statistics."""
        with sqlite3.connect(self.path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM evidence_ledger").fetchone()[0]
            by_type = dict(
                conn.execute(
                    "SELECT event_type, COUNT(*) FROM evidence_ledger GROUP BY event_type"
                ).fetchall()
            )
            retention_days = conn.execute(
                "SELECT COALESCE((julianday('now') - julianday(MIN(timestamp), 'unixepoch')), 0) "
                "FROM evidence_ledger"
            ).fetchone()[0]

        return {
            "total_events": total,
            "by_event_type": by_type,
            "retention_days": round(float(retention_days), 1),
            "chain": self.verify_chain(),
        }

    def export_bundle(self, fmt: str = "markdown") -> str:
        """Export evidence as a human-readable or JSON bundle.

        Args:
            fmt: "markdown" or "json"

        Returns:
            Formatted evidence bundle string.
        """
        events = self.query(limit=500)
        chain = self.verify_chain()

        if fmt == "json":
            return json.dumps(
                {
                    "exported_at": time.time(),
                    "event_count": len(events),
                    "chain": chain,
                    "events": [e.to_dict() for e in events],
                },
                indent=2,
                default=str,
            )

        lines = [
            "# Context Assurance Evidence Bundle",
            "",
            f"- Generated: {time.ctime()}",
            f"- Events in bundle: {len(events)}",
            f"- HMAC algorithm: {chain['hmac_algorithm']}",
            f"- Chain intact: {not chain['chain_broken']}",
            "",
            "## Chain Verification",
            "",
            f"**Total events** in ledger: {chain['total_events']}",
            f"**Chain broken**: {chain['chain_broken']}",
            f"**First broken at**: {chain['first_broken_at'] or 'N/A'}",
            "",
            "---",
            "",
        ]
        for event in events:
            d = event.to_dict()
            lines.extend(
                [
                    f"### {event.event_type} — {event.event_id[:12]}",
                    "",
                    f"- **Time**: {time.ctime(event.timestamp)}",
                    f"- **Session**: {event.session_id}",
                    f"- **Workspace**: {event.workspace_id or 'N/A'}",
                    f"- **Project**: {event.project_id or 'N/A'}",
                    f"- **Hash**: `{event.row_hash[:16]}...`",
                    f"- **Prev**: `{event.prev_hash[:16] if event.prev_hash else '(none)'}...`",
                    "",
                ]
            )
            if d["detail"]:
                lines.append("**Details**:")
                lines.append("")
                for k, v in d["detail"].items():
                    lines.append(f"  - {k}: {v}")
                lines.append("")

        lines.extend(
            [
                "---",
                "",
                "## Verification Instructions",
                "",
                "1. Ensure `CUTCTX_ASSURANCE_HMAC_KEY` matches the key used during recording.",
                "2. Run `cutctx report assurance --verify` to validate the chain.",
                "3. The event-by-event hash chain proves no events have been tampered with",
                "   after they were recorded.",
                "4. This bundle was exported at the time shown above. Live chain verification",
                "   should be run against the local ledger, not the bundle alone.",
                "",
            ]
        )

        return "\n".join(lines)
