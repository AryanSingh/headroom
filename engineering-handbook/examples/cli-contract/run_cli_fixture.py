"""Deterministic Product Atlas CLI contract runner for ./atlasctl.

Invokes the committed atlasctl fixture for the documented success path and the
protected-profile failure path, then prints a stable summary. The script never
reads a real credential store, never prompts, and never touches the network.
"""

from __future__ import annotations

import os
import subprocess
import sys


def _run_atlasctl(argv: list[str], profile: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("ATLAS_TOKEN", None)  # protected-profile path must prove it is absent
    env["ATLAS_PROFILE"] = profile
    env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    return subprocess.run(
        ["bash", "./atlasctl"] + argv,
        capture_output=True,
        text=True,
        env=env,
    )


def main() -> int:
    # 1. Documented success path: JSON stdout, profile staging, exit code 0.
    success = _run_atlasctl(["deploy", "--format", "json"], profile="staging")
    assert success.returncode == 0, success.stderr
    expected_json = '{"command":"deploy status","profile":"staging","status":"ready"}'
    assert success.stdout.strip() == expected_json, success.stdout

    # 2. Protected-profile failure path: production without ATLAS_TOKEN exits 77
    #    and reports an actionable error on stderr; stdout stays clean.
    protected = _run_atlasctl(["deploy", "--format", "json"], profile="production")
    assert protected.returncode == 77, protected.returncode
    assert "ATLAS_TOKEN is required for production" in protected.stderr
    assert protected.stdout.strip() == ""

    # 3. Text default remains stable for the development profile.
    text = _run_atlasctl(["deploy"], profile="development")
    assert text.returncode == 0, text.stderr
    assert text.stdout.strip() == "deploy status: ready (development)", text.stdout

    print("CLI_CONTRACT_FIXTURE_PASS success-json protected-profile-blocked exit-0-exit-77")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
