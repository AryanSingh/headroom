"""Fleet registry for enterprise deployment inventory and heartbeat tracking."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cutctx import paths as _paths
from cutctx.storage.sqlite_schema import stamp_schema_version

FLEET_DB_ENV = "CUTCTX_FLEET_DB_PATH"
_STALE_SECONDS = 900
_SCHEMA_VERSION = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FleetStore:
    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = os.environ.get(FLEET_DB_ENV, "")
        if not db_path:
            from cutctx.proxy.helpers import is_stateless

            if is_stateless():
                db_path = ":memory:"
            else:
                db_path = str(_paths.workspace_dir() / "fleet.db")
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._local = threading.local()
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _ensure_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS deployments (
                deployment_id TEXT PRIMARY KEY,
                name TEXT,
                org_id TEXT,
                workspace_id TEXT,
                project_id TEXT,
                environment TEXT,
                region TEXT,
                version TEXT,
                status TEXT NOT NULL DEFAULT 'healthy',
                metadata TEXT NOT NULL DEFAULT '{}',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_deployments_org ON deployments(org_id);
            CREATE INDEX IF NOT EXISTS idx_deployments_workspace ON deployments(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);
            """
        )
        stamp_schema_version(conn, expected=_SCHEMA_VERSION, store_name="fleet registry")
        conn.commit()

    def upsert_heartbeat(
        self,
        *,
        deployment_id: str | None = None,
        name: str | None = None,
        org_id: str | None = None,
        workspace_id: str | None = None,
        project_id: str | None = None,
        environment: str | None = None,
        region: str | None = None,
        version: str | None = None,
        status: str = "healthy",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        deployment_id = deployment_id or uuid.uuid4().hex[:16]
        now = _now_iso()
        payload = json.dumps(metadata or {})
        with self._lock:
            conn = self._get_conn()
            existing = conn.execute(
                "SELECT first_seen_at FROM deployments WHERE deployment_id = ?",
                (deployment_id,),
            ).fetchone()
            first_seen = existing["first_seen_at"] if existing else now
            conn.execute(
                """
                INSERT INTO deployments (
                    deployment_id, name, org_id, workspace_id, project_id,
                    environment, region, version, status, metadata,
                    first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(deployment_id) DO UPDATE SET
                    name=excluded.name,
                    org_id=excluded.org_id,
                    workspace_id=excluded.workspace_id,
                    project_id=excluded.project_id,
                    environment=excluded.environment,
                    region=excluded.region,
                    version=excluded.version,
                    status=excluded.status,
                    metadata=excluded.metadata,
                    last_seen_at=excluded.last_seen_at
                """,
                (
                    deployment_id,
                    name,
                    org_id,
                    workspace_id,
                    project_id,
                    environment,
                    region,
                    version,
                    status,
                    payload,
                    first_seen,
                    now,
                ),
            )
            conn.commit()
        return self.get_deployment(deployment_id)  # type: ignore[return-value]

    def get_deployment(self, deployment_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM deployments WHERE deployment_id = ?",
            (deployment_id,),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_deployments(
        self,
        *,
        org_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if org_id:
            where.append("org_id = ?")
            params.append(org_id)
        if status:
            where.append("status = ?")
            params.append(status)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        conn = self._get_conn()
        rows = conn.execute(
            f"SELECT * FROM deployments {clause} ORDER BY last_seen_at DESC",
            params,
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def delete_deployment(self, deployment_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            result = conn.execute(
                "DELETE FROM deployments WHERE deployment_id = ?",
                (deployment_id,),
            )
            conn.commit()
            return result.rowcount > 0

    def summarize(self) -> dict[str, Any]:
        deployments = self.list_deployments()
        stale = 0
        status_counts: dict[str, int] = {}
        now = datetime.now(timezone.utc)
        for deployment in deployments:
            status = deployment.get("status") or "unknown"
            status_counts[status] = status_counts.get(status, 0) + 1
            try:
                seen = datetime.fromisoformat(deployment["last_seen_at"])
                if (now - seen).total_seconds() > _STALE_SECONDS:
                    stale += 1
            except Exception:
                stale += 1
        return {
            "total": len(deployments),
            "stale": stale,
            "healthy": status_counts.get("healthy", 0),
            "status_counts": status_counts,
        }

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        if isinstance(data.get("metadata"), str):
            try:
                data["metadata"] = json.loads(data["metadata"])
            except (TypeError, json.JSONDecodeError):
                data["metadata"] = {}
        return data

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None


_global_store: FleetStore | None = None
_global_lock = threading.Lock()


def get_fleet_store(db_path: str | Path | None = None) -> FleetStore:
    global _global_store
    if _global_store is None:
        with _global_lock:
            if _global_store is None:
                _global_store = FleetStore(db_path=db_path)
    return _global_store


def reset_fleet_store() -> None:
    global _global_store
    with _global_lock:
        if _global_store is not None:
            _global_store.close()
            _global_store = None
