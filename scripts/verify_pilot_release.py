#!/usr/bin/env python3
"""Run and record the first-paid-pilot release evidence."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]
    required: bool = True
    timeout_seconds: int = 1200


CHECKS = (
    Check(
        "pilot-doc-contracts",
        (sys.executable, "-m", "pytest", "-q", "tests/test_pilot_release_docs.py"),
    ),
    Check(
        "network-and-deployment-security",
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_proxy_client_auth.py",
            "tests/test_agent_client_auth.py",
            "tests/test_cross_harness_client_auth_e2e.py",
            "tests/test_deployment_security.py",
            "tests/test_product_operator_contracts.py",
        ),
    ),
    Check(
        "license-and-sqlite-durability",
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_storage_backends.py",
            "cutctx_ee/tests/test_license_db.py",
            "tests/test_license_validation_contract.py",
            "tests/test_entitlement_request_path.py",
            "tests/test_management_api_entitlements.py",
        ),
    ),
    Check(
        "supported-provider-and-client-paths",
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_mcp_registry",
            "tests/test_model_router.py",
            "tests/test_provider_proxy_routes.py",
        ),
    ),
    Check(
        "python-lint",
        (
            sys.executable,
            "-m",
            "ruff",
            "check",
            "cutctx/proxy/client_auth.py",
            "tests/test_proxy_client_auth.py",
            "tests/test_product_operator_contracts.py",
            "tests/test_storage_backends.py",
            "cutctx_ee/tests/test_license_db.py",
            "tests/test_pilot_release_docs.py",
            "tests/test_verify_pilot_release.py",
            "scripts/verify_pilot_release.py",
        ),
    ),
    Check("dashboard-unit", ("npm", "test"), timeout_seconds=600),
    Check("dashboard-build", ("npm", "run", "build"), timeout_seconds=600),
    Check("rust-format", ("cargo", "fmt", "--all", "--", "--check"), timeout_seconds=600),
    Check("rust-tests", ("cargo", "test", "--workspace"), timeout_seconds=1800),
    Check(
        "version-contract",
        (sys.executable, "scripts/verify-versions.py"),
    ),
    Check(
        "commercial-license-boundary",
        (sys.executable, "scripts/assert_ee_spdx_headers.py"),
    ),
    Check(
        "helm-render",
        (
            "helm",
            "template",
            "pilot",
            "helm/cutctx",
            "--set",
            "enterprise.adminApiKey=pilot-admin-secret",
            "--set",
            "enterprise.proxyApiKey=pilot-proxy-secret",
            "--set",
            "enterprise.clientApiKey=pilot-client-secret",
        ),
    ),
    Check("docker-compose-config", ("docker", "compose", "config")),
)

EXTERNAL_SIGNOFFS = (
    "Contracting entity and approved pilot agreement",
    "Legal review of terms, privacy terms, and required DPA",
    "Payment or invoice confirmation",
    "Named support owner and response target",
    "Customer approval of data handling and telemetry",
    "Customer-cluster live provider, backup restore, and rollback acceptance",
)


def _command_environment(check: Check) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "CI": "true",
            "GIT_TERMINAL_PROMPT": "0",
            "PAGER": "cat",
            "CUTCTX_ADMIN_API_KEY": "pilot-admin-secret",
            "CUTCTX_PROXY_API_KEY": "pilot-proxy-secret",
            "CUTCTX_CLIENT_API_KEY": "pilot-client-secret",
        }
    )
    if check.name.startswith("dashboard-"):
        environment["npm_config_yes"] = "true"
    return environment


def run_check(check: Check) -> dict[str, object]:
    executable = shutil.which(check.command[0])
    if executable is None and not Path(check.command[0]).exists():
        return {
            "name": check.name,
            "command": list(check.command),
            "required": check.required,
            "status": "failed" if check.required else "skipped",
            "returncode": 127,
            "stdout_tail": "",
            "stderr_tail": f"Executable not found: {check.command[0]}",
        }

    working_directory = ROOT / "dashboard" if check.name.startswith("dashboard-") else ROOT
    try:
        completed = subprocess.run(
            check.command,
            cwd=working_directory,
            env=_command_environment(check),
            text=True,
            capture_output=True,
            timeout=check.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout if isinstance(error.stdout, str) else ""
        stderr = error.stderr if isinstance(error.stderr, str) else ""
        return {
            "name": check.name,
            "command": list(check.command),
            "required": check.required,
            "status": "failed",
            "returncode": 124,
            "stdout_tail": stdout[-4000:],
            "stderr_tail": (stderr + "\nCheck timed out.")[-4000:],
        }

    return {
        "name": check.name,
        "command": list(check.command),
        "required": check.required,
        "status": "passed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def _candidate_commit() -> str:
    completed = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def build_report(checks: Sequence[Check] = CHECKS) -> dict[str, object]:
    results = [run_check(check) for check in checks]
    required_failures = sum(
        1 for result in results if result["required"] and result["status"] != "passed"
    )
    optional_failures = sum(
        1 for result in results if not result["required"] and result["status"] == "failed"
    )
    return {
        "candidate_commit": _candidate_commit(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": required_failures == 0,
        "passed_count": sum(1 for result in results if result["status"] == "passed"),
        "failed": required_failures,
        "optional_failed": optional_failures,
        "skipped": sum(1 for result in results if result["status"] == "skipped"),
        "checks": results,
        "external_signoffs": [
            {"name": signoff, "status": "open"} for signoff in EXTERNAL_SIGNOFFS
        ],
    }


def write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List checks without running them")
    parser.add_argument("--output", type=Path, help="Write the JSON evidence report to this path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.list:
        for check in CHECKS:
            requirement = "required" if check.required else "optional"
            print(f"{check.name} [{requirement}]: {' '.join(check.command)}")
        return 0

    report = build_report()
    if args.output:
        write_report(args.output, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
