from __future__ import annotations

import sqlite3

from cutctx.fleet import FleetStore
from cutctx.org import OrgStore
from cutctx.rbac import RbacAssignmentStore
from cutctx.scim import ScimStore
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
    }

    FleetStore(paths["fleet"])
    OrgStore(paths["org"])
    ScimStore(paths["scim"])
    RbacAssignmentStore(paths["rbac"])
    AuditStore(f"sqlite:///{paths['audit']}")
    LedgerStore(f"sqlite:///{paths['ledger']}")
    MemoryStore(f"sqlite:///{paths['team_memory']}")

    assert {name: _user_version(path) for name, path in paths.items()} == dict.fromkeys(paths, 1)
