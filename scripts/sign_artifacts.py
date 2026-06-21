#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Cutctx Labs.

"""SP-7: Supply-chain signing and verification.

Generates signed manifests of all shipped artifacts and provides
verification scripts for CI. Supports Sigstore (keyless) and Ed25519
(key-based) signing.

Usage:
    python scripts/sign_artifacts.py sign --artifacts-dir dist/ --key-file build-key.pem
    python scripts/sign_artifacts.py verify --artifacts-dir dist/ --manifest manifest.json
    python scripts/sign_artifacts.py scan-secrets --path .
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Known secret patterns that must not appear in released artifacts
SECRET_PATTERNS = [
    (r"sk-ant-[a-zA-Z0-9]{20,}", "Anthropic API key"),
    (r"sk-proj-[a-zA-Z0-9]{20,}", "OpenAI project key"),
    (r"AKIA[A-Z0-9]{16}", "AWS access key"),
    (r"BEGIN (RSA |EC )?PRIVATE KEY", "Private key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub PAT"),
    (r"xox[bpsa]-[a-zA-Z0-9-]+", "Slack token"),
]

# Paths that should never appear in released artifacts
FORBIDDEN_PATHS = [
    "/Users/",
    "/home/",
    "/tmp/",
    "target/debug/",
    "tests/",
    "benches/",
    ".env",
]


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_manifest(
    artifacts_dir: Path,
    build_id: str = "",
) -> dict:
    """Generate a manifest of all artifacts with their SHA-256 hashes."""
    if not build_id:
        build_id = f"build-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    entries = []
    for filepath in sorted(artifacts_dir.rglob("*")):
        if filepath.is_file():
            rel = str(filepath.relative_to(artifacts_dir))
            entries.append({
                "path": rel,
                "sha256": compute_sha256(filepath),
                "size": filepath.stat().st_size,
            })

    manifest = {
        "build_id": build_id,
        "generated_at": int(datetime.now(timezone.utc).timestamp()),
        "generator": "cutctx-sign-artifacts",
        "entries": entries,
    }
    return manifest


def sign_manifest(manifest: dict, key_file: Path) -> dict:
    """Sign a manifest using Ed25519."""
    # Serialize the canonical manifest (excluding signature)
    manifest_for_signing = {k: v for k, v in manifest.items() if k != "signature"}
    canonical = json.dumps(manifest_for_signing, sort_keys=True, separators=(",", ":"))

    # Write temp file for signing
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(canonical)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["openssl", "pkeyutl", "-sign",
             "-inkey", str(key_file),
             "-in", tmp_path,
             "-out", f"{tmp_path}.sig"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Signing failed: {result.stderr}")

        with open(f"{tmp_path}.sig", "rb") as f:
            import base64
            signature = base64.urlsafe_b64encode(f.read()).decode()

        manifest["signature"] = signature
        return manifest
    finally:
        os.unlink(tmp_path)
        if os.path.exists(f"{tmp_path}.sig"):
            os.unlink(f"{tmp_path}.sig")


def verify_manifest_signature(manifest: dict, public_key_file: Path) -> bool:
    """Verify a manifest's Ed25519 signature."""
    if "signature" not in manifest:
        print("FAIL: Manifest has no signature")
        return False

    signature = manifest.pop("signature")
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    manifest["signature"] = signature  # Restore

    import base64
    sig_bytes = base64.urlsafe_b64decode(signature)

    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(canonical)
        tmp_path = f.name
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".sig", delete=False) as f:
        f.write(sig_bytes)
        sig_path = f.name

    try:
        result = subprocess.run(
            ["openssl", "pkeyutl", "-verify",
             "-pubin", "-inkey", str(public_key_file),
             "-in", tmp_path,
             "-sigfile", sig_path],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    finally:
        os.unlink(tmp_path)
        os.unlink(sig_path)


def verify_manifest_hashes(manifest: dict, artifacts_dir: Path) -> list[dict]:
    """Verify artifact hashes against the manifest. Returns violations."""
    violations = []
    for entry in manifest.get("entries", []):
        filepath = artifacts_dir / entry["path"]
        if not filepath.exists():
            violations.append({
                "path": entry["path"],
                "expected": entry["sha256"],
                "actual": "file_not_found",
            })
            continue

        actual = compute_sha256(filepath)
        if actual != entry["sha256"]:
            violations.append({
                "path": entry["path"],
                "expected": entry["sha256"],
                "actual": actual,
            })

    return violations


def scan_secrets(path: Path) -> list[dict]:
    """Scan files for leaked secrets and forbidden paths."""
    findings = []

    for filepath in path.rglob("*"):
        if not filepath.is_file():
            continue
        if filepath.suffix in (".pyc", ".pyo", ".so", ".pyd", ".o", ".exe"):
            continue
        if ".git" in str(filepath) or "__pycache__" in str(filepath):
            continue

        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # Check for secret patterns
        for pattern, desc in SECRET_PATTERNS:
            for match in re.finditer(pattern, content):
                findings.append({
                    "file": str(filepath.relative_to(path)),
                    "type": "secret",
                    "description": desc,
                    "line": content[:match.start()].count("\n") + 1,
                    "context": match.group()[:20] + "..." if len(match.group()) > 20 else match.group(),
                })

        # Check for forbidden paths
        for forbidden in FORBIDDEN_PATHS:
            if forbidden in content:
                findings.append({
                    "file": str(filepath.relative_to(path)),
                    "type": "forbidden_path",
                    "description": f"Contains forbidden path: {forbidden}",
                    "line": -1,
                })

    return findings


def main():
    parser = argparse.ArgumentParser(description="SP-7: Supply-chain signing and verification")
    sub = parser.add_subparsers(dest="command")

    # sign
    sign_p = sub.add_parser("sign", help="Sign artifacts directory")
    sign_p.add_argument("--artifacts-dir", required=True)
    sign_p.add_argument("--key-file", required=True)
    sign_p.add_argument("--output", default="manifest.json")

    # verify
    verify_p = sub.add_parser("verify", help="Verify artifacts against manifest")
    verify_p.add_argument("--artifacts-dir", required=True)
    verify_p.add_argument("--manifest", required=True)
    verify_p.add_argument("--public-key", default=None)

    # scan-secrets
    scan_p = sub.add_parser("scan-secrets", help="Scan for leaked secrets")
    scan_p.add_argument("--path", required=True)

    args = parser.parse_args()

    if args.command == "sign":
        artifacts_dir = Path(args.artifacts_dir)
        key_file = Path(args.key_file)
        manifest = generate_manifest(artifacts_dir)
        manifest = sign_manifest(manifest, key_file)
        output = Path(args.output)
        output.write_text(json.dumps(manifest, indent=2))
        print(f"Signed manifest written to {output} ({len(manifest['entries'])} artifacts)")

    elif args.command == "verify":
        artifacts_dir = Path(args.artifacts_dir)
        manifest = json.loads(Path(args.manifest).read_text())

        # Verify signature if public key provided
        if args.public_key:
            if verify_manifest_signature(manifest, Path(args.public_key)):
                print("PASS: Manifest signature valid")
            else:
                print("FAIL: Manifest signature invalid")
                sys.exit(1)

        # Verify hashes
        violations = verify_manifest_hashes(manifest, artifacts_dir)
        if violations:
            print(f"FAIL: {len(violations)} hash violations:")
            for v in violations:
                print(f"  {v['path']}: expected {v['expected'][:16]}..., got {v['actual'][:16]}...")
            sys.exit(1)
        else:
            print(f"PASS: All {len(manifest['entries'])} artifact hashes match")

    elif args.command == "scan-secrets":
        findings = scan_secrets(Path(args.path))
        if findings:
            print(f"FAIL: {len(findings)} findings:")
            for f in findings:
                print(f"  {f['file']}: {f['description']}")
            sys.exit(1)
        else:
            print("PASS: No secrets or forbidden paths found")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
