"""Best-effort task-quality feedback for live savings canary evaluations."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class CanaryFeedbackReporter:
    """Posts one idempotent feedback event per completed evaluation task."""

    def __init__(self) -> None:
        self.base_url = os.environ.get("CUTCTX_SAVINGS_CANARY_FEEDBACK_URL", "").rstrip("/")
        self.admin_key = os.environ.get("CUTCTX_ADMIN_API_KEY", "")
        self.arm = os.environ.get("CUTCTX_SAVINGS_CANARY_EVAL_ARM", "").strip()
        self.evaluator = os.environ.get("CUTCTX_SAVINGS_CANARY_EVALUATOR", "coding-eval-v1")
        self.run_id = os.environ.get("CUTCTX_SAVINGS_CANARY_EVAL_RUN_ID") or uuid.uuid4().hex

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.admin_key and self.arm)

    def report(
        self,
        *,
        task_id: str,
        quality_success: bool,
        request_id: str | None = None,
        retries: int = 0,
        user_corrections: int = 0,
    ) -> bool:
        if not self.enabled:
            return False
        payload: dict[str, Any] = {
            "event_id": f"{self.run_id}/{task_id}",
            "request_id": request_id,
            "arm": self.arm,
            "quality_success": bool(quality_success),
            "retries": max(0, int(retries)),
            "user_corrections": max(0, int(user_corrections)),
            "evaluator": self.evaluator,
            "evaluated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        try:
            import httpx

            response = httpx.post(
                f"{self.base_url}/savings-canary/feedback",
                headers={"Authorization": f"Bearer {self.admin_key}"},
                json=payload,
                timeout=5.0,
            )
            response.raise_for_status()
            return True
        except Exception:  # evaluator telemetry must never turn into a task failure
            logger.warning(
                "Savings canary feedback delivery failed for task %s; treating as missing data",
                task_id,
                exc_info=True,
            )
            return False


__all__ = ["CanaryFeedbackReporter"]
