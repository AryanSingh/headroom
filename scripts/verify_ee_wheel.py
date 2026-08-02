#!/usr/bin/env python3
"""Verify a compiled Cutctx EE wheel without importing it.

The verifier operates only on the wheel archive. It proves that a signed
manifest covers the complete native payload that will be installed, and rejects
proprietary Python source from a compiled EE distribution.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any

PACKAGE_PREFIX = "cutctx_ee/"
MANIFEST_NAME = f"{PACKAGE_PREFIX}MANIFEST.sha256.json"
GENERATED_SOURCE = f"{PACKAGE_PREFIX}__init__.py"


class WheelVerificationError(RuntimeError):
    """Raised when a compiled EE wheel fails its release integrity contract."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _verify_signature(manifest: dict[str, Any], secret: str) -> None:
    signature = manifest.get("signature")
    if not isinstance(signature, str) or not signature:
        raise WheelVerificationError("MANIFEST is unsigned")
    payload = {key: value for key, value in manifest.items() if key != "signature"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    expected = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise WheelVerificationError("MANIFEST signature is invalid")


def verify_wheel(wheel_path: Path, secret: str) -> dict[str, object]:
    """Verify the signed native payload inside one compiled EE wheel."""
    if not secret:
        raise WheelVerificationError("release signing secret is required")

    with zipfile.ZipFile(wheel_path) as archive:
        names = archive.namelist()
        duplicate_names = {name for name in names if names.count(name) > 1}
        if duplicate_names:
            raise WheelVerificationError(f"duplicate wheel entries: {sorted(duplicate_names)}")
        if MANIFEST_NAME not in names:
            raise WheelVerificationError("MANIFEST is missing from wheel")

        source_leaks = [
            name
            for name in names
            if name.startswith(PACKAGE_PREFIX) and name.endswith(".py") and name != GENERATED_SOURCE
        ]
        if source_leaks:
            raise WheelVerificationError(f"EE source leaked into wheel: {sorted(source_leaks)}")

        raw_manifest = archive.read(MANIFEST_NAME)
        try:
            manifest = json.loads(raw_manifest)
        except json.JSONDecodeError as exc:
            raise WheelVerificationError("MANIFEST is not valid JSON") from exc
        if not isinstance(manifest, dict):
            raise WheelVerificationError("MANIFEST payload is not an object")
        _verify_signature(manifest, secret)

        manifest_files = manifest.get("files")
        if not isinstance(manifest_files, dict) or not manifest_files:
            raise WheelVerificationError("MANIFEST has no native file entries")
        if any(
            not isinstance(name, str) or not isinstance(value, str)
            for name, value in manifest_files.items()
        ):
            raise WheelVerificationError("MANIFEST file entries are invalid")

        native_names = sorted(
            name
            for name in names
            if name.startswith(PACKAGE_PREFIX) and name.endswith((".so", ".pyd"))
        )
        if not native_names:
            raise WheelVerificationError("wheel has no native EE modules")
        expected_names = sorted(f"{PACKAGE_PREFIX}{name}" for name in manifest_files)
        if native_names != expected_names:
            raise WheelVerificationError(
                "MANIFEST native module membership differs from wheel: "
                f"expected={expected_names}, actual={native_names}"
            )

        for archive_name in native_names:
            relative_name = archive_name.removeprefix(PACKAGE_PREFIX)
            actual = _sha256(archive.read(archive_name))
            expected = manifest_files[relative_name]
            if not hmac.compare_digest(actual, expected):
                raise WheelVerificationError(
                    f"MISMATCH: {relative_name} (expected {expected[:16]}…, got {actual[:16]}…)"
                )

    return {
        "wheel": wheel_path.name,
        "wheel_sha256": _sha256(wheel_path.read_bytes()),
        "manifest_sha256": _sha256(raw_manifest),
        "native_module_count": len(native_names),
        "native_modules": [name.removeprefix(PACKAGE_PREFIX) for name in native_names],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--secret-env", default="CUTCTX_LICENSE_HMAC_SECRET")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    secret = os.environ.get(args.secret_env, "")
    try:
        result = verify_wheel(args.wheel, secret)
    except (OSError, WheelVerificationError, zipfile.BadZipFile) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.evidence:
        args.evidence.write_text(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
