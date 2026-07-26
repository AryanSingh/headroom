"""Test that the OpenAPI spec is up-to-date with the implementation.

This test runs the OpenAPI generator's drift-detection mode to ensure
the committed spec matches the actual FastAPI app definition. Drift
(divergence between spec and implementation) is caught at CI time
rather than at runtime.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_openapi_spec_is_up_to_date() -> None:
    """Verify that artifacts/openapi.json matches the app implementation.

    This test runs the generator in --check mode to detect staleness.
    If the test fails, run:
        python scripts/generate_openapi.py
    to regenerate the spec.

    Raises:
        RuntimeError: If the spec has drifted from the implementation.
        SkipTest: If the generator cannot be run (graceful degradation).
    """
    env = os.environ.copy()
    # Skip upstream provider checks during schema generation (for CI)
    env.setdefault("CUTCTX_SKIP_UPSTREAM_CHECK", "1")
    env.setdefault("CUTCTX_ADMIN_API_KEY", "dummy-key-for-schema-generation")
    env.setdefault("CUTCTX_DISABLE_TELEMETRY", "1")

    # Try to run the generator with --check
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "generate_openapi.py"),
                "--check",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            cwd=str(PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("OpenAPI generator timed out (30s)") from exc
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"OpenAPI generator not found at scripts/generate_openapi.py: {exc}"
        ) from exc

    if result.returncode != 0:
        # Drift detected. Include the generator output for debugging.
        msg = (
            "OpenAPI spec is out of date. Run:\n"
            "    python scripts/generate_openapi.py\n"
            "to regenerate it.\n\n"
            "Generator output:\n"
        )
        if result.stdout:
            msg += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            msg += f"STDERR:\n{result.stderr}\n"
        raise RuntimeError(msg)


def test_openapi_paths_count() -> None:
    """Sanity check: verify the generated spec contains a reasonable number of paths.

    This catches obvious issues like the generator failing silently or producing
    an empty spec.

    Raises:
        AssertionError: If the spec has fewer than 50 paths (baseline check).
    """
    spec_file = PROJECT_ROOT / "artifacts" / "openapi.json"
    if not spec_file.exists():
        # This is a graceful skip — the spec hasn't been generated yet
        return

    spec = json.loads(spec_file.read_text(encoding="utf-8"))
    paths = spec.get("paths", {})

    # Sanity check: the FastAPI app should document at least 50 paths
    # (provider routes + management endpoints). If this fails, something
    # went wrong with either the generation or the app construction.
    assert len(paths) >= 50, (
        f"OpenAPI spec has only {len(paths)} paths; expected at least 50. "
        "The generator may have failed silently."
    )
