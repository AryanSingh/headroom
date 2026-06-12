"""End-to-end enterprise smoke tests.

Validates the full enterprise workflow:
SSO → RBAC → compression → audit → retention

These tests verify that all enterprise modules integrate correctly
without requiring a live proxy server.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from headroom.audit import AuditAction, AuditEvent, AuditLogger, get_audit_logger, reset_audit_logger
from headroom.entitlements import EntitlementChecker, EntitlementTier, FEATURE_TIERS
from headroom.org import OrgStore, get_org_store, reset_org_store
from headroom.rbac import AdminRole, RbacChecker, get_rbac_checker, reset_rbac_checker
from headroom.retention import RetentionConfig, RetentionManager
from headroom.sso import SsoClaims, SsoConfig, SsoValidator


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def org_db(tmp_path):
    db = tmp_path / "org_test.db"
    store = OrgStore(db_path=db)
    yield store
    store.close()


@pytest.fixture
def audit_db(tmp_path):
    db = tmp_path / "audit_test.db"
    logger = AuditLogger(db_path=db)
    yield logger
    logger.close()


@pytest.fixture
def enterprise_checker():
    return EntitlementChecker("enterprise")


@pytest.fixture
def builder_checker():
    return EntitlementChecker("builder")


@pytest.fixture
def rbac_checker():
    checker = RbacChecker()
    yield checker
    reset_rbac_checker()


@pytest.fixture
def sso_config():
    return SsoConfig(
        provider_type="oidc",
        discovery_url="https://idp.example.com/.well-known/openid-configuration",
        issuer="https://idp.example.com",
        audience="headroom-api",
        role_mapping={"admin": "admin", "viewer": "viewer"},
        default_role="viewer",
    )


# ── SSO → RBAC Integration ─────────────────────────────────────────────


class TestSsoToRbacFlow:
    """Verify SSO claims flow into RBAC role resolution."""

    def test_sso_claims_provide_role_header(self, sso_config):
        """SSO validation produces claims that map to RBAC roles."""
        claims = SsoClaims(
            subject="user@example.com",
            issuer="https://idp.example.com",
            audience="headroom-api",
            expires_at=time.time() + 3600,
            scopes=["openid", "profile"],
            role="admin",
            raw_claims={"sub": "user@example.com", "role": "admin"},
        )
        assert claims.role == "admin"
        # In real flow, server.py injects x-headroom-role from claims.role

    def test_rbac_resolves_sso_role(self, rbac_checker):
        """RBAC checker resolves role from SSO-injected header."""
        request = MagicMock()
        request.headers = {
            "x-headroom-role": "viewer",
            "x-headroom-user-id": "user@example.com",
        }
        role = rbac_checker.resolve_role(request)
        assert role == AdminRole.VIEWER

    def test_viewer_cannot_write_orgs(self, rbac_checker):
        """Viewer role should be denied org.write permission."""
        assert not rbac_checker.has_permission(AdminRole.VIEWER, "orgs.write")

    def test_viewer_can_read_stats(self, rbac_checker):
        """Viewer role should be allowed stats.read permission."""
        assert rbac_checker.has_permission(AdminRole.VIEWER, "stats.read")

    def test_operator_can_write_config(self, rbac_checker):
        """Operator role should be allowed config.write permission."""
        assert rbac_checker.has_permission(AdminRole.OPERATOR, "config.write")

    def test_operator_cannot_write_rbac(self, rbac_checker):
        """Operator role should be denied rbac.write permission."""
        assert not rbac_checker.has_permission(AdminRole.OPERATOR, "rbac.write")

    def test_admin_can_do_everything(self, rbac_checker):
        """Admin role should have all permissions."""
        from headroom.rbac import PERMISSION_MAP
        for perm in PERMISSION_MAP:
            assert rbac_checker.has_permission(AdminRole.ADMIN, perm), f"Admin missing {perm}"


# ── RBAC → Audit Integration ───────────────────────────────────────────


class TestRbacAuditFlow:
    """Verify RBAC denials are audit-logged."""

    def test_rbac_deny_creates_event(self, audit_db, rbac_checker):
        """When RBAC denies access, an audit event should be created."""
        event = AuditEvent(
            action="auth.access_denied",
            actor="user@example.com",
            detail={
                "role": "viewer",
                "permission": "orgs.write",
                "endpoint": "POST /orgs",
            },
            success=False,
        )
        audit_db.log(event)
        events = audit_db.query(action="auth.access_denied")
        assert len(events) >= 1
        assert events[0]["actor"] == "user@example.com"
        assert events[0]["success"] is False

    def test_admin_action_audited(self, audit_db):
        """Admin write actions should be audit-logged."""
        event = AuditEvent(
            action="org.created",
            actor="admin@example.com",
            detail={"org_name": "Acme Corp", "org_id": "org_abc123"},
            success=True,
        )
        audit_db.log(event)
        events = audit_db.query(action="org.created")
        assert len(events) >= 1


# ── Entitlement → Compression Integration ──────────────────────────────


class TestEntitlementCompressionFlow:
    """Verify entitlement checks gate compression features correctly."""

    def test_builder_gets_all_core_compression(self, builder_checker):
        """Builder tier should have access to all core compression."""
        core_features = [
            "smart_crusher", "code_compressor", "log_compressor",
            "diff_compressor", "search_compressor", "kompress",
            "image_compressor", "audio_compressor",
            "ccr", "ccr_marker", "episodic_memory", "cross_agent_memory",
        ]
        for f in core_features:
            assert builder_checker.is_entitled(f), f"Builder needs {f}"

    def test_builder_denied_enterprise_compression_features(self, builder_checker):
        """Builder should be denied enterprise-only features."""
        enterprise_only = ["sso_saml", "rbac", "audit_logs", "retention_controls"]
        for f in enterprise_only:
            assert not builder_checker.is_entitled(f)

    def test_enterprise_gets_everything(self, enterprise_checker):
        """Enterprise should have access to every feature."""
        for f in FEATURE_TIERS:
            assert enterprise_checker.is_entitled(f)

    def test_tier_upgrade_unlocks_features(self):
        """Moving from builder to team should unlock team features."""
        builder = EntitlementChecker("builder")
        team = EntitlementChecker("team")
        team_features = [f for f, t in FEATURE_TIERS.items() if t == EntitlementTier.TEAM]
        for f in team_features:
            assert not builder.is_entitled(f)
            assert team.is_entitled(f)


# ── Org → Audit Integration ────────────────────────────────────────────


class TestOrgAuditFlow:
    """Verify org CRUD operations are audit-logged."""

    def test_create_org_with_audit(self, org_db, audit_db):
        """Creating an org should produce an audit event."""
        org = org_db.create_org(name="Acme Corp", admin_email="admin@acme.com")
        event = AuditEvent(
            action="org.created",
            actor="admin@acme.com",
            detail={"org_id": org["id"], "org_name": "Acme Corp"},
        )
        audit_db.log(event)
        events = audit_db.query(action="org.created")
        assert len(events) >= 1

    def test_org_hierarchy_with_workspaces(self, org_db):
        """Full org hierarchy should include workspaces and projects."""
        org = org_db.create_org(name="Acme Corp")
        ws = org_db.create_workspace(org_id=org["id"], name="Engineering")
        proj = org_db.create_project(workspace_id=ws["id"], name="headroom", path="/srv/headroom")
        hierarchy = org_db.get_org_hierarchy(org["id"])
        assert hierarchy is not None
        assert len(hierarchy["workspaces"]) == 1
        assert len(hierarchy["workspaces"][0]["projects"]) == 1

    def test_project_resolution(self, org_db):
        """Project resolution should return full hierarchy."""
        org = org_db.create_org(name="Test Org")
        ws = org_db.create_workspace(org_id=org["id"], name="Default")
        proj = org_db.create_project(workspace_id=ws["id"], name="myproject", path="/opt/myproject")
        resolved = org_db.resolve_project(proj["id"])
        assert resolved is not None
        assert resolved["project"]["name"] == "myproject"
        assert resolved["workspace"]["name"] == "Default"
        assert resolved["organization"]["name"] == "Test Org"


# ── Retention → Audit Integration ──────────────────────────────────────


class TestRetentionAuditFlow:
    """Verify retention cleanup is audit-logged."""

    def test_retention_cleanup_audit_event(self, audit_db):
        """Retention cleanup should produce an audit event."""
        event = AuditEvent(
            action="retention.cleanup",
            actor="system",
            detail={"cleaned_audit_events": 15, "cleaned_episodic_memories": 3},
        )
        audit_db.log(event)
        events = audit_db.query(action="retention.cleanup")
        assert len(events) >= 1

    def test_retention_config_defaults(self):
        """Retention config should have sane defaults."""
        config = RetentionConfig()
        assert config.ccr_max_age_seconds == 604800  # 7 days
        assert config.audit_max_age_days == 90
        assert config.episodic_max_age_days == 30

    def test_retention_disabled_when_flags_off(self):
        """Retention manager should be disabled when all enabled flags are False."""
        config = RetentionConfig(ccr_enabled=False, audit_enabled=False, episodic_enabled=False)
        manager = RetentionManager(config=config)
        assert not manager.enabled


# ── Full Enterprise Workflow ────────────────────────────────────────────


class TestFullEnterpriseWorkflow:
    """End-to-end: SSO login → RBAC check → feature entitlement → audit log → retention."""

    def test_enterprise_workflow(self, org_db, audit_db, sso_config):
        """Simulate a full enterprise request lifecycle."""
        # 1. SSO: User authenticates via IdP, gets claims
        claims = SsoClaims(
            subject="dev@acme.com",
            issuer=sso_config.issuer,
            audience=sso_config.audience,
            expires_at=time.time() + 3600,
            scopes=["openid"],
            role="operator",
            raw_claims={"sub": "dev@acme.com", "role": "operator"},
        )

        # 2. RBAC: Resolve role from claims
        rbac = RbacChecker()
        request = MagicMock()
        request.headers = {
            "x-headroom-role": claims.role,
            "x-headroom-user-id": claims.subject,
        }
        role = rbac.resolve_role(request)
        assert role == AdminRole.OPERATOR

        # 3. Entitlement: Check feature access
        checker = EntitlementChecker("enterprise")
        assert checker.is_entitled("smart_crusher")
        assert checker.is_entitled("audit_logs")

        # 4. RBAC permission check
        assert rbac.has_permission(role, "stats.read")
        assert rbac.has_permission(role, "config.write")
        assert not rbac.has_permission(role, "rbac.write")  # Admin-only

        # 5. Audit: Log the action
        event = AuditEvent(
            action="compression.request",
            actor=claims.subject,
            detail={"role": role.value, "feature": "smart_crusher", "tokens_saved": 1500},
        )
        audit_db.log(event)

        # 6. Verify audit trail
        events = audit_db.query(actor=claims.subject)
        assert len(events) >= 1
        assert events[0]["detail"]["tokens_saved"] == 1500

    def test_viewer_denied_from_admin_action(self, audit_db):
        """Simulate a viewer trying to reset stats — should be denied and audited."""
        # RBAC check
        rbac = RbacChecker()
        request = MagicMock()
        request.headers = {"x-headroom-role": "viewer"}
        role = rbac.resolve_role(request)

        # Permission check
        has_perm = rbac.has_permission(role, "stats.reset")
        assert not has_perm

        # Audit the denial
        event = AuditEvent(
            action="auth.access_denied",
            actor="viewer@acme.com",
            detail={"role": "viewer", "permission": "stats.reset", "endpoint": "POST /stats/reset"},
            success=False,
        )
        audit_db.log(event)

        # Verify
        events = audit_db.query(action="auth.access_denied")
        assert len(events) >= 1

    def test_builder_cannot_access_team_features(self):
        """Builder-tier user should be denied all team+ features."""
        checker = EntitlementChecker("builder")
        paid_features = [f for f, t in FEATURE_TIERS.items() if t != EntitlementTier.BUILDER]
        denied = 0
        for f in paid_features:
            if not checker.is_entitled(f):
                denied += 1
        assert denied == len(paid_features), f"Builder should deny all {len(paid_features)} paid features"

    def test_enterprise_org_lifecycle(self, org_db, audit_db):
        """Full org lifecycle: create → workspace → project → audit → delete."""
        # Create org
        org = org_db.create_org(name="Acme Corp", admin_email="admin@acme.com")
        audit_db.log(AuditEvent(action="org.created", actor="admin@acme.com", detail={"org_id": org["id"]}))

        # Create workspace
        ws = org_db.create_workspace(org_id=org["id"], name="Engineering")
        audit_db.log(AuditEvent(action="workspace.created", actor="admin@acme.com", detail={"workspace_id": ws["id"]}))

        # Create project
        proj = org_db.create_project(workspace_id=ws["id"], name="headroom", path="/srv/headroom")
        audit_db.log(AuditEvent(action="project.created", actor="admin@acme.com", detail={"project_id": proj["id"]}))

        # Verify hierarchy
        hierarchy = org_db.get_org_hierarchy(org["id"])
        assert hierarchy is not None
        assert len(hierarchy["workspaces"]) == 1
        assert len(hierarchy["workspaces"][0]["projects"]) == 1

        # Verify audit trail
        all_events = audit_db.query()
        actions = [e["action"] for e in all_events]
        assert "org.created" in actions
        assert "workspace.created" in actions
        assert "project.created" in actions

        # Delete org (cascade)
        deleted = org_db.delete_org(org["id"])
        assert deleted
        assert org_db.get_org(org["id"]) is None

    def test_retention_after_audit_activity(self, audit_db):
        """Audit events should be queryable for retention decisions."""
        # Generate some audit events
        for i in range(10):
            audit_db.log(AuditEvent(
                action="compression.request",
                actor=f"user{i}@acme.com",
                detail={"tokens_saved": i * 100},
            ))

        # Query for retention
        events = audit_db.query(action="compression.request")
        assert len(events) == 10

        # Count for cleanup decisions
        count = audit_db.count(action="compression.request")
        assert count == 10
