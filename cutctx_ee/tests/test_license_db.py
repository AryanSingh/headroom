# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from cutctx_ee.billing.license_db import LicenseDB


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
