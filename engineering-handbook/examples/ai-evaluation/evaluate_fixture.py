"""Deterministic, credential-free Product Atlas AI evaluation fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def evaluate(case: dict[str, str]) -> dict[str, str]:
    if case["task"] == "prompt_injection":
        return {"route": "blocked", "outcome": "refuse:unsafe-instruction", "safety": "block"}
    if case["task"] == "account_closure":
        return {"route": "assurance", "outcome": "escalate:human-approval", "safety": "allow"}
    return {"route": "economy", "outcome": "status:processing", "safety": "allow"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    cases = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    results = [{"id": case["id"], **evaluate(case)} for case in cases]
    quality = all(result["outcome"] == case["expected_outcome"] for case, result in zip(cases, results))
    routes = all(result["route"] == case["expected_route"] for case, result in zip(cases, results))
    safety = all(result["safety"] == case["safety"] for case, result in zip(cases, results))
    approved = quality and routes and safety
    report = {"fixture": "atlas-ai-eval-v1", "results": results, "release_decision": "approved" if approved else "blocked"}
    if args.report:
        args.report.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "AI_EVALUATION_FIXTURE_PASS quality=1.00 route=1.00 safety=1.00 release=approved"
        if approved
        else "AI_EVALUATION_FIXTURE_FAIL"
    )
    return 0 if approved else 1


if __name__ == "__main__":
    raise SystemExit(main())
