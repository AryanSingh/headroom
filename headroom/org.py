"""Organization, workspace, and project data model.

Provides the canonical entity hierarchy for enterprise multi-tenant usage:

    Organization > Workspace > Project > Agent

Each entity has a stable ID, display name, and metadata. Storage is
SQLite-backed with WAL mode for concurrent reads.

Enterprise feature — some features gated on entitlement_tier.

Usage:
    from headroom.org import OrgStore

    store = OrgStore(db_path="/path/to/org.db")
    org = store.create_org(name="Acme Corp", admin_email="admin@acme.com")
    ws = store.create_workspace(org_id=org["id"], name="Engineering")
    proj = store.create_project(workspace_id=ws["id"], name="backend-api")
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from headroom import paths as _paths

logger = logging.getLogger("headroom.org")

ORG_DB_ENV = "HEADROOM_ORG_DB_PATH"

# Defense-in-depth: validate SQL column names match safe identifier pattern.
# Column names come from hardcoded `allowed` sets, but this guard prevents
# accidental injection if the allowlist is ever extended carelessly.
_SAFE_COL_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _validate_col_name(name: str) -> str:
    """Validate that a column name is a safe SQL identifier."""
    if not _SAFE_COL_RE.match(name):
        raise ValueError(f"Invalid SQL column name: {name!r}")
    return name


def _generate_id() -> str:
    """Generate a compact unique ID (16 hex chars)."""
    return uuid.uuid4().hex[:16]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrgStore:
    """SQLite-backed store for organizations, workspaces, projects, and agents.

    Thread-safe via a threading lock. Connections are thread-local.
    All mutations are idempotent where possible.
    """

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = os.environ.get(ORG_DB_ENV, "")
        if not db_path:
            db_path = str(_paths.workspace_dir() / "org.db")
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
            CREATE TABLE IF NOT EXISTS organizations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT UNIQUE,
                admin_email TEXT,
                settings TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                name TEXT NOT NULL,
                slug TEXT,
                settings TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (org_id) REFERENCES organizations(id)
            );

            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                name TEXT NOT NULL,
                slug TEXT,
                path TEXT,
                settings TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            );

            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                agent_type TEXT,
                settings TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );

            CREATE INDEX IF NOT EXISTS idx_ws_org ON workspaces(org_id);
            CREATE INDEX IF NOT EXISTS idx_proj_ws ON projects(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_agent_proj ON agents(project_id);
            """
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Organizations
    # ------------------------------------------------------------------

    def create_org(
        self,
        name: str,
        admin_email: str | None = None,
        slug: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new organization."""
        now = _now_iso()
        org_id = _generate_id()
        slug = slug or name.lower().replace(" ", "-")[:32]
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO organizations
                   (id, name, slug, admin_email, settings, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (org_id, name, slug, admin_email, json.dumps(settings or {}), now, now),
            )
            conn.commit()
        logger.info("Created organization: id=%s name=%s", org_id, name)
        return self.get_org(org_id)  # type: ignore[return-value]

    def get_org(self, org_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def list_orgs(self) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM organizations ORDER BY created_at").fetchall()
        return [self._row_to_dict(r) for r in rows]

    def update_org(self, org_id: str, **kwargs: Any) -> dict[str, Any] | None:
        """Update organization fields."""
        allowed = {"name", "slug", "admin_email", "settings"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return self.get_org(org_id)
        if "settings" in updates and isinstance(updates["settings"], dict):
            updates["settings"] = json.dumps(updates["settings"])
        updates["updated_at"] = _now_iso()
        set_clause = ", ".join(f"{_validate_col_name(k)} = ?" for k in updates)
        values = list(updates.values()) + [org_id]
        with self._lock:
            conn = self._get_conn()
            conn.execute(f"UPDATE organizations SET {set_clause} WHERE id = ?", values)
            conn.commit()
        return self.get_org(org_id)

    def delete_org(self, org_id: str) -> bool:
        """Delete org and all child workspaces/projects/agents (cascade)."""
        with self._lock:
            conn = self._get_conn()
            # Cascade: agents -> projects -> workspaces -> org
            ws_ids = [
                r["id"]
                for r in conn.execute(
                    "SELECT id FROM workspaces WHERE org_id = ?", (org_id,)
                ).fetchall()
            ]
            for ws_id in ws_ids:
                proj_ids = [
                    r["id"]
                    for r in conn.execute(
                        "SELECT id FROM projects WHERE workspace_id = ?", (ws_id,)
                    ).fetchall()
                ]
                for proj_id in proj_ids:
                    conn.execute("DELETE FROM agents WHERE project_id = ?", (proj_id,))
                conn.execute("DELETE FROM projects WHERE workspace_id = ?", (ws_id,))
            conn.execute("DELETE FROM workspaces WHERE org_id = ?", (org_id,))
            result = conn.execute("DELETE FROM organizations WHERE id = ?", (org_id,))
            conn.commit()
            return result.rowcount > 0

    # ------------------------------------------------------------------
    # Workspaces
    # ------------------------------------------------------------------

    def create_workspace(
        self,
        org_id: str,
        name: str,
        slug: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = _now_iso()
        ws_id = _generate_id()
        slug = slug or name.lower().replace(" ", "-")[:32]
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO workspaces
                   (id, org_id, name, slug, settings, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (ws_id, org_id, name, slug, json.dumps(settings or {}), now, now),
            )
            conn.commit()
        logger.info("Created workspace: id=%s org=%s name=%s", ws_id, org_id, name)
        return self.get_workspace(ws_id)  # type: ignore[return-value]

    def get_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM workspaces WHERE id = ?", (workspace_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_workspaces(self, org_id: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM workspaces WHERE org_id = ? ORDER BY created_at", (org_id,)
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def update_workspace(self, workspace_id: str, **kwargs: Any) -> dict[str, Any] | None:
        allowed = {"name", "slug", "settings"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return self.get_workspace(workspace_id)
        if "settings" in updates and isinstance(updates["settings"], dict):
            updates["settings"] = json.dumps(updates["settings"])
        updates["updated_at"] = _now_iso()
        set_clause = ", ".join(f"{_validate_col_name(k)} = ?" for k in updates)
        values = list(updates.values()) + [workspace_id]
        with self._lock:
            conn = self._get_conn()
            conn.execute(f"UPDATE workspaces SET {set_clause} WHERE id = ?", values)
            conn.commit()
        return self.get_workspace(workspace_id)

    def delete_workspace(self, workspace_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            proj_ids = [
                r["id"]
                for r in conn.execute(
                    "SELECT id FROM projects WHERE workspace_id = ?", (workspace_id,)
                ).fetchall()
            ]
            for proj_id in proj_ids:
                conn.execute("DELETE FROM agents WHERE project_id = ?", (proj_id,))
            conn.execute("DELETE FROM projects WHERE workspace_id = ?", (workspace_id,))
            result = conn.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
            conn.commit()
            return result.rowcount > 0

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def create_project(
        self,
        workspace_id: str,
        name: str,
        slug: str | None = None,
        path: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = _now_iso()
        proj_id = _generate_id()
        slug = slug or name.lower().replace(" ", "-")[:32]
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO projects
                   (id, workspace_id, name, slug, path, settings, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (proj_id, workspace_id, name, slug, path, json.dumps(settings or {}), now, now),
            )
            conn.commit()
        logger.info("Created project: id=%s ws=%s name=%s", proj_id, workspace_id, name)
        return self.get_project(proj_id)  # type: ignore[return-value]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_projects(self, workspace_id: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM projects WHERE workspace_id = ? ORDER BY created_at",
            (workspace_id,),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def update_project(self, project_id: str, **kwargs: Any) -> dict[str, Any] | None:
        allowed = {"name", "slug", "path", "settings"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return self.get_project(project_id)
        if "settings" in updates and isinstance(updates["settings"], dict):
            updates["settings"] = json.dumps(updates["settings"])
        updates["updated_at"] = _now_iso()
        set_clause = ", ".join(f"{_validate_col_name(k)} = ?" for k in updates)
        values = list(updates.values()) + [project_id]
        with self._lock:
            conn = self._get_conn()
            conn.execute(f"UPDATE projects SET {set_clause} WHERE id = ?", values)
            conn.commit()
        return self.get_project(project_id)

    def delete_project(self, project_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM agents WHERE project_id = ?", (project_id,))
            result = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            return result.rowcount > 0

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    def create_agent(
        self,
        project_id: str,
        name: str,
        agent_type: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = _now_iso()
        agent_id = _generate_id()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO agents
                   (id, project_id, name, agent_type, settings, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (agent_id, project_id, name, agent_type, json.dumps(settings or {}), now, now),
            )
            conn.commit()
        logger.info("Created agent: id=%s proj=%s name=%s", agent_id, project_id, name)
        return self.get_agent(agent_id)  # type: ignore[return-value]

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_agents(self, project_id: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM agents WHERE project_id = ? ORDER BY created_at",
            (project_id,),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def delete_agent(self, agent_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            result = conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
            conn.commit()
            return result.rowcount > 0

    # ------------------------------------------------------------------
    # Hierarchy lookups
    # ------------------------------------------------------------------

    def get_org_hierarchy(self, org_id: str) -> dict[str, Any] | None:
        """Get full org tree: org > workspaces > projects > agents."""
        org = self.get_org(org_id)
        if not org:
            return None

        workspaces = self.list_workspaces(org_id)
        for ws in workspaces:
            projects = self.list_projects(ws["id"])
            for proj in projects:
                proj["agents"] = self.list_agents(proj["id"])
            ws["projects"] = projects
        org["workspaces"] = workspaces
        return org

    def resolve_project(self, project_id: str) -> dict[str, Any] | None:
        """Resolve full hierarchy path for a project."""
        proj = self.get_project(project_id)
        if not proj:
            return None
        ws = self.get_workspace(proj["workspace_id"])
        org = self.get_org(ws["org_id"]) if ws else None
        return {
            "project": proj,
            "workspace": ws,
            "organization": org,
        }

    def find_project_by_path(self, path: str) -> dict[str, Any] | None:
        """Find a project by filesystem path."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM projects WHERE path = ?", (path,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        # Parse JSON settings
        if "settings" in d and isinstance(d["settings"], str):
            try:
                d["settings"] = json.loads(d["settings"])
            except (json.JSONDecodeError, TypeError):
                d["settings"] = {}
        return d

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_global_store: OrgStore | None = None
_global_lock = threading.Lock()


def get_org_store(db_path: str | Path | None = None) -> OrgStore:
    """Get or create the global org store singleton."""
    global _global_store
    if _global_store is None:
        with _global_lock:
            if _global_store is None:
                _global_store = OrgStore(db_path=db_path)
    return _global_store


def reset_org_store() -> None:
    """Reset the global singleton (for testing)."""
    global _global_store
    with _global_lock:
        if _global_store is not None:
            _global_store.close()
            _global_store = None
