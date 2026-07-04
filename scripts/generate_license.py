#!/usr/bin/env python3
"""Generate signed Cutctx license keys.

This script generates HMAC-SHA256 signed license keys matching the format
expected by the Rust proxy validator (config.rs).

Format: {prefix}-{payload}.{signature}
  - prefix: tier-based (ent-, biz-, team-, bld-)
  - payload: JSON with org, seats, expiry (base64url encoded)
  - signature: HMAC-SHA256 hex of {prefix}-{payload}

Environment:
  CUTCTX_LICENSE_HMAC_SECRET: The shared secret for signing (required unless --dry-run)

Examples:
  # Generate a team license
  export CUTCTX_LICENSE_HMAC_SECRET=my_secret
  python scripts/generate_license.py --tier team --org acme --seats 10

  # Dry run without secret
  python scripts/generate_license.py --tier business --org widgetcorp --dry-run
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime


def encode_payload(org_name: str, seats: int, expiry: str | None = None) -> str:
    """Encode org_name, seats, and optional expiry as base64url JSON."""
    payload = {
        "org": org_name,
        "seats": seats,
    }
    if expiry:
        payload["expiry"] = expiry

    json_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    b64_bytes = base64.urlsafe_b64encode(json_bytes).rstrip(b"=")
    return b64_bytes.decode("ascii")


def tier_to_prefix(tier: str) -> str:
    """Map tier name to license key prefix."""
    tier_lower = tier.lower()
    mapping = {
        "builder": "bld-",
        "team": "team-",
        "business": "biz-",
        "enterprise": "ent-",
    }
    if tier_lower not in mapping:
        raise ValueError(
            f"Unknown tier: {tier}. Must be one of: builder, team, business, enterprise"
        )
    return mapping[tier_lower]


def generate_license_key(
    tier: str,
    org_name: str,
    seats: int,
    expiry: str | None = None,
    secret: str | None = None,
) -> tuple[str, str]:
    """Generate a signed HMAC license key."""
    prefix = tier_to_prefix(tier)
    payload = encode_payload(org_name, seats, expiry)
    unsigned_key = f"{prefix}{payload}"

    if secret is None:
        return unsigned_key, None

    # Sign with HMAC-SHA256, use first 32 hex chars (128 bits).
    # The Rust verifier (crates/cutctx-core/src/licensing.rs) compares
    # exactly SIG_HEX_LEN=32 chars with constant-time XOR fold.
    _SIG_HEX_LEN = 32
    sig_bytes = hmac.new(
        secret.encode("utf-8"),
        unsigned_key.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sig_hex = sig_bytes.hex()[:_SIG_HEX_LEN]

    signed_key = f"{unsigned_key}.{sig_hex}"
    return unsigned_key, signed_key


def main():
    parser = argparse.ArgumentParser(
        description="Generate HMAC-signed or Ed25519-signed Cutctx license keys",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--tier",
        required=True,
        choices=["builder", "team", "business", "enterprise"],
        help="License tier",
    )
    parser.add_argument(
        "--org",
        required=True,
        help="Organization name",
    )
    parser.add_argument(
        "--seats",
        type=int,
        default=1,
        help="Number of seats (default: 1)",
    )
    parser.add_argument(
        "--expiry",
        help="Expiry date (YYYY-MM-DD format, optional)",
    )
    parser.add_argument(
        "--algo",
        choices=["hmac", "ed25519"],
        default="hmac",
        help="Signing algorithm (default: hmac)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate unsigned key without secret (for testing, HMAC only)",
    )

    args = parser.parse_args()

    # Validate expiry format if provided
    if args.expiry:
        try:
            datetime.strptime(args.expiry, "%Y-%m-%d")
        except ValueError:
            print(
                f"Error: Invalid expiry date '{args.expiry}'. Use YYYY-MM-DD format.",
                file=sys.stderr,
            )
            sys.exit(1)

    if args.algo == "ed25519":
        if args.dry_run:
            print("Error: dry-run not supported for ed25519.", file=sys.stderr)
            sys.exit(1)

        kid = os.environ.get("CUTCTX_LICENSE_KID")
        priv_hex = os.environ.get("CUTCTX_LICENSE_PRIVATE_KEY")
        if not kid or not priv_hex:
            print(
                "Error: CUTCTX_LICENSE_KID and CUTCTX_LICENSE_PRIVATE_KEY must be set for ed25519.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Add cutctx_ee path
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from cutctx_ee.billing.license_token import sign_license

        try:
            extra = {"org": args.org, "seats": args.seats}
            if args.expiry:
                extra["expiry"] = args.expiry
            signed_key = sign_license(args.tier, kid, priv_hex, extra)
            unsigned_key = "hrk1 token"
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # HMAC
        secret = None
        if not args.dry_run:
            secret = os.environ.get("CUTCTX_LICENSE_HMAC_SECRET")
            if not secret:
                print(
                    "Error: CUTCTX_LICENSE_HMAC_SECRET not set.\n"
                    "Set the env var or use --dry-run to generate unsigned keys.",
                    file=sys.stderr,
                )
                sys.exit(1)

        try:
            unsigned_key, signed_key = generate_license_key(
                tier=args.tier,
                org_name=args.org,
                seats=args.seats,
                expiry=args.expiry,
                secret=secret,
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Output
    print("Cutctx License Key Generated")
    print("=" * 60)
    print(f"Tier:               {args.tier}")
    print(f"Organization:       {args.org}")
    print(f"Seats:              {args.seats}")
    if args.expiry:
        print(f"Expiry:             {args.expiry}")
    else:
        print("Expiry:             (none)")
    print()

    if args.dry_run:
        print("DRY RUN (unsigned key)")
        print(f"Key:                {unsigned_key}")
    else:
        print("Signed License Key")
        print(f"Key:                {signed_key}")
        print()
        print("To activate this license, run:")
        print(f"  cutctx license activate {signed_key}")


if __name__ == "__main__":
    main()
