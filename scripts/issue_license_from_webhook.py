#!/usr/bin/env python3
"""
Called by pitchtoship Stripe webhook when checkout.session.completed fires.
Can also be called manually for license issuance.

Usage:
  python scripts/issue_license_from_webhook.py \
    --plan starter --email customer@example.com \
    --org "Acme Corp" --stripe-customer-id cus_xxx [--dry-run]
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEV_SECRET = "dev-secret-do-not-use-in-production"

# Plan -> tier mapping (inverse of headroom/billing.py TIER_TO_PLAN)
PLAN_TO_TIER = {
    "starter": "team",
    "studio": "business",
    "portfolio": "enterprise",
}

# Tier -> default seat count (0 = unlimited)
TIER_TO_SEATS = {
    "team": 5,
    "business": 25,
    "enterprise": 0,
}

# ---------------------------------------------------------------------------
# License key generation (same HMAC logic as generate_license.py)
# ---------------------------------------------------------------------------

def encode_payload(org_name: str, seats: int, expiry: str | None = None) -> str:
    """Encode org_name, seats, and optional expiry as base64url JSON."""
    payload: dict = {
        "org": org_name,
        "seats": seats if seats > 0 else "unlimited",
    }
    if expiry:
        payload["expiry"] = expiry

    json_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    b64_bytes = base64.urlsafe_b64encode(json_bytes).rstrip(b"=")
    return b64_bytes.decode("ascii")


def tier_to_prefix(tier: str) -> str:
    """Map tier name to license key prefix."""
    mapping = {
        "builder": "bld-",
        "team": "team-",
        "business": "biz-",
        "enterprise": "ent-",
    }
    tier_lower = tier.lower()
    if tier_lower not in mapping:
        raise ValueError(
            f"Unknown tier: {tier}. Must be one of: builder, team, business, enterprise"
        )
    return mapping[tier_lower]


def generate_license_key(
    tier: str,
    org_name: str,
    seats: int,
    expiry: str | None,
    secret: str | None,
) -> str:
    """Generate a signed (or placeholder for dry-run) license key.

    Format: {prefix}{b64_payload}.{hmac_hex}
    The '.' separator is always present, matching generate_license.py.
    """
    prefix = tier_to_prefix(tier)
    payload = encode_payload(org_name, seats, expiry)
    unsigned_key = f"{prefix}{payload}"

    if secret is None:
        # Dry-run: return key with placeholder sig so '.' separator is always present
        return f"{unsigned_key}.dryrun"

    sig_bytes = hmac.new(
        secret.encode("utf-8"),
        unsigned_key.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{unsigned_key}.{sig_bytes.hex()}"


# ---------------------------------------------------------------------------
# SQLite logging (~/.cutctx/licenses_issued.db)
# ---------------------------------------------------------------------------

def get_db_path() -> Path:
    db_dir = Path.home() / ".cutctx"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "licenses_issued.db"


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS licenses (
            id                 INTEGER PRIMARY KEY,
            email              TEXT,
            org                TEXT,
            plan               TEXT,
            tier               TEXT,
            license_key        TEXT,
            stripe_customer_id TEXT,
            issued_at          TEXT
        )
        """
    )
    conn.commit()


def log_license(
    email: str,
    org: str,
    plan: str,
    tier: str,
    license_key: str,
    stripe_customer_id: str | None,
    issued_at: str,
) -> None:
    db_path = get_db_path()
    with sqlite3.connect(str(db_path)) as conn:
        init_db(conn)
        conn.execute(
            """
            INSERT INTO licenses
                (email, org, plan, tier, license_key, stripe_customer_id, issued_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (email, org, plan, tier, license_key, stripe_customer_id, issued_at),
        )
        conn.commit()
    print(f"[db] License logged to {db_path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Email delivery via Resend (stdlib urllib, no third-party deps)
# ---------------------------------------------------------------------------

EMAIL_SUBJECT = "Your CutCtx license key is ready"


def build_email_body(license_key: str, org: str) -> str:
    return (
        f"Hi {org},\n\n"
        "Your CutCtx license key is ready. Here are your activation instructions:\n\n"
        f"License Key:\n  {license_key}\n\n"
        "1. Install CutCtx:\n"
        "   pip install cutctx-ai\n\n"
        "2. Activate your license:\n"
        f"   cutctx license activate {license_key}\n\n"
        "3. Full documentation:\n"
        "   https://cutctx.dev/docs\n\n"
        "If you have any questions, reply to this email or visit https://cutctx.dev/docs.\n\n"
        "-- The CutCtx Team\n"
    )


def send_email_resend(to_email: str, org: str, license_key: str, api_key: str) -> bool:
    """Send license email via Resend API (stdlib urllib only). Returns True on success."""
    import urllib.request

    payload = json.dumps(
        {
            "from": "CutCtx <licenses@cutctx.dev>",
            "to": [to_email],
            "subject": EMAIL_SUBJECT,
            "text": build_email_body(license_key, org),
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.getcode() in (200, 201):
                print(f"[email] Sent via Resend to {to_email}", file=sys.stderr)
                return True
            print(
                f"[email] Resend returned unexpected status {resp.getcode()}",
                file=sys.stderr,
            )
            return False
    except Exception as exc:
        print(f"[email] Resend delivery failed: {exc}", file=sys.stderr)
        return False


def deliver_license(to_email: str, org: str, license_key: str) -> None:
    """Try Resend; fall back to printing the email body to stdout."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    if api_key:
        if send_email_resend(to_email, org, license_key, api_key):
            return
        print("[email] Falling back to stdout delivery", file=sys.stderr)
    else:
        print(
            "[email] RESEND_API_KEY not set -- printing email to stdout",
            file=sys.stderr,
        )

    print()
    print("=" * 60)
    print(f"TO:      {to_email}")
    print(f"SUBJECT: {EMAIL_SUBJECT}")
    print("-" * 60)
    print(build_email_body(license_key, org))
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Issue a CutCtx license key (Stripe webhook handler / manual issuance)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--plan",
        required=True,
        choices=["starter", "studio", "portfolio"],
        help="PitchToShip plan (starter->team, studio->business, portfolio->enterprise)",
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Customer email address",
    )
    parser.add_argument(
        "--org",
        required=True,
        help="Organization / company name (embedded in the license payload)",
    )
    parser.add_argument(
        "--stripe-customer-id",
        default=None,
        dest="stripe_customer_id",
        help="Stripe customer ID (e.g. cus_xxx)",
    )
    parser.add_argument(
        "--seats",
        type=int,
        default=None,
        help=(
            "Override seat count "
            "(defaults: team=5, business=25, enterprise=unlimited)"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and print key without sending email or writing to DB",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Map plan -> tier
    tier = PLAN_TO_TIER[args.plan]

    # Determine seat count
    seats = args.seats if args.seats is not None else TIER_TO_SEATS[tier]

    # Expiry: 1 year from today (UTC)
    expiry = (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d")

    # Check for Ed25519 Issuer Config
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from headroom_ee.billing.license_token import get_default_issuer_config, sign_license

    kid, priv_hex = get_default_issuer_config()

    if kid and priv_hex:
        if args.dry_run:
            print("[warn] dry-run for hrk1 token uses real keys but does not email/log", file=sys.stderr)

        extra = {"org": args.org, "seats": seats if seats > 0 else "unlimited"}
        if expiry:
            extra["expiry"] = expiry

        try:
            license_key = sign_license(tier, kid, priv_hex, extra)
        except Exception as e:
            print(f"Error signing hrk1 license: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Resolve HMAC secret
        secret: str | None = os.environ.get("HEADROOM_LICENSE_HMAC_SECRET") or ""
        if not secret:
            if args.dry_run:
                secret = None  # unsigned placeholder
                print(
                    "[warn] HEADROOM_LICENSE_HMAC_SECRET not set -- dry-run key is UNSIGNED",
                    file=sys.stderr,
                )
            else:
                secret = DEV_SECRET
                print(
                    "[warn] Neither Ed25519 nor HMAC secret set -- using dev fallback HMAC secret. "
                    "DO NOT use this key in production.",
                    file=sys.stderr,
                )

        # Generate legacy license key
        license_key = generate_license_key(
            tier=tier,
            org_name=args.org,
            seats=seats,
            expiry=expiry,
            secret=secret,
        )

    issued_at = datetime.utcnow().isoformat() + "Z"

    # Always print the key to stdout
    print(license_key)

    if args.dry_run:
        seats_display = "unlimited" if seats == 0 else str(seats)
        print(
            f"\n[dry-run] plan={args.plan} tier={tier} "
            f"seats={seats_display} expiry={expiry}",
            file=sys.stderr,
        )
        print(f"[dry-run] email={args.email} org={args.org}", file=sys.stderr)
        print("[dry-run] No email sent, no DB write.", file=sys.stderr)
        return

    # Log to SQLite
    log_license(
        email=args.email,
        org=args.org,
        plan=args.plan,
        tier=tier,
        license_key=license_key,
        stripe_customer_id=args.stripe_customer_id,
        issued_at=issued_at,
    )

    # Send email
    deliver_license(to_email=args.email, org=args.org, license_key=license_key)


if __name__ == "__main__":
    main()
