"""Tests for RBAC system (headroom/rbac.py)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from headroom.rbac import (
    AdminRole,
    PERMISSION_MAP,
    ROLE_HIERARCHY,
    RbacChecker,
    get_rbac_checker,
    reset_rbac_checker,
)


# ---------------------------------------------------------------------------
# AdminRole
# ---------------------------------------------------------------------------


class TestAdminRole:
    def test_enum_values(self):
        assert AdminRole.VIEWER.value == "viewer"
        assert AdminRole.OPERATOR.value == "operator"
        assert AdminRole.ADMIN.value == "admin"

    def test_ordering(self):
        assert ROLE_HIERARCHY[AdminRole.VIEWER] < ROLE_HIERARCHY[AdminRole.OPERATOR]
        assert ROLE_HIERARCHY[AdminRole.OPERATOR] < ROLE_HIERARCHY[AdminRole.ADMIN]

    def test_permission_map_has_entries(self):
        assert len(PERMISSION_MAP) >= 15


# ---------------------------------------------------------------------------
# RbacChecker
# ---------------------------------------------------------------------------


class TestRbacChecker:
    def test_resolve_role_explicit_header(self):
        checker = RbacChecker()
        request = MagicMock()
        request.headers = {"x-headroom-role": "operator"}
        role = checker.resolve_role(request)
        assert role == AdminRole.OPERATOR

    def test_resolve_role_invalid_header_falls_back(self):
        checker = RbacChecker()
        request = MagicMock()
        request.headers = {"x-headroom-role": "invalid_role"}
        role = checker.resolve_role(request)
        assert role == AdminRole.ADMIN  # default

    def test_resolve_role_user_id_assignment(self):
        checker = RbacChecker()
        checker.assign_role("user123", AdminRole.VIEWER)
        request = MagicMock()
        request.headers = {"x-headroom-user-id": "user123"}
        role = checker.resolve_role(request)
        assert role == AdminRole.VIEWER

    def test_resolve_role_default_admin(self):
        checker = RbacChecker()
        request = MagicMock()
        request.headers = {}
        role = checker.resolve_role(request)
        assert role == AdminRole.ADMIN

    def test_has_permission_viewer_stats(self):
        checker = RbacChecker()
        assert checker.has_permission(AdminRole.VIEWER, "stats.read") is True

    def test_has_permission_viewer_denied_write(self):
        checker = RbacChecker()
        assert checker.has_permission(AdminRole.VIEWER, "stats.reset") is False

    def test_has_permission_operator_cache_write(self):
        checker = RbacChecker()
        assert checker.has_permission(AdminRole.OPERATOR, "cache.write") is True

    def test_has_permission_operator_denied_org_write(self):
        checker = RbacChecker()
        assert checker.has_permission(AdminRole.OPERATOR, "orgs.write") is False

    def test_has_permission_admin_all(self):
        checker = RbacChecker()
        for perm in PERMISSION_MAP:
            assert checker.has_permission(AdminRole.ADMIN, perm) is True

    def test_check_permission_raises_on_deny(self):
        from fastapi import HTTPException

        checker = RbacChecker()
        with pytest.raises(HTTPException) as exc_info:
            checker.check_permission(AdminRole.VIEWER, "stats.reset")
        assert exc_info.value.status_code == 403
        detail = exc_info.value.detail
        assert detail["error"] == "insufficient_permissions"
        assert detail["role"] == "viewer"

    def test_check_permission_passes(self):
        checker = RbacChecker()
        # Should not raise
        checker.check_permission(AdminRole.ADMIN, "stats.reset")

    def test_assign_and_revoke(self):
        checker = RbacChecker()
        checker.assign_role("user1", AdminRole.OPERATOR)
        assert "user1" in checker.list_assignments()
        assert checker.revoke_role("user1") is True
        assert "user1" not in checker.list_assignments()
        assert checker.revoke_role("user1") is False

    def test_list_assignments(self):
        checker = RbacChecker()
        checker.assign_role("a", AdminRole.VIEWER)
        checker.assign_role("b", AdminRole.ADMIN)
        assignments = checker.list_assignments()
        assert assignments == {"a": "viewer", "b": "admin"}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestGlobalSingleton:
    def test_get_creates_default(self):
        reset_rbac_checker()
        checker = get_rbac_checker()
        assert isinstance(checker, RbacChecker)
        reset_rbac_checker()

    def test_reset_clears(self):
        reset_rbac_checker()
        c1 = get_rbac_checker()
        reset_rbac_checker()
        c2 = get_rbac_checker()
        assert c1 is not c2
        reset_rbac_checker()
