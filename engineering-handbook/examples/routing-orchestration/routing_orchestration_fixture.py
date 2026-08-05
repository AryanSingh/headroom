"""Deterministic Product Atlas routing fallback policy evidence fixture.

Verifies policy-match selection, latency/cost-bounded fallback, and fail-closed
queueing: a disallowed provider is never selected, and budget exhaustion queues
work instead of silently routing to an unapproved destination.
"""

from __future__ import annotations

from dataclasses import dataclass

POLICY_REVISION = "2026.08.1"


@dataclass(frozen=True)
class Provider:
    id: str
    regions: frozenset
    cost_per_job: int
    latency_ms: int


PROVIDERS = {
    "eu-fast-v2": Provider("eu-fast-v2", frozenset({"eu"}), cost_per_job=10, latency_ms=120),
    "eu-accurate-v1": Provider(
        "eu-accurate-v1", frozenset({"eu"}), cost_per_job=25, latency_ms=400
    ),
    "us-general-v3": Provider("us-general-v3", frozenset({"us"}), cost_per_job=5, latency_ms=90),
}


@dataclass(frozen=True)
class Job:
    id: str
    region: str
    classification: str
    cost_budget: int
    latency_bound_ms: int


@dataclass(frozen=True)
class Decision:
    job: str
    provider: str | None
    reason: str
    policy_revision: str
    queued: bool

    def render(self) -> str:
        provider = self.provider or "queue"
        return f"{self.job} -> {provider} ({self.reason})"


def decide(job: Job, available: dict[str, bool], timeout: dict[str, bool]) -> Decision:
    """Resolve a route under policy revision 2026.08.1.

    Ordering: preferred approved provider, then bounded fallback, then queue.
    A provider outside the approved region set is never reachable, so a
    fail-open default to us-general-v3 is structurally impossible.
    """
    approved_order = ["eu-fast-v2", "eu-accurate-v1"] if job.region == "eu" else []

    for provider_id in approved_order:
        provider = PROVIDERS[provider_id]
        if timeout.get(provider_id, False):
            continue
        if not available.get(provider_id, False):
            continue
        if provider.cost_per_job > job.cost_budget:
            continue
        if provider.latency_ms > job.latency_bound_ms:
            continue
        reason = "policy-match" if provider_id == approved_order[0] else "latency-bounded-fallback"
        return Decision(job.id, provider_id, reason, POLICY_REVISION, queued=False)

    # No approved provider is within budget and latency bounds: fail closed.
    for provider_id in approved_order:
        if timeout.get(provider_id, False):
            return Decision(job.id, None, "preferred-timeout", POLICY_REVISION, queued=True)
    return Decision(job.id, None, "budget-held", POLICY_REVISION, queued=True)


def main() -> None:
    # 1. Policy match: the preferred approved provider is available and in budget.
    eu_job = Job(
        id="job-3301",
        region="eu",
        classification="restricted-eu",
        cost_budget=20,
        latency_bound_ms=300,
    )
    decision = decide(eu_job, available={"eu-fast-v2": True}, timeout={})
    assert decision.provider == "eu-fast-v2" and decision.reason == "policy-match"
    assert not decision.queued and decision.policy_revision == POLICY_REVISION

    # 2. Latency-bounded fallback: the preferred provider times out and the
    #    approved fallback fits the cost and latency bounds, so it is selected
    #    instead of an unapproved provider.
    fallback_job = Job(
        id="job-3302",
        region="eu",
        classification="restricted-eu",
        cost_budget=30,
        latency_bound_ms=500,
    )
    decision = decide(
        fallback_job,
        available={"eu-fast-v2": False, "eu-accurate-v1": True},
        timeout={"eu-fast-v2": True},
    )
    assert decision.provider == "eu-accurate-v1" and decision.reason == "latency-bounded-fallback"
    assert not decision.queued

    # 3. Fail-closed on budget exhaustion: the fallback exceeds the cost budget,
    #    so the job queues with reason budget-held rather than routing to
    #    us-general-v3 (which is cheaper but outside the EU allowlist).
    tight_job = Job(
        id="job-3303",
        region="eu",
        classification="restricted-eu",
        cost_budget=12,
        latency_bound_ms=500,
    )
    decision = decide(
        tight_job,
        available={"eu-fast-v2": False, "eu-accurate-v1": True},
        timeout={},
    )
    assert decision.provider is None and decision.reason == "budget-held" and decision.queued

    # 4. Fail-closed on capacity absence: no approved provider is available at
    #    all; the job queues and the US route remains unreachable.
    decision = decide(
        eu_job,
        available={"eu-fast-v2": False, "eu-accurate-v1": False},
        timeout={},
    )
    assert decision.provider is None and decision.reason == "budget-held" and decision.queued
    assert PROVIDERS["us-general-v3"].regions.isdisjoint({eu_job.region})

    # 5. Fail-closed on latency bound: the fallback is too slow, so the job
    #    queues instead of exceeding its latency budget.
    slow_bound_job = Job(
        id="job-3305",
        region="eu",
        classification="restricted-eu",
        cost_budget=30,
        latency_bound_ms=300,
    )
    decision = decide(
        slow_bound_job,
        available={"eu-fast-v2": False, "eu-accurate-v1": True},
        timeout={"eu-fast-v2": True},
    )
    assert decision.provider is None and decision.reason == "preferred-timeout" and decision.queued

    print("ROUTING_FIXTURE_PASS policy-match latency-bounded-fallback budget-held-fail-closed")


if __name__ == "__main__":
    main()
