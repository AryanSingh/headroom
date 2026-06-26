# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

from unittest.mock import MagicMock, patch

from cutctx_ee.trial import TrialManager, TrialState


def test_server_side_trial_active():
    manager = TrialManager(MagicMock())
    manager._state = TrialState(started_at=100.0, trial_token="tok_123")

    with patch("cutctx.billing.client.is_trial_active", return_value=True):
        info = manager.check_trial()
        assert info["active"] is True
        assert info["expired"] is False


def test_server_side_trial_expired():
    manager = TrialManager(MagicMock())
    manager._state = TrialState(started_at=100.0, trial_token="tok_123")

    with patch("cutctx.billing.client.is_trial_active", return_value=False):
        info = manager.check_trial()
        assert info["active"] is False
        assert info["expired"] is True


def test_start_server_trial():
    manager = TrialManager(MagicMock())

    with patch("cutctx.billing.client.start_trial", return_value=True):
        state = manager.start_trial(
            org_id="org_1", trial_token="tok_123", customer_email="test@example.com"
        )
        assert state.trial_token == "tok_123"
