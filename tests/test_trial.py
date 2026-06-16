"""Tests for headroom.trial — trial enforcement system."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from headroom.trial import TRIAL_DAYS, TrialManager, TrialState


class TestTrialState:
    def test_properties(self):
        state = TrialState(started_at=time.time() - 86400)  # 1 day ago
        assert state.elapsed_days == pytest.approx(1.0, abs=0.01)
        assert state.remaining_days == pytest.approx(TRIAL_DAYS - 1.0, abs=0.01)
        assert not state.is_expired

    def test_expired(self):
        state = TrialState(started_at=time.time() - (TRIAL_DAYS + 1) * 86400)
        assert state.is_expired
        assert state.remaining_days == 0.0

    def test_roundtrip(self):
        state = TrialState(started_at=1000.0, org_id="org_1", activated=True)
        d = state.to_dict()
        restored = TrialState.from_dict(d)
        assert restored.started_at == 1000.0
        assert restored.org_id == "org_1"
        assert restored.activated is True


class TestTrialManager:
    def test_start_trial(self, tmp_path: Path):
        sm = TrialManager(state_path=tmp_path / "trial.json")
        state = sm.start_trial(org_id="org_test")
        assert state.org_id == "org_test"
        assert not state.is_expired

    def test_check_trial_active(self, tmp_path: Path):
        sm = TrialManager(state_path=tmp_path / "trial.json")
        sm.start_trial()
        info = sm.check_trial()
        assert info["active"] is True
        assert info["expired"] is False
        assert info["remaining_days"] > 0

    def test_enforce_trial_not_expired(self, tmp_path: Path):
        sm = TrialManager(state_path=tmp_path / "trial.json")
        sm.start_trial()
        assert sm.enforce_trial() is False

    def test_enforce_trial_expired(self, tmp_path: Path):
        sm = TrialManager(state_path=tmp_path / "trial.json")
        # Start trial in the past (expired)
        state = sm.start_trial()
        state.started_at = time.time() - (TRIAL_DAYS + 1) * 86400
        sm._state = state
        sm._save()
        assert sm.enforce_trial() is True

    def test_activate_license_disables_enforcement(self, tmp_path: Path):
        sm = TrialManager(state_path=tmp_path / "trial.json")
        state = sm.start_trial()
        state.started_at = time.time() - (TRIAL_DAYS + 1) * 86400
        sm._state = state
        sm._save()
        assert sm.enforce_trial() is True

        sm.activate_license(org_id="org_123")
        assert sm.enforce_trial() is False
        info = sm.check_trial()
        assert info["activated"] is True

    def test_persistence(self, tmp_path: Path):
        path = tmp_path / "trial.json"
        sm1 = TrialManager(state_path=path)
        sm1.start_trial(org_id="org_persist")

        sm2 = TrialManager(state_path=path)
        assert sm2.state.org_id == "org_persist"

    def test_corrupt_state_starts_fresh(self, tmp_path: Path):
        path = tmp_path / "trial.json"
        path.write_text("not valid json {{{")
        sm = TrialManager(state_path=path)
        state = sm.state
        assert state.started_at > 0  # Fresh trial created
