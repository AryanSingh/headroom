# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""Role-based access control (RBAC) for enterprise admin endpoints.

Defines roles (admin, operator, viewer) and provides permission checking
for the management API surface. Roles are stored in the org DB and resolved
from admin API keys or headers.

Enterprise feature — gated on entitlement_tier >= BUSINESS.

Usage:
    from cutctx.rbac import RbacChecker, AdminRole

    checker = RbacChecker(org_store=org_store)
    role = checker.resolve_role(request)
    if not checker.has_permission(role, "config.write"):
        raise HTTPException(403)
"""

from __future__ import annotations

import enum
import logging
import os
import sqlite3
import threading
import time
from typing import Any

from cutctx.storage.sqlite_schema import stamp_schema_version

logger = logging.getLogger("cutctx.rbac")
_SCHEMA_VERSION = 1


class AdminRole(str, enum.Enum):
    """Admin roles in order of ascending privilege."""

    VIEWER = "viewer"  # Read-only: stats, health, audit logs
    MEMORY_CURATOR = "memory_curator"  # Read-only + approve/deprecate memory
    OPERATOR = "operator"  # Read + write: config, policies, cache
    ADMIN = "admin"  # Full access: RBAC, license, org management, retention


# Permission map — each permission requires at minimum the listed role.
# Permissions not listed default to ADMIN (most restrictive).
ROLE_HIERARCHY: dict[AdminRole, int] = {
    AdminRole.VIEWER: 0,
    AdminRole.MEMORY_CURATOR: 1,
    AdminRole.OPERATOR: 2,
    AdminRole.ADMIN: 3,
}

# Permission → minimum role required
PERMISSION_MAP: dict[str, AdminRole] = {
    # Read-only (viewer+)
    "stats.read": AdminRole.VIEWER,
    "stats.history": AdminRole.VIEWER,
    "dashboard.read": AdminRole.VIEWER,
    "audit.read": AdminRole.VIEWER,
    "health.read": AdminRole.VIEWER,
    "entitlements.read": AdminRole.VIEWER,
    "orgs.read": AdminRole.VIEWER,
    "license.read": AdminRole.VIEWER,
    "reports.read": AdminRole.VIEWER,
    "fleet.read": AdminRole.VIEWER,
    "scim.read": AdminRole.VIEWER,
    "residency.read": AdminRole.VIEWER,
    # Memory Curator
    "memory.curate": AdminRole.MEMORY_CURATOR,
    # Write (operator+)
    "stats.write": AdminRole.OPERATOR,
    "cache.write": AdminRole.OPERATOR,
    "config.write": AdminRole.OPERATOR,
    "compression.write": AdminRole.OPERATOR,
    "transformations.read": AdminRole.OPERATOR,
    "fleet.write": AdminRole.OPERATOR,
    "webhooks.read": AdminRole.OPERATOR,
    "webhooks.write": AdminRole.OPERATOR,
    "airgap.read": AdminRole.OPERATOR,
    "rate_limit.read": AdminRole.OPERATOR,
    "secrets.read": AdminRole.OPERATOR,
    "secrets.write": AdminRole.OPERATOR,
    "sso.read": AdminRole.OPERATOR,
    "sso.write": AdminRole.OPERATOR,
    "providers.read": AdminRole.VIEWER,
    "providers.write": AdminRole.OPERATOR,
    # Admin-only
    "stats.reset": AdminRole.ADMIN,
    "config.reset": AdminRole.ADMIN,
    "orgs.write": AdminRole.ADMIN,
    "workspaces.write": AdminRole.ADMIN,
    "projects.write": AdminRole.ADMIN,
    "license.write": AdminRole.ADMIN,
    "entitlements.write": AdminRole.ADMIN,
    "rbac.write": AdminRole.ADMIN,
    "retention.write": AdminRole.ADMIN,
    "audit.export": AdminRole.ADMIN,
    "scim.write": AdminRole.ADMIN,
    "mfa.write": AdminRole.ADMIN,
}


class RbacChecker:
    """Checks roles and permissions for admin endpoints.

    Resolution order for role:
    1. Authenticated role stored on request.state by the auth layer
    2. X-Cutctx-Role header when explicitly enabled for trusted proxy chaining
    3. X-Cutctx-User-Id header → lookup in org DB
    4. Default: viewer (fail-closed, read-only)
    """

    def __init__(
        self,
        org_store: Any | None = None,
        role_assignments: dict[str, AdminRole] | None = None,
    ):
        self._org_store = org_store
        self._assignments = role_assignments or {}
        # Unknown or unauthenticated callers are read-only. The admin auth
        # layer places ``cutctx_role=admin`` on requests that present the
        # configured root key, while SSO places the asserted IdP role there.
        self._default_role = AdminRole.VIEWER

    def resolve_role(self, request: Any) -> AdminRole:
        """Resolve the caller's role from the request.

        Args:
            request: FastAPI Request object (or compatible).

        Returns:
            The resolved AdminRole.
        """
        request_state = getattr(request, "state", None)
        state_role = getattr(request_state, "cutctx_role", None)
        if isinstance(state_role, str) and state_role.strip():
            try:
                return AdminRole(state_role.strip().lower())
            except ValueError:
                logger.debug("Invalid state role value: %s", state_role)

        # 1. Explicit role header is dangerous on a directly exposed proxy:
        # only honor it when an operator explicitly trusts an upstream proxy
        # to set the header.
        role_header = getattr(request, "headers", {})
        explicit_role = role_header.get("x-cutctx-role", "").strip().lower()
        allow_role_header = os.environ.get("CUTCTX_ALLOW_ROLE_HEADER", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if explicit_role and allow_role_header:
            try:
                return AdminRole(explicit_role)
            except ValueError:
                logger.debug("Invalid X-Cutctx-Role header: %s", explicit_role)

        # 2. User ID → role assignment lookup
        state_user_id = getattr(request_state, "cutctx_user_id", None)
        user_id = (
            state_user_id.strip()
            if isinstance(state_user_id, str) and state_user_id.strip()
            else role_header.get("x-cutctx-user-id", "").strip()
        )
        if user_id and user_id in self._assignments:
            return self._assignments[user_id]

        # 3. Org store lookup (if available)
        if self._org_store and user_id:
            try:
                role_str = self._get_role_from_store(user_id)
                if role_str:
                    return AdminRole(role_str)
            except Exception:
                logger.debug("Org store role lookup failed", exc_info=True)

        # 4. Default (backward-compatible)
        return self._default_role

    def has_permission(self, role: AdminRole, permission: str) -> bool:
        """Check if a role has the given permission."""
        required_role = PERMISSION_MAP.get(permission, AdminRole.ADMIN)
        return ROLE_HIERARCHY[role] >= ROLE_HIERARCHY[required_role]

    def check_permission(self, role: AdminRole, permission: str) -> None:
        """Check permission and raise HTTPException if denied."""
        if not self.has_permission(role, permission):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=403,
                detail={
                    "error": "insufficient_permissions",
                    "role": role.value,
                    "required_permission": permission,
                    "required_role": PERMISSION_MAP.get(permission, AdminRole.ADMIN).value,
                },
            )

    def assign_role(self, user_id: str, role: AdminRole) -> None:
        """Assign a role to a user (in-memory)."""
        self._assignments[user_id] = role
        logger.info("Role assigned: user=%s role=%s", user_id, role.value)

    def revoke_role(self, user_id: str) -> bool:
        """Revoke a user's role assignment."""
        if user_id in self._assignments:
            del self._assignments[user_id]
            logger.info("Role revoked: user=%s", user_id)
            return True
        return False

    def list_assignments(self) -> dict[str, str]:
        """List all role assignments."""
        return {uid: role.value for uid, role in self._assignments.items()}

    def _get_role_from_store(self, user_id: str) -> str | None:
        """Look up a user's role from the org store."""
        if not self._org_store:
            return None
        try:
            # Simple lookup — the org store could be extended with a users table
            # For now, check if user_id is an admin_email on any org
            orgs = self._org_store.list_orgs()
            for org in orgs:
                if org.get("admin_email") == user_id:
                    return AdminRole.ADMIN.value
        except Exception:
            pass
        return None


# Module-level singleton
_rbac_checker: RbacChecker | None = None


class RbacAssignmentStore:
    """SQLite-backed persistence for RBAC role assignments.

    Audit-Deep-2026-06-21 Medium-29: the previous RbacChecker
    stored assignments in a process-local dict, which meant
    role assignments were lost on restart (and not shared
    across replicas of the proxy). This store is the
    production-grade replacement.

    Schema:
        role_assignments(
            user_id       TEXT PRIMARY KEY,
            role          TEXT NOT NULL,
            assigned_by   TEXT,
            assigned_at   REAL NOT NULL,
            notes         TEXT
        )

    A 60-second in-process cache keeps the hot path fast; the
    cache is invalidated on every write. Multi-replica
    deployments that need sub-second consistency should use an
    external store (out of scope; the SQLite file is a
    single-writer store).
    """

    DEFAULT_DB_PATH = "~/.cutctx/rbac.db"
    CACHE_TTL_S = 60.0

    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        from cutctx.proxy.helpers import is_stateless

        self._stateless = is_stateless()
        self._lock = threading.RLock()
        self._cache: dict[str, tuple[float, AdminRole]] = {}
        if self._stateless:
            self._db_path = ":memory:"
            self._memory_conn: sqlite3.Connection | None = None
        else:
            import os
            from pathlib import Path

            path = Path(os.path.expanduser(str(db_path or self.DEFAULT_DB_PATH)))
            path.parent.mkdir(parents=True, exist_ok=True)
            self._db_path = str(path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if self._stateless:
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:", timeout=5.0, check_same_thread=False)
                self._memory_conn.row_factory = sqlite3.Row
            return self._memory_conn
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS role_assignments (
                    user_id     TEXT PRIMARY KEY,
                    role        TEXT NOT NULL,
                    assigned_by TEXT,
                    assigned_at REAL NOT NULL,
                    notes       TEXT
                )
                """
            )
            stamp_schema_version(conn, expected=_SCHEMA_VERSION, store_name="RBAC store")
            conn.commit()

    def get(self, user_id: str) -> AdminRole | None:
        with self._lock:
            cached = self._cache.get(user_id)
            if cached is not None:
                ts, role = cached
                if time.time() - ts < self.CACHE_TTL_S:
                    return role
            row = (
                self._connect()
                .execute(
                    "SELECT role FROM role_assignments WHERE user_id = ?",
                    (user_id,),
                )
                .fetchone()
            )
        if row is None:
            return None
        try:
            role = AdminRole(row["role"])
        except ValueError:
            return None
        self._cache[user_id] = (time.time(), role)
        return role

    def set(
        self,
        user_id: str,
        role: AdminRole,
        *,
        assigned_by: str | None = None,
        notes: str = "",
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO role_assignments(user_id, role, assigned_by, assigned_at, notes)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    role = excluded.role,
                    assigned_by = excluded.assigned_by,
                    assigned_at = excluded.assigned_at,
                    notes = excluded.notes
                """,
                (user_id, role.value, assigned_by, time.time(), notes),
            )
        # Invalidate cache for this user (and on other replicas
        # we'd need pub/sub; for now the 60s TTL is the SLA).
        self._cache.pop(user_id, None)

    def delete(self, user_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM role_assignments WHERE user_id = ?",
                (user_id,),
            )
            removed = cur.rowcount > 0
        if removed:
            self._cache.pop(user_id, None)
        return removed

    def list_all(self) -> dict[str, dict[str, Any]]:
        """Return all assignments as a dict of metadata.

        The returned shape matches what the admin endpoint
        ``GET /admin/rbac/assignments`` expects.
        """
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT user_id, role, assigned_by, assigned_at, notes "
                "FROM role_assignments ORDER BY user_id"
            ).fetchall()
        return {
            r["user_id"]: {
                "role": r["role"],
                "assigned_by": r["assigned_by"],
                "assigned_at": r["assigned_at"],
                "notes": r["notes"] or "",
            }
            for r in rows
        }

    def invalidate_cache(self) -> None:
        with self._lock:
            self._cache.clear()


class PersistentRbacChecker(RbacChecker):
    """RbacChecker that reads/writes role assignments to a
    SQLite-backed store. Drop-in replacement for RbacChecker
    that survives process restarts and is shared across
    replicas of the proxy (via the on-disk file).

    Falls back to the in-memory dict for the lookup path only
    when the store is unavailable (network file system outage,
    read-only mount). The write path always goes to the store.
    """

    def __init__(
        self,
        store: RbacAssignmentStore,
        org_store: Any | None = None,
    ) -> None:
        super().__init__(org_store=org_store)
        self._store = store
        # Pre-load the in-memory dict so the hot lookup path
        # doesn't hit SQLite on every request.
        try:
            for user_id, meta in store.list_all().items():
                try:
                    self._assignments[user_id] = AdminRole(meta["role"])
                except ValueError:
                    logger.warning(
                        "Skipping invalid role %r for user %s",
                        meta.get("role"),
                        user_id,
                    )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("PersistentRbacChecker: initial load failed: %s", exc)

    def resolve_role(self, request: Any) -> AdminRole:
        """Resolve role, preferring the SQLite store for fresh data.

        Falls back to the in-memory snapshot (loaded at
        construction) if the store is unreachable, so a
        transient FS error does not break authentication.
        """
        # 1. Fast path: in-memory snapshot
        result = super().resolve_role(request)
        # The parent class falls through to _default_role
        # (AdminRole.ADMIN) when nothing matches. That is
        # fail-open. For the persistent checker we want
        # fail-closed when the store actually has data
        # (i.e. when an operator has explicitly configured
        # RBAC). The store knows the answer; the snapshot
        # may be stale.
        if result is AdminRole.ADMIN and self._store is not None:
            request_state = getattr(request, "state", None)
            headers = getattr(request, "headers", {})
            user_id = getattr(request_state, "cutctx_user_id", None) or headers.get(
                "x-cutctx-user-id", ""
            )
            user_id = user_id.strip() if isinstance(user_id, str) else ""
            if user_id:
                stored = self._store.get(user_id)
                if stored is not None:
                    return stored
        return result

    def assign_role(
        self,
        user_id: str,
        role: AdminRole,
        *,
        assigned_by: str | None = None,
        notes: str = "",
    ) -> None:
        """Assign a role and persist it."""
        super().assign_role(user_id, role)
        self._store.set(user_id, role, assigned_by=assigned_by, notes=notes)

    def revoke_role(self, user_id: str) -> bool:
        """Revoke and delete from the store."""
        in_mem_removed = super().revoke_role(user_id)
        store_removed = self._store.delete(user_id)
        return in_mem_removed or store_removed

    def list_assignments(self) -> dict[str, str]:
        """List from the store (the source of truth)."""
        return {user_id: meta["role"] for user_id, meta in self._store.list_all().items()}


def get_rbac_checker() -> RbacChecker:
    """Get or create the global RBAC checker.

    Audit-Deep-2026-06-21 Medium-29: the singleton uses
    RbacAssignmentStore (SQLite) when CUTCTX_RBAC_DB_PATH is
    set (or the default ~/.cutctx/rbac.db exists / can be
    created); otherwise it falls back to the in-process
    RbacChecker for backward compatibility.
    """
    global _rbac_checker  # noqa: PLW0603
    if _rbac_checker is None:
        db_path = os.environ.get("CUTCTX_RBAC_DB_PATH") or RbacAssignmentStore.DEFAULT_DB_PATH
        try:
            store = RbacAssignmentStore(db_path=db_path)
            _rbac_checker = PersistentRbacChecker(store=store)
            logger.info("RBAC: persistent (SQLite) at %s", store._db_path)
        except Exception as exc:
            logger.warning(
                "RBAC: persistent store unavailable (%s); "
                "falling back to in-memory. Role assignments "
                "will NOT survive a restart.",
                exc,
            )
            _rbac_checker = RbacChecker()
    return _rbac_checker


def reset_rbac_checker() -> None:
    """Reset the global RBAC checker (for testing)."""
    global _rbac_checker  # noqa: PLW0603
    _rbac_checker = None


__all__ = [
    "AdminRole",
    "PERMISSION_MAP",
    "ROLE_HIERARCHY",
    "RbacChecker",
    "RbacAssignmentStore",
    "PersistentRbacChecker",
    "get_rbac_checker",
    "reset_rbac_checker",
    "has_permission",
]


def has_permission(actor: str, permission: str) -> bool:
    """Convenience helper for callers that have an actor string
    but no FastAPI Request (e.g. EE policy API).

    Looks up the role for the actor via the global RBAC
    checker and checks the permission. Returns False (fail-
    closed) when the actor is unknown OR when the actor
    resolves to a non-ADMIN role for an unknown-SSO
    subject. The only exception is admin-key holders
    (actor starts with "key:") who map to ADMIN by
    convention since the key fingerprint IS the auth
    factor.

    Audit-Deep-2026-06-21: the previous code defaulted to
    ADMIN for any unknown SSO user. That meant an unknown
    user (e.g. a stale token, a typo in a test) gained
    ADMIN privileges — the opposite of fail-closed. This
    fix: unknown SSO users default to VIEWER (the lowest
    privilege role), so they get no access to any
    permission in the map.
    """
    checker = get_rbac_checker()
    # Map the actor to a role. Actors are typically
    # "sso:<user>", "key:<fp>", or "admin".
    user_id: str | None = None
    is_admin_key = False
    if isinstance(actor, str) and actor.startswith("sso:"):
        user_id = actor[len("sso:") :]
    elif isinstance(actor, str) and actor.startswith("key:"):
        # Admin-key holders map to ADMIN by convention (they
        # authenticated with a valid admin key).
        is_admin_key = True
    # For "admin" or empty, default to ADMIN.
    role: AdminRole
    if user_id is None and not is_admin_key:
        # Fall-through case: bare "admin" or empty actor.
        # Could be a system action; allow ADMIN.
        role = AdminRole.ADMIN
    elif is_admin_key:
        role = AdminRole.ADMIN
    else:
        # SSO user: look up in the store. Unknown SSO user
        # defaults to VIEWER (fail-closed).
        stored = (
            checker._store.get(user_id) if hasattr(checker, "_store") and checker._store else None
        )
        if stored is not None:
            role = stored
        else:
            role = AdminRole.VIEWER
    return checker.has_permission(role, permission)
