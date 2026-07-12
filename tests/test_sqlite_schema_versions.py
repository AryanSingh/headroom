from __future__ import annotations

import sqlite3

from cryptography.fernet import Fernet

from cutctx.cache.prefix_tracker import SessionTrackerStore
from cutctx.fleet import FleetStore
from cutctx.org import OrgStore
from cutctx.proxy.webhook_stores import WebhookDeadLetterStore, WebhookSubscriptionStore
from cutctx.rbac import RbacAssignmentStore
from cutctx.scim import ScimStore
from cutctx.security.mfa import MfaStore
from cutctx.security.secrets_store import SecretsStore
from cutctx.telemetry.episodes import EpisodeStore
from cutctx_ee.audit.store import AuditStore
from cutctx_ee.ledger.store import LedgerStore
from cutctx_ee.memory_service.store import MemoryStore


def _user_version(path) -> int:
    with sqlite3.connect(str(path)) as conn:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])


def test_operational_sqlite_stores_stamp_schema_version(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CUTCTX_AUDIT_SECRET_KEY", "schema-version-test-secret")
    paths = {
        "fleet": tmp_path / "fleet.db",
        "org": tmp_path / "org.db",
        "scim": tmp_path / "scim.db",
        "rbac": tmp_path / "rbac.db",
        "audit": tmp_path / "audit.db",
        "ledger": tmp_path / "ledger.db",
        "team_memory": tmp_path / "team-memory.db",
        "prefix_tracker": tmp_path / "prefix-tracker.db",
        "webhook_subscriptions": tmp_path / "webhook-subscriptions.db",
        "webhook_dlq": tmp_path / "webhook-dlq.db",
        "mfa": tmp_path / "mfa.db",
        "secrets": tmp_path / "secrets.db",
        "episodes": tmp_path / "episodes.db",
    }

    FleetStore(paths["fleet"])
    OrgStore(paths["org"])
    ScimStore(paths["scim"])
    RbacAssignmentStore(paths["rbac"])
    AuditStore(f"sqlite:///{paths['audit']}")
    LedgerStore(f"sqlite:///{paths['ledger']}")
    MemoryStore(f"sqlite:///{paths['team_memory']}")
    SessionTrackerStore(db_path=paths["prefix_tracker"])
    WebhookSubscriptionStore(db_path=paths["webhook_subscriptions"])
    WebhookDeadLetterStore(db_path=paths["webhook_dlq"])
    MfaStore(db_path=paths["mfa"])
    SecretsStore(
        db_path=paths["secrets"],
        strict=True,
        encryption_key=Fernet.generate_key(),
    )
    EpisodeStore(db_path=str(paths["episodes"]))

    assert {name: _user_version(path) for name, path in paths.items()} == dict.fromkeys(paths, 1)
