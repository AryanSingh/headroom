# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cutctx.storage.sqlite_schema import stamp_sqlalchemy_schema_version
from cutctx_ee.policy.models import Base, Policy

_SCHEMA_VERSION = 1


class PolicyStore:
    """Proprietary policy store."""

    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        stamp_sqlalchemy_schema_version(
            self.engine, expected=_SCHEMA_VERSION, store_name="policy store"
        )
        self.SessionLocal = sessionmaker(bind=self.engine)

    def get_policy(
        self,
        org_id: str,
        workspace_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Get the applicable policy for an org/workspace."""
        with self.SessionLocal() as session:
            query = session.query(Policy).filter(Policy.org_id == org_id)
            if workspace_id:
                # Prefer workspace specific, fallback to org wide
                ws_policy = query.filter(Policy.workspace_id == workspace_id).first()
                if ws_policy:
                    return self._to_dict(ws_policy)

            # Org wide policy
            org_policy = query.filter(Policy.workspace_id.is_(None)).first()
            if org_policy:
                return self._to_dict(org_policy)

        return None

    def upsert_policy(
        self,
        org_id: str,
        workspace_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create or update a policy."""
        with self.SessionLocal() as session:
            policy = (
                session.query(Policy)
                .filter(Policy.org_id == org_id, Policy.workspace_id == workspace_id)
                .first()
            )

            if not policy:
                policy = Policy(org_id=org_id, workspace_id=workspace_id, **kwargs)
                session.add(policy)
            else:
                for key, value in kwargs.items():
                    setattr(policy, key, value)
                policy.version += 1  # type: ignore[assignment,operator]

            session.commit()
            session.refresh(policy)
            return self._to_dict(policy)

    def _to_dict(self, policy: Policy) -> dict[str, Any]:
        return {
            "id": policy.id,
            "org_id": policy.org_id,
            "workspace_id": policy.workspace_id,
            "version": policy.version,
            "budget_limit_usd": policy.budget_limit_usd,
            "budget_period": policy.budget_period,
            "rpm_limit": policy.rpm_limit,
            "tpm_limit": policy.tpm_limit,
            "allowed_models": policy.allowed_models.split(",") if policy.allowed_models else None,
            "require_compression": policy.require_compression,
        }
