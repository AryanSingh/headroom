"""Deterministic Product Atlas agent webhook integration evidence fixture.

Verifies HMAC signature verification over the original body, replay rejection
through a per-tenant event ledger, and authority-boundary enforcement: an agent
may prepare a preview but cannot execute a delivery without an approval token.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field

TENANT_SECRETS = {
    "tenant-a": "atlas-secret-a-2026",
    "tenant-b": "atlas-secret-b-2026",
}
EVENT_TYPE = "expense.export.requested"


def canonical_body(event: dict) -> bytes:
    """Deterministic JSON serialization used for signing and verification."""
    return json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(event: dict, secret: str) -> str:
    body = canonical_body(event)
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(event: dict, secret: str, signature: str) -> bool:
    expected = sign(event, secret)
    provided = signature.strip()
    if not provided.startswith("sha256="):
        return False
    return hmac.compare_digest(expected, provided)


@dataclass
class WebhookReceiver:
    """In-memory receiver with replay ledger and approval-gated tool use."""

    secrets: dict = field(default_factory=lambda: dict(TENANT_SECRETS))
    processed_events: set = field(default_factory=set)
    previews_created: int = 0
    deliveries_executed: int = 0

    def _replay_recorded(self, event: dict) -> bool:
        return event["event_id"] in self.processed_events

    def deliver(self, event: dict, signature: str, approval_token: str | None) -> tuple[str, str]:
        secret = self.secrets.get(event["tenant"])
        if secret is None:
            return "rejected", "tenant-unknown"
        if not verify_signature(event, secret, signature):
            return "rejected", "signature-mismatch"
        if self._replay_recorded(event):
            return "rejected", "replay"

        if event["type"] != EVENT_TYPE:
            return "rejected", "unsupported-event"

        # Authority boundary: prepare a preview, but never deliver funds or
        # export until a named finance approval token is presented.
        self.previews_created += 1
        self.processed_events.add(event["event_id"])
        if approval_token is None:
            return "preview-only", "approval-required"
        if approval_token != f"approve-{event['tenant']}":
            return "preview-only", "approval-token-invalid"
        self.deliveries_executed += 1
        return "executed", "finance-approved"


def main() -> None:
    receiver = WebhookReceiver()
    event = {
        "event_id": "evt-881",
        "tenant": "tenant-a",
        "type": EVENT_TYPE,
        "payload": {"export_id": "exp-12", "amount_cents": 4800},
    }
    signature = sign(event, TENANT_SECRETS["tenant-a"])

    # 1. Valid signed event: preview created, delivery held for finance approval.
    status, reason = receiver.deliver(event, signature, approval_token=None)
    assert (status, reason) == ("preview-only", "approval-required")
    assert receiver.previews_created == 1 and receiver.deliveries_executed == 0

    # 2. Altered body: any mutation breaks the original-body signature.
    altered = dict(event)
    altered["payload"] = {"export_id": "exp-12", "amount_cents": 999999}
    status, reason = receiver.deliver(altered, signature, approval_token=None)
    assert (status, reason) == ("rejected", "signature-mismatch")

    # 3. Replay: the same event_id is rejected even with a valid signature.
    status, reason = receiver.deliver(event, signature, approval_token=None)
    assert (status, reason) == ("rejected", "replay")
    assert receiver.previews_created == 1  # no second preview from the replay

    # 4. Authority boundary: a valid, non-replayed event still cannot execute
    #    without the correct approval token. The invalid-token attempt creates
    #    a preview and marks the event processed; a fresh event is used to
    #    prove that the correct token permits execution.
    second = {
        "event_id": "evt-882",
        "tenant": "tenant-a",
        "type": EVENT_TYPE,
        "payload": {"export_id": "exp-13", "amount_cents": 2500},
    }
    signature_second = sign(second, TENANT_SECRETS["tenant-a"])
    status, reason = receiver.deliver(second, signature_second, approval_token="approve-tenant-b")
    assert (status, reason) == ("preview-only", "approval-token-invalid")
    assert receiver.previews_created == 2 and receiver.deliveries_executed == 0

    third = {
        "event_id": "evt-883",
        "tenant": "tenant-a",
        "type": EVENT_TYPE,
        "payload": {"export_id": "exp-14", "amount_cents": 900},
    }
    signature_third = sign(third, TENANT_SECRETS["tenant-a"])
    status, reason = receiver.deliver(third, signature_third, approval_token="approve-tenant-a")
    assert (status, reason) == ("executed", "finance-approved")
    assert receiver.deliveries_executed == 1

    print(
        "AGENT_INTEGRATION_FIXTURE_PASS hmac-verified altered-rejected "
        "replay-rejected authority-boundary-enforced"
    )


if __name__ == "__main__":
    main()
