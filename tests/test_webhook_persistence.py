# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Tests for the WebhookSubscriptionStore + WebhookDeadLetterStore.

Audit-Deep-2026-06-21 High-15: subscriptions + DLQ were
in-memory only. These tests pin the SQLite-backed
persistence.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_sub_store(tmp_path: Path):
    from headroom.proxy.webhook_stores import WebhookSubscriptionStore

    yield WebhookSubscriptionStore(db_path=str(tmp_path / "subs.db"))


@pytest.fixture
def tmp_dlq_store(tmp_path: Path):
    from headroom.proxy.webhook_stores import WebhookDeadLetterStore

    yield WebhookDeadLetterStore(
        db_path=str(tmp_path / "dlq.db"), max_rows=10
    )


class TestSubscriptionStore:
    def test_upsert_then_list(self, tmp_sub_store):
        from headroom.proxy.webhook_stores import StoredSubscription

        sub = tmp_sub_store.upsert(
            url="https://example.com/hook",
            secret="shh",
            event_types=("policy.upsert", "auth.failed"),
        )
        assert isinstance(sub, StoredSubscription)
        assert sub.id.startswith("wh_")
        listing = tmp_sub_store.list_all()
        assert len(listing) == 1
        assert listing[0].url == "https://example.com/hook"
        assert listing[0].event_types == ("policy.upsert", "auth.failed")

    def test_upsert_overwrites_by_id(self, tmp_sub_store):
        sub = tmp_sub_store.upsert(
            url="https://example.com/hook", secret="v1"
        )
        same_id = sub.id
        # Re-upsert with the same id, different secret.
        tmp_sub_store.upsert(
            url="https://example.com/hook", secret="v2", sub_id=same_id
        )
        loaded = tmp_sub_store.get(same_id)
        assert loaded.secret == "v2"

    def test_upsert_catchall_event_types(self, tmp_sub_store):
        sub = tmp_sub_store.upsert(
            url="https://example.com/hook", secret="shh"
        )
        loaded = tmp_sub_store.get(sub.id)
        # event_types is None for catch-all subscriptions
        assert loaded.event_types is None

    def test_delete(self, tmp_sub_store):
        sub = tmp_sub_store.upsert(
            url="https://example.com/hook", secret="shh"
        )
        assert tmp_sub_store.delete(sub.id) is True
        assert tmp_sub_store.get(sub.id) is None
        # Second delete returns False
        assert tmp_sub_store.delete(sub.id) is False

    def test_persistence_across_instances(self, tmp_path: Path):
        from headroom.proxy.webhook_stores import WebhookSubscriptionStore

        store_a = WebhookSubscriptionStore(db_path=str(tmp_path / "s.db"))
        sub = store_a.upsert(
            url="https://example.com/hook", secret="shh"
        )
        store_b = WebhookSubscriptionStore(db_path=str(tmp_path / "s.db"))
        loaded = store_b.get(sub.id)
        assert loaded is not None
        assert loaded.url == "https://example.com/hook"


class TestDeadLetterStore:
    def test_add_then_list_unacknowledged(self, tmp_dlq_store):
        dl = tmp_dlq_store.add(
            event_id="evt-1",
            event_type="policy.upsert",
            payload={"x": 1},
            target_url="https://example.com/hook",
            last_status=500,
            last_error="server error",
            attempts=5,
        )
        assert dl.id.startswith("dlq_")
        unack = tmp_dlq_store.list_unacknowledged()
        assert len(unack) == 1
        assert unack[0].event_id == "evt-1"
        assert unack[0].acknowledged is False

    def test_acknowledge(self, tmp_dlq_store):
        dl = tmp_dlq_store.add(
            event_id="evt-1",
            event_type="policy.upsert",
            payload={},
            target_url="https://example.com/hook",
            last_status=None,
            last_error="queue full",
            attempts=0,
        )
        assert tmp_dlq_store.acknowledge(dl.id) is True
        # Acknowledged entries no longer appear in
        # list_unacknowledged but do in list_all.
        assert tmp_dlq_store.list_unacknowledged() == []
        all_items = tmp_dlq_store.list_all()
        assert len(all_items) == 1
        assert all_items[0].acknowledged is True

    def test_purge_acknowledged(self, tmp_dlq_store):
        for i in range(3):
            tmp_dlq_store.add(
                event_id=f"evt-{i}",
                event_type="policy.upsert",
                payload={},
                target_url="https://example.com/hook",
                last_status=500,
                last_error="err",
                attempts=1,
            )
        # Acknowledge two of three
        items = tmp_dlq_store.list_unacknowledged()
        tmp_dlq_store.acknowledge(items[0].id)
        tmp_dlq_store.acknowledge(items[1].id)
        purged = tmp_dlq_store.purge_acknowledged()
        assert purged == 2
        # One unacknowledged remains
        assert len(tmp_dlq_store.list_unacknowledged()) == 1

    def test_max_rows_enforced(self, tmp_path: Path):
        """The DLQ caps at max_rows.

        When the table exceeds max_rows, the oldest
        acknowledged rows are purged first. If still over,
        the oldest unacknowledged rows are purged (with a
        loud warning) to bound the table.
        """
        from headroom.proxy.webhook_stores import WebhookDeadLetterStore

        store = WebhookDeadLetterStore(
            db_path=str(tmp_path / "dlq.db"), max_rows=5
        )
        for i in range(8):
            store.add(
                event_id=f"evt-{i}",
                event_type="policy.upsert",
                payload={},
                target_url="https://example.com/hook",
                last_status=500,
                last_error="err",
                attempts=1,
            )
        # Should never exceed max_rows
        assert len(store.list_all()) <= 5


class TestDispatcherIntegration:
    """End-to-end: the dispatcher uses the persistent stores."""

    def test_dispatcher_uses_persistent_subscription(self, tmp_path: Path):
        import os

        os.environ["HEADROOM_WEBHOOKS_IN_MEMORY"] = "0"
        os.environ["CUTCTX_WEBHOOK_DB_PATH"] = str(tmp_path / "subs.db")
        os.environ["CUTCTX_WEBHOOK_DLQ_DB_PATH"] = str(tmp_path / "dlq.db")

        from headroom.proxy.webhook_stores import (
            WebhookDeadLetterStore,
            WebhookSubscriptionStore,
        )
        from headroom.proxy.webhooks import (
            WebhookDispatcher,
            WebhookSubscription,
        )

        sub_store = WebhookSubscriptionStore(
            db_path=str(tmp_path / "subs.db")
        )
        dlq_store = WebhookDeadLetterStore(
            db_path=str(tmp_path / "dlq.db")
        )
        d = WebhookDispatcher(
            subscription_store=sub_store, dlq_store=dlq_store
        )
        d.subscribe(
            WebhookSubscription(
                url="https://example.com/hook",
                secret="shh",
                event_types=("policy.upsert",),
            )
        )
        # Now simulate a restart: new dispatcher reads from
        # the same DB.
        d2 = WebhookDispatcher(
            subscription_store=WebhookSubscriptionStore(
                db_path=str(tmp_path / "subs.db")
            ),
            dlq_store=WebhookDeadLetterStore(
                db_path=str(tmp_path / "dlq.db")
            ),
        )
        subs = d2.list_subscriptions()
        assert len(subs) == 1
        assert subs[0]["url"] == "https://example.com/hook"
