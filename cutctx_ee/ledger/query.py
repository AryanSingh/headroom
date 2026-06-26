# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from cutctx_ee.ledger.models import SpendEvent


class LedgerQuery:
    """Time-series query builder for spend ledger."""

    def __init__(self, session: Session):
        self.session = session

    def aggregate_spend(
        self,
        group_by: list[str],
        start_ts: int | None = None,
        end_ts: int | None = None,
        org_id: str | None = None,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> list[dict]:
        """Aggregate spend events by specified dimensions.

        Args:
            group_by: List of columns to group by (e.g. ['org_id', 'model']).
            start_ts: Optional start timestamp (inclusive).
            end_ts: Optional end timestamp (inclusive).
            org_id: Optional filter by org.
            workspace_id: Optional filter by workspace.
            project_id: Optional filter by project.
        """
        valid_group_columns = {
            "org_id": SpendEvent.org_id,
            "workspace_id": SpendEvent.workspace_id,
            "project_id": SpendEvent.project_id,
            "agent_id": SpendEvent.agent_id,
            "model": SpendEvent.model,
            "provider": SpendEvent.provider,
            "auth_mode": SpendEvent.auth_mode,
        }

        # Select columns: the group by columns + sum aggregates
        select_cols: list[Any] = []
        for col_name in group_by:
            if col_name in valid_group_columns:
                select_cols.append(valid_group_columns[col_name])

        select_cols.extend(
            [
                func.sum(SpendEvent.est_cost_usd).label("total_cost_usd"),
                func.sum(SpendEvent.est_cost_saved_usd).label("total_saved_usd"),
                func.sum(SpendEvent.input_tokens).label("total_input_tokens"),
                func.sum(SpendEvent.output_tokens).label("total_output_tokens"),
                func.sum(SpendEvent.tokens_saved).label("total_tokens_saved"),
                func.count(SpendEvent.id).label("request_count"),
            ]
        )

        query = self.session.query(*select_cols)

        # Apply filters
        if start_ts is not None:
            query = query.filter(SpendEvent.ts >= start_ts)
        if end_ts is not None:
            query = query.filter(SpendEvent.ts <= end_ts)
        if org_id is not None:
            query = query.filter(SpendEvent.org_id == org_id)
        if workspace_id is not None:
            query = query.filter(SpendEvent.workspace_id == workspace_id)
        if project_id is not None:
            query = query.filter(SpendEvent.project_id == project_id)

        # Apply group by
        for col_name in group_by:
            if col_name in valid_group_columns:
                query = query.group_by(valid_group_columns[col_name])

        results = query.all()

        # Convert to list of dicts
        output = []
        for row in results:
            row_dict = {}
            for i, col_name in enumerate(group_by):
                if col_name in valid_group_columns:
                    row_dict[col_name] = row[i]

            offset = len([c for c in group_by if c in valid_group_columns])
            row_dict["total_cost_usd"] = row[offset] or 0.0
            row_dict["total_saved_usd"] = row[offset + 1] or 0.0
            row_dict["total_input_tokens"] = row[offset + 2] or 0
            row_dict["total_output_tokens"] = row[offset + 3] or 0
            row_dict["total_tokens_saved"] = row[offset + 4] or 0
            row_dict["request_count"] = row[offset + 5] or 0

            output.append(row_dict)

        return output
