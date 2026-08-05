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
from email.parser import BytesParser
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

        if wheel_path.name.endswith("-none-any.whl"):
            raise WheelVerificationError("compiled EE wheel must use a native platform tag")

        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        wheel_metadata_names = [name for name in names if name.endswith(".dist-info/WHEEL")]
        if len(metadata_names) != 1 or len(wheel_metadata_names) != 1:
            raise WheelVerificationError("wheel must contain exactly one METADATA and WHEEL file")
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        version = metadata.get("Version", "")
        if not version:
            raise WheelVerificationError("wheel METADATA is missing Version")
        required_core = f"cutctx-ai=={version}"
        declared_dependencies = set(metadata.get_all("Requires-Dist", []))
        if required_core not in declared_dependencies:
            raise WheelVerificationError(
                f"wheel METADATA must require exact core dependency {required_core}"
            )
        required_runtime_dependencies = {
            "cryptography>=41.0.0",
            "PyJWT[crypto]>=2.8.0",
            "sqlalchemy<3.0,>=2.0",
        }
        missing_runtime_dependencies = required_runtime_dependencies - declared_dependencies
        if missing_runtime_dependencies:
            raise WheelVerificationError(
                "wheel METADATA is missing EE runtime dependencies: "
                f"{sorted(missing_runtime_dependencies)}"
            )
        wheel_metadata = archive.read(wheel_metadata_names[0]).decode("utf-8", errors="replace")
        if "Root-Is-Purelib: false" not in wheel_metadata or "-none-any" in wheel_metadata:
            raise WheelVerificationError("compiled EE wheel must declare a native platform tag")

        source_leaks = [
            name
            for name in names
            if name.startswith(PACKAGE_PREFIX) and name.endswith(".py") and name != GENERATED_SOURCE
        ]
        if source_leaks:
            raise WheelVerificationError(f"EE source leaked into wheel: {sorted(source_leaks)}")

        unexpected_entries = []
        for name in names:
            if name.endswith("/") or ".dist-info/" in name:
                continue
            if name in {GENERATED_SOURCE, MANIFEST_NAME}:
                continue
            if name.startswith(PACKAGE_PREFIX) and name.endswith((".so", ".pyd")):
                if any(part.endswith(".build") for part in Path(name).parts):
                    unexpected_entries.append(name)
                continue
            unexpected_entries.append(name)
        if unexpected_entries:
            raise WheelVerificationError(
                f"unexpected wheel entries: {sorted(unexpected_entries)}"
            )

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
        "version": version,
        "verification_passed": True,
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
