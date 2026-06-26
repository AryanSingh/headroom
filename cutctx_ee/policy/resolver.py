# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

from typing import Any

from cutctx_ee.policy.signer import sign_policy
from cutctx_ee.policy.store import PolicyStore


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

        # PR-P2-5: Dynamic budget enforcement
        # If a budget is set, check the actual spend in the ledger.
        # If spend >= budget, set rpm=0 to instruct the proxy to block requests.
        if policy_dict.get("budget_limit_usd") is not None:
            try:
                from datetime import datetime

                from cutctx_ee.ledger.api import get_store as get_ledger_store
                from cutctx_ee.ledger.query import LedgerQuery

                ledger_store = get_ledger_store()
                with ledger_store.SessionLocal() as session:
                    query_engine = LedgerQuery(session)

                    # Calculate start of period (e.g. MTD)
                    period = policy_dict.get("budget_period", "monthly").lower()
                    now = datetime.utcnow()

                    if period == "daily":
                        start_ts = int(
                            now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                        )
                    else:  # default monthly
                        start_ts = int(
                            now.replace(
                                day=1, hour=0, minute=0, second=0, microsecond=0
                            ).timestamp()
                        )

                    results = query_engine.aggregate_spend(
                        group_by=["org_id"],  # aggregate total org spend
                        start_ts=start_ts,
                        org_id=org_id,
                        workspace_id=workspace_id,
                    )

                    spend = results[0]["total_cost_usd"] if results else 0.0
                    payload["mtd_spend"] = spend

            except Exception as e:
                # If ledger is uninitialized or unavailable, proceed with static policy
                import logging

                logging.getLogger(__name__).warning(f"Failed to check budget ledger: {e}")

        return sign_policy(payload, kid=kid, private_key_hex=private_key_hex)
