# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

from __future__ import annotations

import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from cutctx_ee.billing.license_db import LICENSE_DELIVERY_STALE_SECONDS, LicenseDB


def _checkout_record(license_key: str, subscription_id: str):
    now = time.time()
    return SimpleNamespace(
        license_key=license_key,
        tier="team",
        customer_email="buyer@example.com",
        seats=3,
        stripe_customer_id="cus_1",
        stripe_subscription_id=subscription_id,
        created_at=now,
        expires_at=now + 3600,
        active=True,
    )


def test_fulfill_checkout_replay_returns_existing_license(tmp_path) -> None:
    db = LicenseDB(tmp_path / "licenses.db")

    first, first_created = db.fulfill_checkout(_checkout_record("license-a", "sub_same"))
    replay, replay_created = db.fulfill_checkout(_checkout_record("license-b", "sub_same"))

    assert first_created is True
    assert replay_created is False
    assert first.license_key == replay.license_key == "license-a"
    assert db._conn.execute("SELECT count(*) FROM licenses").fetchone()[0] == 1


def test_concurrent_checkout_fulfillment_issues_one_license(tmp_path) -> None:
    db_path = tmp_path / "licenses.db"
    LicenseDB(db_path).close()
    barrier = threading.Barrier(2)

    def fulfill(license_key: str):
        connection = LicenseDB(db_path)
        try:
            barrier.wait()
            return connection.fulfill_checkout(_checkout_record(license_key, "sub_concurrent"))
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(fulfill, ["license-a", "license-b"]))

    returned_keys = {record.license_key for record, _created in results}
    assert returned_keys in ({"license-a"}, {"license-b"})
    assert sum(created for _record, created in results) == 1

    verification_db = LicenseDB(db_path)
    try:
        rows = verification_db._conn.execute(
            "SELECT license_key FROM licenses WHERE stripe_subscription_id = ?",
            ("sub_concurrent",),
        ).fetchall()
    finally:
        verification_db.close()
    assert len(rows) == 1


def test_direct_upsert_rejects_conflicting_subscription_association(tmp_path) -> None:
    db = LicenseDB(tmp_path / "licenses.db")

    db.upsert(_checkout_record("license-canonical", "sub_direct"))
    with pytest.raises(sqlite3.IntegrityError):
        db.upsert(_checkout_record("license-later", "sub_direct"))

    rows = db._conn.execute(
        "SELECT license_key, stripe_subscription_id FROM licenses ORDER BY license_key"
    ).fetchall()
    assert rows == [("license-canonical", "sub_direct")]


def test_initialization_detaches_historical_duplicate_subscription_associations(tmp_path) -> None:
    db_path = tmp_path / "licenses.db"
    raw = LicenseDB(db_path)
    raw._conn.execute("DROP INDEX IF EXISTS licenses_stripe_subscription_id_unique")
    raw._conn.execute(
        "INSERT INTO licenses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("legacy-a", "team", "a@example.com", 1, "cus-a", "sub_legacy", 1.0, 10.0, 1),
    )
    raw._conn.execute(
        "INSERT INTO licenses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("legacy-b", "team", "b@example.com", 1, "cus-b", "sub_legacy", 2.0, 10.0, 1),
    )
    raw._conn.execute("PRAGMA user_version = 1")
    raw._conn.commit()
    raw.close()

    migrated = LicenseDB(db_path)
    rows = migrated._conn.execute(
        "SELECT license_key, stripe_subscription_id FROM licenses ORDER BY license_key"
    ).fetchall()
    index = migrated._conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
        ("licenses_stripe_subscription_id_unique",),
    ).fetchone()

    assert rows == [("legacy-a", "sub_legacy"), ("legacy-b", None)]
    assert index is not None
    assert "WHERE stripe_subscription_id IS NOT NULL" in index[0]
    assert migrated.deactivate_subscription("sub_legacy") is True
    assert migrated.validate("legacy-a") == {"valid": False, "reason": "subscription_cancelled"}
    assert migrated.validate("legacy-b") == {"valid": False, "reason": "revoked"}
    revocation = migrated._conn.execute(
        "SELECT reason FROM revocations WHERE license_key = ?", ("legacy-b",)
    ).fetchone()
    assert "duplicate subscription" in revocation[0]
    assert "migration" in revocation[0]


def test_stale_delivery_claim_is_fenced_from_the_reclaiming_worker(tmp_path) -> None:
    db = LicenseDB(tmp_path / "licenses.db")
    record, created = db.fulfill_checkout(_checkout_record("license-fenced", "sub_fenced"))
    assert created is True

    claim_a = db.claim_license_delivery(record.license_key)
    assert claim_a is not None
    db._conn.execute(
        "UPDATE license_deliveries SET claimed_at = ? WHERE license_key = ?",
        (time.time() - LICENSE_DELIVERY_STALE_SECONDS - 1, record.license_key),
    )
    db._conn.commit()
    claim_b = db.claim_license_delivery(record.license_key)
    assert claim_b is not None
    assert claim_b != claim_a

    assert db.release_license_delivery(record.license_key, claim_a, RuntimeError("late")) is False
    assert db.mark_license_delivery_delivered(record.license_key, claim_a) is False
    owner = db._conn.execute(
        "SELECT status, claim_token FROM license_deliveries WHERE license_key = ?",
        (record.license_key,),
    ).fetchone()
    assert owner == ("sending", claim_b)

    assert db.mark_license_delivery_delivered(record.license_key, claim_b) is True
    final = db._conn.execute(
        "SELECT status, claim_token, claimed_at FROM license_deliveries WHERE license_key = ?",
        (record.license_key,),
    ).fetchone()
    assert final == ("delivered", None, None)


def _db_with_one_seat_license(tmp_path) -> LicenseDB:
    db = LicenseDB(tmp_path / "licenses.db")
    now = time.time()
    db.upsert(("local-license", "team", "buyer@example.com", 1, "", "", now, now + 3600, 1))
    return db


def test_activation_refuses_new_instance_when_license_limit_is_reached(tmp_path) -> None:
    db = _db_with_one_seat_license(tmp_path)

    assert db.activate_instance("local-license", "instance-1") is True
    assert db.activate_instance("local-license", "instance-2") is False


def test_activation_renews_existing_instance_at_limit(tmp_path) -> None:
    db = _db_with_one_seat_license(tmp_path)

    assert db.activate_instance("local-license", "instance-1") is True
    assert db.activate_instance("local-license", "instance-1") is True


@pytest.mark.parametrize("seats", [0, -1])
def test_activation_rejects_non_positive_seat_count(tmp_path, seats: int) -> None:
    db = LicenseDB(tmp_path / "licenses.db")
    now = time.time()
    db.upsert(("local-license", "team", "buyer@example.com", seats, "", "", now, now + 3600, 1))

    assert db.activate_instance("local-license", "instance-1") is False


@pytest.mark.parametrize("seats", [0, -1])
def test_checkout_rejects_non_positive_seat_count(tmp_path, seats: int) -> None:
    db = LicenseDB(tmp_path / "licenses.db")
    now = time.time()
    db.upsert(("local-license", "team", "buyer@example.com", seats, "", "", now, now + 3600, 1))

    assert db.checkout_seat("local-license", "user-1", 3600) is False


def test_concurrent_activation_across_two_connections_respects_one_seat(tmp_path) -> None:
    db_path = tmp_path / "licenses.db"
    db = _db_with_one_seat_license(tmp_path)
    db.close()
    barrier = threading.Barrier(2)

    def activate(instance_id: str) -> bool:
        connection = LicenseDB(db_path)
        try:
            barrier.wait()
            return connection.activate_instance("local-license", instance_id)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(activate, ["instance-1", "instance-2"]))

    assert sum(results) == 1

    verification_db = LicenseDB(db_path)
    try:
        activation_count = verification_db._conn.execute(
            "SELECT count(*) FROM activations WHERE license_key = ?",
            ("local-license",),
        ).fetchone()[0]
    finally:
        verification_db.close()

    assert activation_count == 1


def test_concurrent_checkout_across_two_connections_respects_one_seat(tmp_path) -> None:
    db_path = tmp_path / "licenses.db"
    db = _db_with_one_seat_license(tmp_path)
    db._conn.execute(
        """
        CREATE TRIGGER wait_for_concurrent_checkout
        BEFORE INSERT ON seat_leases
        BEGIN
            SELECT checkout_barrier();
        END
        """
    )
    db._conn.commit()
    db.close()
    start_barrier = threading.Barrier(2)
    insert_barrier = threading.Barrier(2)

    def wait_for_other_insert() -> None:
        try:
            insert_barrier.wait(timeout=1)
        except threading.BrokenBarrierError:
            pass

    def checkout(user_id: str) -> bool:
        connection = LicenseDB(db_path)
        try:
            connection._conn.create_function("checkout_barrier", 0, wait_for_other_insert)
            start_barrier.wait()
            return connection.checkout_seat("local-license", user_id, 3600)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(checkout, ["user-1", "user-2"]))

    assert sum(results) == 1

    verification_db = LicenseDB(db_path)
    try:
        lease_rows = verification_db._conn.execute(
            "SELECT user_id FROM seat_leases WHERE license_key = ?",
            ("local-license",),
        ).fetchall()
    finally:
        verification_db.close()

    assert len(lease_rows) == 1
    assert lease_rows[0][0] in {"user-1", "user-2"}


def test_activation_waits_for_short_external_write_lock(tmp_path) -> None:
    db_path = tmp_path / "licenses.db"
    owner = _db_with_one_seat_license(tmp_path)
    owner._conn.execute("BEGIN IMMEDIATE")

    def activate() -> bool:
        contender = LicenseDB(db_path)
        try:
            return contender.activate_instance("local-license", "instance-1")
        finally:
            contender.close()

    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(activate)
        time.sleep(0.1)
        owner._conn.commit()
        assert result.result(timeout=2) is True
    owner.close()

    verification_db = LicenseDB(db_path)
    try:
        activation_count = verification_db._conn.execute(
            "SELECT count(*) FROM activations WHERE license_key = ?",
            ("local-license",),
        ).fetchone()[0]
    finally:
        verification_db.close()

    assert activation_count == 1
