#!/usr/bin/env python3
"""Generate OpenAPI schema from FastAPI app.

This script builds the Cutctx Proxy FastAPI application and extracts its
OpenAPI schema without starting a server. It supports a --check mode to
detect drift between the committed spec and the actual implementation.

Usage:
    python scripts/generate_openapi.py               # Generate and write spec
    python scripts/generate_openapi.py --check       # Check for drift (exit non-zero if changed)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Running ``python scripts/generate_openapi.py`` puts ``scripts/`` rather than
# the repository root first on sys.path.  CI installs the built wheel before
# running the drift test, so without this guard the generator can inspect that
# stale installed copy instead of the checked-out implementation.
project_root_str = str(PROJECT_ROOT)
if sys.path[0] != project_root_str:
    sys.path.insert(0, project_root_str)


def _setup_env() -> None:
    """Configure environment for app construction without starting a server."""
    # Skip upstream provider checks during schema generation
    os.environ.setdefault("CUTCTX_SKIP_UPSTREAM_CHECK", "1")
    # Use dummy admin key if required
    os.environ.setdefault("CUTCTX_ADMIN_API_KEY", "dummy-key-for-schema-generation")
    # Disable server startup
    os.environ.setdefault("CUTCTX_DISABLE_TELEMETRY", "1")


def _build_app() -> Any:
    """Build the FastAPI app without starting a server.

    Returns:
        The FastAPI application instance.

    Raises:
        ImportError: If FastAPI or required dependencies are unavailable.
        Exception: If app construction fails (typically due to missing dependencies
            or configuration).
    """
    try:
        import cutctx.orchestration as orchestration
        from cutctx.proxy.server import create_app
    except ImportError as exc:
        raise ImportError(
            "FastAPI or cutctx modules not available. "
            "Ensure the package is installed and dependencies are available."
        ) from exc

    try:
        # The committed artifact describes the always-available core API.
        # Optional orchestration dependencies may be installed in a developer
        # environment but absent in CI or a core deployment, so allowing their
        # auto-detection here makes schema generation environment-dependent.
        original_builder = orchestration.build_orchestration_service
        orchestration.build_orchestration_service = lambda: None
        try:
            return create_app()
        finally:
            orchestration.build_orchestration_service = original_builder
    except Exception as exc:
        # Provide helpful context for common failure modes
        print(f"ERROR: Failed to construct FastAPI app: {exc}", file=sys.stderr)
        raise


def _sort_dict_recursively(obj: Any) -> Any:
    """Recursively sort dictionary keys for deterministic output.

    Args:
        obj: The object to sort (dict, list, or scalar).

    Returns:
        The sorted object.
    """
    if isinstance(obj, dict):
        return {k: _sort_dict_recursively(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [_sort_dict_recursively(item) for item in obj]
    return obj


def generate_spec(app: Any) -> dict[str, Any]:
    """Generate the OpenAPI schema from the FastAPI app.

    Args:
        app: The FastAPI application instance.

    Returns:
        The OpenAPI schema as a dictionary.
    """
    openapi_schema = app.openapi()
    if openapi_schema is None:
        raise RuntimeError("App.openapi() returned None")

    # Normalise `info.version` out of the committed spec.
    #
    # `cutctx/_version.py` computes the version from commit history, so it
    # changes on essentially every commit. Leaving it in would make the
    # committed spec churn constantly and, worse, make the `--check` drift
    # gate fail on every unrelated commit — training everyone to ignore it.
    # The spec's job is to pin the API *shape*; the release version is
    # tracked by release-please, not here.
    info = openapi_schema.get("info")
    if isinstance(info, dict):
        info["version"] = "unversioned"

    return openapi_schema


def write_spec(spec: dict[str, Any], output_path: Path) -> None:
    """Write the OpenAPI spec to a JSON file.

    The file is written with sorted keys to ensure deterministic output
    across multiple runs.

    Args:
        spec: The OpenAPI schema dictionary.
        output_path: Path where the spec should be written.
    """
    # Sort all keys recursively for deterministic output
    sorted_spec = _sort_dict_recursively(spec)

    # Write as JSON (allows for easier tooling/validation)
    output_path.write_text(
        json.dumps(sorted_spec, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_spec(spec_path: Path) -> dict[str, Any]:
    """Read an existing OpenAPI spec from disk.

    Args:
        spec_path: Path to the spec file.

    Returns:
        The parsed OpenAPI schema.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    return json.loads(spec_path.read_text(encoding="utf-8"))


def check_drift(new_spec: dict[str, Any], existing_spec: dict[str, Any]) -> bool:
    """Check if the generated spec differs from the existing one.

    Args:
        new_spec: The newly generated spec.
        existing_spec: The existing committed spec.

    Returns:
        True if specs differ (drift detected), False if identical.
    """
    return json.dumps(new_spec, sort_keys=True) != json.dumps(existing_spec, sort_keys=True)


def _count_paths(spec: dict[str, Any]) -> int:
    """Count the number of paths in an OpenAPI spec.

    Args:
        spec: The OpenAPI schema.

    Returns:
        The count of paths.
    """
    return len(spec.get("paths", {}))


def main() -> int:
    """Main entry point.

    Returns:
        0 on success, non-zero on failure or drift detection.
    """
    parser = argparse.ArgumentParser(description="Generate OpenAPI schema from FastAPI app")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check mode: verify spec is up-to-date, exit non-zero if drift detected",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/openapi.json"),
        help="Output path for generated spec (default: artifacts/openapi.json)",
    )
    args = parser.parse_args()

    _setup_env()

    try:
        app = _build_app()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        new_spec = generate_spec(app)
    except Exception as exc:
        print(f"ERROR: Failed to generate OpenAPI schema: {exc}", file=sys.stderr)
        return 1

    new_path_count = _count_paths(new_spec)
    print(f"Generated spec with {new_path_count} paths")

    if args.check:
        # Check mode: compare with existing spec
        if not args.output.exists():
            print(f"ERROR: Spec file not found at {args.output}", file=sys.stderr)
            return 1

        try:
            existing_spec = read_spec(args.output)
        except Exception as exc:
            print(f"ERROR: Failed to read existing spec: {exc}", file=sys.stderr)
            return 1

        if check_drift(new_spec, existing_spec):
            existing_path_count = _count_paths(existing_spec)
            print("DRIFT DETECTED: spec has diverged from implementation")
            print(f"  Existing: {existing_path_count} paths")
            print(f"  Generated: {new_path_count} paths")
            return 1

        print("OK: Spec is up-to-date")
        return 0
    else:
        # Write mode: generate and write spec
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            write_spec(new_spec, args.output)
            print(f"Wrote spec to {args.output}")
            return 0
        except Exception as exc:
            print(f"ERROR: Failed to write spec: {exc}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    sys.exit(main())
