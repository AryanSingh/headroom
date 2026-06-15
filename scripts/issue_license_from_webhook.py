#!/usr/bin/env python3
"""
Called by pitchtoship webhook when payment completes.

Input: JSON with {email, plan, billing, stripe_customer_id}
Output: Generates a license key and sends it to the customer email.

Usage:
    python scripts/issue_license_from_webhook.py --dry-run --plan starter --email test@example.com
    python scripts/issue_license_from_webhook.py --plan studio --email customer@company.com
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# License key format: {tier}-{base64_payload}.{hmac_hex}
# Tiers: team, business, enterprise

PLAN_TO_TIER = {
    "starter": "team",
    "studio": "business",
    "portfolio": "enterprise",
}

LICENSE_DB_PATH = os.environ.get(
    "CUTCTX_LICENSE_DB_PATH",
    os.path.expanduser("~/.cutctx/licenses_issued.db"),
)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def generate_license_key(tier: str, email: str, expiry_days: int = 365) -> str:
    """Generate a license key in the format {tier}-{base64_payload}.{hmac_hex}."""
    secret = os.environ.get("HEADROOM_LICENSE_HMAC_SECRET", "")
    if not secret:
        # Dev mode: generate a key without HMAC
        payload = {
            "tier": tier,
            "email": email,
            "expires": (
                datetime.now(timezone.utc) + timedelta(days=expiry_days)
            ).isoformat(),
            "issued": datetime.now(timezone.utc).isoformat(),
        }
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
        encoded = _b64url_encode(payload_bytes)
        return f"{tier}-{encoded}.dev"

    payload = {
        "tier": tier,
        "email": email,
        "expires": (
            datetime.now(timezone.utc) + timedelta(days=expiry_days)
        ).isoformat(),
        "issued": datetime.now(timezone.utc).isoformat(),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    encoded = _b64url_encode(payload_bytes)
    sig = hmac.new(secret.encode(), f"{tier}-{encoded}".encode(), hashlib.sha256).hexdigest()[
        :16
    ]
    return f"{tier}-{encoded}.{sig}"


def _init_db(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS licenses_issued (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            tier TEXT NOT NULL,
            license_key TEXT NOT NULL,
            stripe_customer_id TEXT,
            plan TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def record_license(
    email: str,
    tier: str,
    license_key: str,
    plan: str,
    stripe_customer_id: str | None = None,
    db_path: str | None = None,
) -> None:
    """Record issued license in SQLite DB."""
    path = db_path or LICENSE_DB_PATH
    conn = _init_db(path)
    now = datetime.now(timezone.utc).isoformat()
    expires = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
    conn.execute(
        "INSERT INTO licenses_issued (email, tier, license_key, stripe_customer_id, plan, issued_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (email, tier, license_key, stripe_customer_id, plan, now, expires),
    )
    conn.commit()
    conn.close()


def send_license_email(email: str, license_key: str, tier: str) -> bool:
    """Send license key via email. Returns True on success."""
    api_key = os.environ.get("RESEND_API_KEY") or os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        print(f"[DRY RUN] Would send email to {email} with key: {license_key}")
        return False

    try:
        import httpx

        subject = f"Your CutCtx {tier.title()} License Key"
        body = (
            f"Welcome to CutCtx!\n\n"
            f"Your {tier.title()} license key:\n\n"
            f"  {license_key}\n\n"
            f"To activate, run:\n"
            f"  cutctx license activate {license_key}\n\n"
            f"Or set the environment variable:\n"
            f"  export HEADROOM_LICENSE_KEY={license_key}\n\n"
            f"If you have any questions, reply to this email.\n\n"
            f"— The CutCtx Team"
        )

        if os.environ.get("RESEND_API_KEY"):
            resp = httpx.post(
                "https://api.resend.com/emails",
                json={
                    "from": "CutCtx <licenses@cutctx.dev>",
                    "to": [email],
                    "subject": subject,
                    "text": body,
                },
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
        else:
            resp = httpx.post(
                "https://api.sendgrid.com/v3/mail/send",
                json={
                    "personalizations": [{"to": [{"email": email}]}],
                    "from": {"email": "licenses@cutctx.dev", "name": "CutCtx"},
                    "subject": subject,
                    "content": [{"type": "text/plain", "value": body}],
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )

        return resp.status_code in (200, 201, 202)
    except Exception as e:
        print(f"Failed to send email: {e}", file=sys.stderr)
        return False


def handle_webhook_payload(
    payload: dict,
    dry_run: bool = False,
    db_path: str | None = None,
) -> dict:
    """
    Process a pitchtoship checkout.session.completed webhook payload.

    Returns: {"success": bool, "license_key": str|None, "error": str|None}
    """
    email = payload.get("email", "")
    plan = payload.get("plan", "")
    stripe_customer_id = payload.get("stripe_customer_id")

    if not email or not plan:
        return {"success": False, "license_key": None, "error": "Missing email or plan"}

    tier = PLAN_TO_TIER.get(plan)
    if not tier:
        return {"success": False, "license_key": None, "error": f"Unknown plan: {plan}"}

    license_key = generate_license_key(tier, email)

    if dry_run:
        print(f"[DRY RUN] Would issue: tier={tier}, email={email}, key={license_key}")
        return {"success": True, "license_key": license_key, "error": None}

    # Record in DB
    try:
        record_license(email, tier, license_key, plan, stripe_customer_id, db_path)
    except Exception as e:
        print(f"DB record failed: {e}", file=sys.stderr)

    # Send email
    email_sent = send_license_email(email, license_key, tier)

    return {
        "success": True,
        "license_key": license_key,
        "email_sent": email_sent,
        "error": None,
    }


def main():
    parser = argparse.ArgumentParser(description="Issue CutCtx license key from webhook")
    parser.add_argument("--plan", required=True, choices=list(PLAN_TO_TIER.keys()))
    parser.add_argument("--email", required=True)
    parser.add_argument("--stripe-customer-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args()

    payload = {
        "email": args.email,
        "plan": args.plan,
        "stripe_customer_id": args.stripe_customer_id,
    }

    result = handle_webhook_payload(payload, dry_run=args.dry_run, db_path=args.db_path)

    if result["success"]:
        print(json.dumps(result, indent=2))
    else:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
