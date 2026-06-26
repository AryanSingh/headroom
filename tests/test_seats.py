"""Tests for cutctx.seats — seat management system."""

from __future__ import annotations

from pathlib import Path

from cutctx.seats import TIER_SEAT_LIMITS, SeatInfo, SeatManager, SeatState


class TestSeatInfo:
    def test_roundtrip(self):
        seat = SeatInfo(
            user_id="usr_123",
            email="test@example.com",
            display_name="Test User",
            added_at=1000.0,
            last_active_at=2000.0,
        )
        d = seat.to_dict()
        restored = SeatInfo.from_dict(d)
        assert restored.user_id == "usr_123"
        assert restored.email == "test@example.com"
        assert restored.is_active is True


class TestSeatState:
    def test_seats_used(self):
        state = SeatState(org_id="org_1", seats_limit=5)
        state.seats["a"] = SeatInfo(user_id="a", is_active=True)
        state.seats["b"] = SeatInfo(user_id="b", is_active=True)
        state.seats["c"] = SeatInfo(user_id="c", is_active=False)
        assert state.seats_used == 2
        assert state.seats_available == 3
        assert not state.is_at_limit

    def test_at_limit(self):
        state = SeatState(org_id="org_1", seats_limit=2)
        state.seats["a"] = SeatInfo(user_id="a", is_active=True)
        state.seats["b"] = SeatInfo(user_id="b", is_active=True)
        assert state.is_at_limit
        assert state.seats_available == 0

    def test_roundtrip(self):
        state = SeatState(org_id="org_1", tier="team", seats_limit=10)
        state.seats["u1"] = SeatInfo(user_id="u1", email="a@b.com")
        d = state.to_dict()
        restored = SeatState.from_dict(d)
        assert restored.org_id == "org_1"
        assert restored.seats_limit == 10
        assert "u1" in restored.seats


class TestSeatManager:
    def test_set_tier(self, tmp_path: Path):
        sm = SeatManager(state_path=tmp_path / "seats.json")
        sm.set_tier("team")
        assert sm.state.tier == "team"
        assert sm.state.seats_limit == TIER_SEAT_LIMITS["team"]

    def test_set_tier_custom_limit(self, tmp_path: Path):
        sm = SeatManager(state_path=tmp_path / "seats.json")
        sm.set_tier("team", seats_limit=25)
        assert sm.state.seats_limit == 25

    def test_add_seat(self, tmp_path: Path):
        sm = SeatManager(state_path=tmp_path / "seats.json")
        sm.set_tier("team")
        seat = sm.add_seat(email="user@test.com", display_name="Test")
        assert seat is not None
        assert seat.email == "user@test.com"
        assert sm.state.seats_used == 1

    def test_add_seat_at_limit(self, tmp_path: Path):
        sm = SeatManager(state_path=tmp_path / "seats.json")
        sm.set_tier("builder")  # limit=1
        sm.add_seat()
        result = sm.add_seat()
        assert result is None
        assert sm.state.seats_used == 1

    def test_remove_seat(self, tmp_path: Path):
        sm = SeatManager(state_path=tmp_path / "seats.json")
        sm.set_tier("team")
        seat = sm.add_seat()
        assert sm.remove_seat(seat.user_id) is True
        assert sm.state.seats_used == 0

    def test_remove_nonexistent_seat(self, tmp_path: Path):
        sm = SeatManager(state_path=tmp_path / "seats.json")
        assert sm.remove_seat("nonexistent") is False

    def test_check_seat(self, tmp_path: Path):
        sm = SeatManager(state_path=tmp_path / "seats.json")
        sm.set_tier("team")
        seat = sm.add_seat()
        info = sm.check_seat(seat.user_id)
        assert info["has_seat"] is True
        assert info["seats_used"] == 1
        assert info["seats_limit"] == TIER_SEAT_LIMITS["team"]

    def test_enforce_seat_limit(self, tmp_path: Path):
        sm = SeatManager(state_path=tmp_path / "seats.json")
        sm.set_tier("builder")
        assert sm.enforce_seat_limit() is False
        sm.add_seat()
        assert sm.enforce_seat_limit() is True

    def test_persistence(self, tmp_path: Path):
        path = tmp_path / "seats.json"
        sm1 = SeatManager(state_path=path)
        sm1.set_tier("team")
        sm1.add_seat(email="persist@test.com")

        sm2 = SeatManager(state_path=path)
        assert sm2.state.tier == "team"
        assert sm2.state.seats_used == 1

    def test_sync_from_license(self, tmp_path: Path):
        sm = SeatManager(state_path=tmp_path / "seats.json")
        sm.set_tier("team", seats_limit=5)
        sm.add_seat()
        sm.add_seat()
        sm.add_seat()
        # Decrease limit to 2 — excess seats should be deactivated
        sm.sync_from_license(seats_used=3, seats_limit=2)
        assert sm.state.seats_limit == 2
        # Only 2 active seats should remain
        assert sm.state.seats_used <= 2

    def test_corrupt_state_starts_fresh(self, tmp_path: Path):
        path = tmp_path / "seats.json"
        path.write_text("not valid json {{{")
        sm = SeatManager(state_path=path)
        assert sm.state.org_id == "default"
