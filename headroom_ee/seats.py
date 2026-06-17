# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Headroom Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""Seat management for Headroom organizations.

Tracks per-org seat usage and enforces seat limits defined by the license tier.
Seat state is persisted to ``~/.headroom/seat_state.json`` using
machine-derived encryption (Fernet) to prevent trivial tampering.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from headroom import paths
from headroom.security.state_crypto import read_encrypted_json, write_encrypted_json

logger = logging.getLogger("headroom.seats")

SEAT_STATE_FILE = "seat_state.json"

# Default seat limits per tier
TIER_SEAT_LIMITS = {
    "builder": 1,
    "team": 10,
    "business": 50,
    "enterprise": 500,
}


@dataclass
class SeatInfo:
    """A single seat/user record."""

    user_id: str
    email: str | None = None
    display_name: str | None = None
    added_at: float = 0.0
    last_active_at: float = 0.0
    is_active: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> SeatInfo:
        return cls(
            user_id=d["user_id"],
            email=d.get("email"),
            display_name=d.get("display_name"),
            added_at=d.get("added_at", 0.0),
            last_active_at=d.get("last_active_at", 0.0),
            is_active=d.get("is_active", True),
        )


@dataclass
class SeatState:
    """Persisted seat tracking state for an organization."""

    org_id: str
    tier: str = "builder"
    seats_limit: int = 1
    seats: dict[str, SeatInfo] = field(default_factory=dict)
    last_synced_at: float = 0.0

    @property
    def seats_used(self) -> int:
        """Number of active seats."""
        return sum(1 for s in self.seats.values() if s.is_active)

    @property
    def seats_available(self) -> int:
        """Remaining seats available."""
        return max(0, self.seats_limit - self.seats_used)

    @property
    def is_at_limit(self) -> bool:
        """True if no seats are available."""
        return self.seats_used >= self.seats_limit

    def to_dict(self) -> dict:
        d = asdict(self)
        d["seats"] = {k: v.to_dict() for k, v in self.seats.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> SeatState:
        seats = {k: SeatInfo.from_dict(v) for k, v in d.get("seats", {}).items()}
        return cls(
            org_id=d["org_id"],
            tier=d.get("tier", "builder"),
            seats_limit=d.get("seats_limit", 1),
            seats=seats,
            last_synced_at=d.get("last_synced_at", 0.0),
        )


class SeatManager:
    """Manages seat allocation, tracking, and limits."""

    def __init__(self, state_path: Path | None = None):
        self._state_path = state_path or (paths.workspace_dir() / SEAT_STATE_FILE)
        self._state: SeatState | None = None

    def _load(self) -> SeatState:
        if self._state is not None:
            return self._state

        data = read_encrypted_json(self._state_path)
        if data is not None:
            try:
                self._state = SeatState.from_dict(data)
                return self._state
            except (KeyError, TypeError):
                logger.warning("Corrupt seat state at %s, starting fresh", self._state_path)

        # No state — create with org_id placeholder
        self._state = SeatState(org_id="default")
        self._save()
        return self._state

    def _save(self) -> None:
        if self._state is None:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        write_encrypted_json(self._state_path, self._state.to_dict())

    @property
    def state(self) -> SeatState:
        return self._load()

    def set_tier(self, tier: str, seats_limit: int | None = None) -> None:
        """Update tier and seat limit."""
        state = self._load()
        state.tier = tier.lower()
        state.seats_limit = seats_limit or TIER_SEAT_LIMITS.get(state.tier, 1)
        self._save()
        logger.info("Seat tier updated to %s, limit=%d", state.tier, state.seats_limit)

    def add_seat(
        self,
        user_id: str | None = None,
        email: str | None = None,
        display_name: str | None = None,
    ) -> SeatInfo | None:
        """Add a new seat. Returns None if at limit."""
        state = self._load()

        if state.is_at_limit:
            logger.warning(
                "Cannot add seat: at limit (%d/%d) for org %s",
                state.seats_used,
                state.seats_limit,
                state.org_id,
            )
            return None

        # Generate user_id if not provided
        if user_id is None:
            user_id = f"usr_{uuid.uuid4().hex[:12]}"

        seat = SeatInfo(
            user_id=user_id,
            email=email,
            display_name=display_name,
            added_at=time.time(),
            last_active_at=time.time(),
            is_active=True,
        )
        state.seats[user_id] = seat
        self._save()
        logger.info(
            "Seat added: %s (org=%s, %d/%d)",
            user_id,
            state.org_id,
            state.seats_used,
            state.seats_limit,
        )
        return seat

    def remove_seat(self, user_id: str) -> bool:
        """Remove a seat. Returns True if seat was found and removed."""
        state = self._load()
        if user_id not in state.seats:
            return False
        del state.seats[user_id]
        self._save()
        logger.info(
            "Seat removed: %s (org=%s, %d/%d)",
            user_id,
            state.org_id,
            state.seats_used,
            state.seats_limit,
        )
        return True

    def touch_seat(self, user_id: str) -> None:
        """Update last_active_at for a seat."""
        state = self._load()
        if user_id in state.seats:
            state.seats[user_id].last_active_at = time.time()
            self._save()

    def check_seat(self, user_id: str) -> dict:
        """Check if a user has a valid seat.

        Returns dict with:
            - has_seat: bool
            - seats_used: int
            - seats_limit: int
            - seats_available: int
        """
        state = self._load()
        seat = state.seats.get(user_id)
        has_seat = seat is not None and seat.is_active if seat else False

        return {
            "has_seat": has_seat,
            "seats_used": state.seats_used,
            "seats_limit": state.seats_limit,
            "seats_available": state.seats_available,
        }

    def enforce_seat_limit(self) -> bool:
        """Return True if seat limit is enforced (at or over limit)."""
        state = self._load()
        return state.is_at_limit

    def sync_from_license(self, seats_used: int, seats_limit: int) -> None:
        """Sync seat counts from license validation response."""
        state = self._load()
        state.seats_limit = seats_limit
        state.last_synced_at = time.time()

        # Also send heartbeat to PitchToShip if configured
        from headroom_ee.billing.pitchtoship_client import heartbeat_seat, is_configured
        if is_configured():
            result = heartbeat_seat(
                license_key=state.org_id,  # Use org_id as license key reference
                hwid=f"hr_{state.org_id}",
            )
            if result:
                logger.info("PitchToShip heartbeat sent, seats=%d/%d", result.get("seats_used", 0), result.get("seats_limit", 0))

        # Mark excess seats as inactive if limit decreased
        active_seats = [s for s in state.seats.values() if s.is_active]
        if len(active_seats) > seats_limit:
            # Deactivate the most recently added seats
            active_seats.sort(key=lambda s: s.added_at, reverse=True)
            for seat in active_seats[seats_limit:]:
                seat.is_active = False
                logger.info("Seat deactivated (limit exceeded): %s", seat.user_id)

        self._save()
        logger.info(
            "Seats synced from license: %d/%d (org=%s)",
            seats_used,
            seats_limit,
            state.org_id,
        )
