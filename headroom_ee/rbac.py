# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Headroom Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""Role-based access control (RBAC) for enterprise admin endpoints.

Defines roles (admin, operator, viewer) and provides permission checking
for the management API surface. Roles are stored in the org DB and resolved
from admin API keys or headers.

Enterprise feature — gated on entitlement_tier >= BUSINESS.

Usage:
    from headroom.rbac import RbacChecker, AdminRole

    checker = RbacChecker(org_store=org_store)
    role = checker.resolve_role(request)
    if not checker.has_permission(role, "config.write"):
        raise HTTPException(403)
"""

from __future__ import annotations

import enum
import logging
from typing import Any

logger = logging.getLogger("headroom.rbac")


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
    # Memory Curator
    "memory.curate": AdminRole.MEMORY_CURATOR,
    # Write (operator+)
    "stats.write": AdminRole.OPERATOR,
    "cache.write": AdminRole.OPERATOR,
    "config.write": AdminRole.OPERATOR,
    "compression.write": AdminRole.OPERATOR,
    "transformations.read": AdminRole.OPERATOR,
    "fleet.write": AdminRole.OPERATOR,
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
}


class RbacChecker:
    """Checks roles and permissions for admin endpoints.

    Resolution order for role:
    1. X-Headroom-Role header (explicit override, for testing)
    2. X-Headroom-User-Id header → lookup in org DB
    3. Default: admin (backward-compatible when no RBAC configured)
    """

    def __init__(
        self,
        org_store: Any | None = None,
        role_assignments: dict[str, AdminRole] | None = None,
    ):
        self._org_store = org_store
        self._assignments = role_assignments or {}
        # Default role when no RBAC is configured (backward-compatible)
        self._default_role = AdminRole.ADMIN

    def resolve_role(self, request: Any) -> AdminRole:
        """Resolve the caller's role from the request.

        Args:
            request: FastAPI Request object (or compatible).

        Returns:
            The resolved AdminRole.
        """
        request_state = getattr(request, "state", None)
        state_role = getattr(request_state, "headroom_role", None)
        if isinstance(state_role, str) and state_role.strip():
            try:
                return AdminRole(state_role.strip().lower())
            except ValueError:
                logger.debug("Invalid state role value: %s", state_role)

        # 1. Explicit role header (testing / proxy chaining)
        role_header = getattr(request, "headers", {})
        explicit_role = role_header.get("x-headroom-role", "").strip().lower()
        if explicit_role:
            try:
                return AdminRole(explicit_role)
            except ValueError:
                logger.debug("Invalid X-Headroom-Role header: %s", explicit_role)

        # 2. User ID → role assignment lookup
        state_user_id = getattr(request_state, "headroom_user_id", None)
        user_id = (
            state_user_id.strip()
            if isinstance(state_user_id, str) and state_user_id.strip()
            else role_header.get("x-headroom-user-id", "").strip()
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


def get_rbac_checker() -> RbacChecker:
    """Get or create the global RBAC checker."""
    global _rbac_checker  # noqa: PLW0603
    if _rbac_checker is None:
        _rbac_checker = RbacChecker()
    return _rbac_checker


def reset_rbac_checker() -> None:
    """Reset the global RBAC checker (for testing)."""
    global _rbac_checker  # noqa: PLW0603
    _rbac_checker = None
