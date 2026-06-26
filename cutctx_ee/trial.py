# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""Trial enforcement for Cutctx licenses.

Manages 14-day Builder-tier trials. When a trial expires, the user is
restricted to basic compression only (core compressors, no CCR, no memory,
no Live Zone).

Trial state is persisted to ``~/.cutctx/trial_state.json`` using
machine-derived encryption (Fernet) to prevent trivial tampering.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from cutctx import paths
from cutctx.security.state_crypto import read_encrypted_json, write_encrypted_json

logger = logging.getLogger("cutctx.trial")

TRIAL_DAYS = 14
TRIAL_STATE_FILE = "trial_state.json"


@dataclass
class TrialState:
    """Persisted trial state."""

    started_at: float  # Unix timestamp when trial started
    org_id: str | None = None
    activated: bool = False  # True once user has activated a license
    expired_notified: bool = False  # True once we've shown expiration warning
    trial_token: str | None = None  # Server-side trial token

    @property
    def elapsed_days(self) -> float:
        """Days since trial started."""
        return (time.time() - self.started_at) / 86400.0

    @property
    def remaining_days(self) -> float:
        """Days remaining in trial."""
        return max(0.0, TRIAL_DAYS - self.elapsed_days)

    @property
    def is_expired(self) -> bool:
        """True if trial has exceeded TRIAL_DAYS."""
        return self.elapsed_days > TRIAL_DAYS

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> TrialState:
        return cls(
            started_at=d["started_at"],
            org_id=d.get("org_id"),
            activated=d.get("activated", False),
            expired_notified=d.get("expired_notified", False),
            trial_token=d.get("trial_token"),
        )


class TrialManager:
    """Manages trial lifecycle: start, check, enforce."""

    def __init__(self, state_path: Path | None = None):
        self._state_path = state_path or (paths.workspace_dir() / TRIAL_STATE_FILE)
        self._state: TrialState | None = None

    def _load(self) -> TrialState:
        """Load trial state from disk (encrypted), or create a fresh one."""
        if self._state is not None:
            return self._state

        data = read_encrypted_json(self._state_path)
        if data is not None:
            try:
                self._state = TrialState.from_dict(data)
                return self._state
            except (KeyError, TypeError):
                logger.warning("Corrupt trial state at %s, starting fresh", self._state_path)

        # No state file or corrupt — start new trial
        self._state = TrialState(started_at=time.time())
        self._save()
        return self._state

    def _save(self) -> None:
        """Persist trial state to disk (encrypted)."""
        if self._state is None:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        write_encrypted_json(self._state_path, self._state.to_dict())

    @property
    def state(self) -> TrialState:
        return self._load()

    def start_trial(
        self,
        org_id: str | None = None,
        trial_token: str | None = None,
        customer_email: str | None = None,
    ) -> TrialState:
        """Start a new trial. Called on first proxy start or license activation."""
        if trial_token and customer_email:
            from cutctx.billing.client import start_trial as server_start_trial

            server_start_trial(trial_token, customer_email)

        self._state = TrialState(started_at=time.time(), org_id=org_id, trial_token=trial_token)
        self._save()
        logger.info("Trial started for org=%s, expires in %d days", org_id, TRIAL_DAYS)
        return self._state

    def activate_license(self, org_id: str | None = None) -> None:
        """Mark trial as activated (user has a valid paid license)."""
        state = self._load()
        state.activated = True
        if org_id:
            state.org_id = org_id
        self._save()
        logger.info("Trial activated for org=%s", org_id)

    def check_trial(self) -> dict:
        """Check trial status and return enforcement info.

        Returns dict with:
            - active: bool — whether trial is still active
            - expired: bool — whether trial has expired
            - remaining_days: float — days remaining
            - elapsed_days: float — days elapsed
            - activated: bool — whether user has activated a paid license
        """
        state = self._load()

        # If user has activated a paid license, trial is irrelevant
        if state.activated:
            return {
                "active": False,
                "expired": False,
                "remaining_days": 0.0,
                "elapsed_days": state.elapsed_days,
                "activated": True,
            }

        # Try PitchToShip server-side trial verification first
        from cutctx_ee.billing.pitchtoship_client import is_configured, verify_trial_token

        if is_configured() and state.trial_token:
            pts_result = verify_trial_token(state.trial_token)
            if pts_result is not None:
                return {
                    "active": pts_result.get("valid", False),
                    "expired": not pts_result.get("valid", True),
                    "remaining_days": 14.0 if pts_result.get("valid") else 0.0,
                    "elapsed_days": state.elapsed_days,
                    "activated": False,
                }

        # Check server-side trial state if token is present
        if state.trial_token:
            from cutctx.billing.client import is_trial_active

            if is_trial_active(state.trial_token):
                return {
                    "active": True,
                    "expired": False,
                    "remaining_days": 14.0,  # Trust the server
                    "elapsed_days": state.elapsed_days,
                    "activated": False,
                }
            else:
                return {
                    "active": False,
                    "expired": True,
                    "remaining_days": 0.0,
                    "elapsed_days": state.elapsed_days,
                    "activated": False,
                }

        return {
            "active": not state.is_expired,
            "expired": state.is_expired,
            "remaining_days": state.remaining_days,
            "elapsed_days": state.elapsed_days,
            "activated": False,
        }

    def enforce_trial(self) -> bool:
        """Return True if user should be restricted to basic compression.

        Returns True when:
        - Trial has expired AND user hasn't activated a paid license
        """
        info = self.check_trial()
        if info["activated"]:
            return False
        return info["expired"]

    def remaining_days(self) -> float:
        """Return remaining trial days."""
        return self._load().remaining_days
