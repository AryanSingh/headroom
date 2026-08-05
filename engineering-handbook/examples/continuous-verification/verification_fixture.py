"""Deterministic Product Atlas release-gate fixture; no services or network required."""

from __future__ import annotations


def release_decision(checks: dict[str, bool], evidence: dict[str, str]) -> str:
    """Block every failed check until its immutable evidence reference is present."""
    failed = [check_id for check_id, passed in checks.items() if not passed]
    if failed and not all(evidence.get(check_id) for check_id in failed):
        return "blocked-missing-evidence"
    return "blocked" if failed else "approved"


def main() -> None:
    checks = {"unit": True, "migration-reconciliation": False, "security": True}
    assert release_decision(checks, {}) == "blocked-missing-evidence"
    evidence = {"migration-reconciliation": "EV-ATLAS-042"}
    assert release_decision(checks, evidence) == "blocked"
    checks["migration-reconciliation"] = True
    assert release_decision(checks, evidence) == "approved"
    print("CONTINUOUS_VERIFICATION_FIXTURE_PASS failed-check-blocked evidence-linked promotion-approved")


if __name__ == "__main__":
    main()
