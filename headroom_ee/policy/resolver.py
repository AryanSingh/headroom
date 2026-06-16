from typing import Any

from headroom_ee.policy.signer import sign_policy
from headroom_ee.policy.store import PolicyStore


class PolicyResolver:
    """Resolves and signs policies for the offline proxy cache."""

    def __init__(self, store: PolicyStore):
        self.store = store

    def resolve_and_sign(
        self,
        org_id: str,
        workspace_id: str | None = None,
        kid: str | None = None,
        private_key_hex: str | None = None,
    ) -> str | None:
        """Fetch the applicable policy, structure the payload, and sign it."""
        policy_dict = self.store.get_policy(org_id, workspace_id)
        if not policy_dict:
            return None

        # Build payload for the Rust proxy
        # Exclude nulls to save space
        payload: dict[str, Any] = {"v": policy_dict["version"]}

        if policy_dict.get("budget_limit_usd") is not None:
            payload["budget_usd"] = policy_dict["budget_limit_usd"]
            payload["budget_period"] = policy_dict.get("budget_period", "daily")

        if policy_dict.get("rpm_limit") is not None:
            payload["rpm"] = policy_dict["rpm_limit"]

        if policy_dict.get("tpm_limit") is not None:
            payload["tpm"] = policy_dict["tpm_limit"]

        if policy_dict.get("allowed_models") is not None:
            payload["models"] = policy_dict["allowed_models"]

        if policy_dict.get("require_compression"):
            payload["req_comp"] = True

        # Sign it
        return sign_policy(payload, kid=kid, private_key_hex=private_key_hex)
