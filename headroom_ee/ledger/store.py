# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Headroom Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

from collections.abc import Iterable
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from headroom.pricing.registry import PricingRegistry
from headroom_ee.ledger.models import Base, SpendEvent
from headroom_ee.ledger.pricing import compute_costs


class LedgerStore:
    """Proprietary spend ledger store.

    Handles the write path for incoming spend events.
    """

    def __init__(self, db_url: str, pricing_registry: PricingRegistry | None = None):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.pricing_registry = pricing_registry

    def insert_events(self, events: Iterable[dict[str, Any]]) -> None:
        """Insert a batch of spend events.

        Args:
            events: Iterable of dictionaries containing SpendEvent fields.
                    Expected to match the JSON schema from the Rust spend emitter.
        """
        with self.SessionLocal() as session:
            for event_data in events:
                # If cost isn't provided by the emitter, compute it here
                if self.pricing_registry and (
                    event_data.get("est_cost_usd") is None
                    or event_data.get("est_cost_saved_usd") is None
                ):
                    costs = compute_costs(
                        registry=self.pricing_registry,
                        model=event_data.get("model"),
                        input_tokens=event_data.get("input_tokens", 0),
                        output_tokens=event_data.get("output_tokens", 0),
                        tokens_saved=event_data.get("tokens_saved", 0),
                    )

                    if event_data.get("est_cost_usd") is None:
                        event_data["est_cost_usd"] = costs.est_cost_usd
                    if event_data.get("est_cost_saved_usd") is None:
                        event_data["est_cost_saved_usd"] = costs.est_cost_saved_usd

                db_event = SpendEvent(**event_data)
                session.add(db_event)
            session.commit()
