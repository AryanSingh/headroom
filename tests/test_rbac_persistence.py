# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Tests for RbacAssignmentStore and PersistentRbacChecker.

Audit-Deep-2026-06-21 Medium-29: the previous RbacChecker stored
role assignments in a process-local dict, which meant they
were lost on restart and not shared across replicas. These
tests pin the SQLite-backed store + drop-in PersistentRbacChecker
replacement.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_db(tmp_path: Path):
    """A fresh SQLite database for each test."""
    db = tmp_path / "rbac.db"
    yield str(db)
    # SQLite WAL files may linger; tmp_path cleanup handles them.


class TestRbacAssignmentStore:
    def test_empty_store_returns_none(self, tmp_db):
        from cutctx_ee.rbac import RbacAssignmentStore

        store = RbacAssignmentStore(db_path=tmp_db)
        assert store.get("alice") is None

    def test_set_then_get(self, tmp_db):
        from cutctx_ee.rbac import AdminRole, RbacAssignmentStore

        store = RbacAssignmentStore(db_path=tmp_db)
        store.set("alice", AdminRole.OPERATOR, assigned_by="admin")
        result = store.get("alice")
        assert result == AdminRole.OPERATOR

    def test_set_overwrites(self, tmp_db):
        from cutctx_ee.rbac import AdminRole, RbacAssignmentStore

        store = RbacAssignmentStore(db_path=tmp_db)
        store.set("alice", AdminRole.VIEWER)
        store.set("alice", AdminRole.ADMIN)
        assert store.get("alice") == AdminRole.ADMIN

    def test_delete_returns_true_when_present(self, tmp_db):
        from cutctx_ee.rbac import AdminRole, RbacAssignmentStore

        store = RbacAssignmentStore(db_path=tmp_db)
        store.set("alice", AdminRole.VIEWER)
        assert store.delete("alice") is True
        assert store.get("alice") is None

    def test_delete_returns_false_when_absent(self, tmp_db):
        from cutctx_ee.rbac import RbacAssignmentStore

        store = RbacAssignmentStore(db_path=tmp_db)
        assert store.delete("missing") is False

    def test_list_all(self, tmp_db):
        from cutctx_ee.rbac import AdminRole, RbacAssignmentStore

        store = RbacAssignmentStore(db_path=tmp_db)
        store.set("alice", AdminRole.OPERATOR, notes="first")
        store.set("bob", AdminRole.VIEWER, assigned_by="alice")
        listing = store.list_all()
        assert set(listing.keys()) == {"alice", "bob"}
        assert listing["alice"]["role"] == "operator"
        assert listing["alice"]["notes"] == "first"
        assert listing["bob"]["assigned_by"] == "alice"

    def test_persistence_across_instances(self, tmp_db):
        """The whole point: assignments survive a process restart."""
        from cutctx_ee.rbac import AdminRole, RbacAssignmentStore

        store1 = RbacAssignmentStore(db_path=tmp_db)
        store1.set("alice", AdminRole.OPERATOR)
        store1.set("bob", AdminRole.ADMIN)

        # Simulate restart: new instance, same DB file.
        store2 = RbacAssignmentStore(db_path=tmp_db)
        assert store2.get("alice") == AdminRole.OPERATOR
        assert store2.get("bob") == AdminRole.ADMIN
        assert set(store2.list_all().keys()) == {"alice", "bob"}

    def test_cache_invalidates_on_write(self, tmp_db):
        from cutctx_ee.rbac import AdminRole, RbacAssignmentStore

        store = RbacAssignmentStore(db_path=tmp_db)
        store.set("alice", AdminRole.VIEWER)
        # First read populates the cache
        assert store.get("alice") == AdminRole.VIEWER
        # Direct DB write (bypassing the store)
        import sqlite3

        with sqlite3.connect(tmp_db) as conn:
            conn.execute(
                "UPDATE role_assignments SET role = ? WHERE user_id = ?",
                ("admin", "alice"),
            )
        # Cache TTL is 60s, so the read still returns the cached VIEWER.
        # After invalidate_cache, the read picks up the DB value.
        store.invalidate_cache()
        assert store.get("alice") == AdminRole.ADMIN


class TestPersistentRbacChecker:
    def test_assign_role_persists(self, tmp_db):
        from cutctx_ee.rbac import (
            AdminRole,
            PersistentRbacChecker,
            RbacAssignmentStore,
        )

        store = RbacAssignmentStore(db_path=tmp_db)
        checker = PersistentRbacChecker(store=store)
        checker.assign_role("alice", AdminRole.OPERATOR, assigned_by="admin")
        # Re-open the store from the same DB file to verify
        # the assignment was persisted.
        fresh_store = RbacAssignmentStore(db_path=tmp_db)
        assert fresh_store.get("alice") == AdminRole.OPERATOR

    def test_revoke_role_removes_from_store(self, tmp_db):
        from cutctx_ee.rbac import (
            AdminRole,
            PersistentRbacChecker,
            RbacAssignmentStore,
        )

        store = RbacAssignmentStore(db_path=tmp_db)
        checker = PersistentRbacChecker(store=store)
        checker.assign_role("alice", AdminRole.VIEWER)
        assert checker.revoke_role("alice") is True
        assert store.get("alice") is None

    def test_list_assignments_from_store(self, tmp_db):
        from cutctx_ee.rbac import (
            AdminRole,
            PersistentRbacChecker,
            RbacAssignmentStore,
        )

        store = RbacAssignmentStore(db_path=tmp_db)
        checker = PersistentRbacChecker(store=store)
        checker.assign_role("alice", AdminRole.OPERATOR)
        checker.assign_role("bob", AdminRole.VIEWER)
        listing = checker.list_assignments()
        assert listing == {"alice": "operator", "bob": "viewer"}

    def test_persistent_checker_survives_restart(self, tmp_db):
        from cutctx_ee.rbac import (
            AdminRole,
            PersistentRbacChecker,
            RbacAssignmentStore,
        )

        store_a = RbacAssignmentStore(db_path=tmp_db)
        checker_a = PersistentRbacChecker(store=store_a)
        checker_a.assign_role("alice", AdminRole.OPERATOR)

        # Simulate restart: new instance.
        store_b = RbacAssignmentStore(db_path=tmp_db)
        checker_b = PersistentRbacChecker(store=store_b)
        # The new checker sees alice as OPERATOR (loaded at
        # construction from the DB).
        # We verify via the store, not via the in-memory snapshot,
        # because resolve_role's fast path uses the snapshot.
        assert store_b.get("alice") == AdminRole.OPERATOR
        assert checker_b.list_assignments() == {"alice": "operator"}


class TestHasPermissionHelper:
    def test_admin_key_actor_has_any_permission(self, tmp_db):
        from cutctx_ee.rbac import (
            PersistentRbacChecker,
            RbacAssignmentStore,
            has_permission,
            reset_rbac_checker,
        )

        store = RbacAssignmentStore(db_path=tmp_db)
        reset_rbac_checker()
        # Inject a checker that has the store
        import cutctx_ee.rbac as rbac_mod

        old = rbac_mod._rbac_checker
        rbac_mod._rbac_checker = PersistentRbacChecker(store=store)
        try:
            # An admin-key actor (no "sso:" prefix) maps to ADMIN
            # by convention. They can do anything.
            assert has_permission("key:abcd1234", "config.write") is True
            assert has_permission("admin", "rbac.write") is True
        finally:
            rbac_mod._rbac_checker = old
            reset_rbac_checker()

    def test_known_sso_user_resolves_role(self, tmp_db):
        from cutctx_ee.rbac import (
            AdminRole,
            PersistentRbacChecker,
            RbacAssignmentStore,
            has_permission,
            reset_rbac_checker,
        )

        store = RbacAssignmentStore(db_path=tmp_db)
        store.set("alice@corp", AdminRole.OPERATOR)
        reset_rbac_checker()
        import cutctx_ee.rbac as rbac_mod

        old = rbac_mod._rbac_checker
        rbac_mod._rbac_checker = PersistentRbacChecker(store=store)
        try:
            # alice is OPERATOR -> can write config, cannot
            # write rbac (admin-only).
            assert has_permission("sso:alice@corp", "config.write") is True
            assert has_permission("sso:alice@corp", "rbac.write") is False
        finally:
            rbac_mod._rbac_checker = old
            reset_rbac_checker()
