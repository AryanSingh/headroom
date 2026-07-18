"""License management CLI commands.

Provides activate, status, and upgrade commands for managing Cutctx licenses.
"""

from __future__ import annotations

import json
import logging
import webbrowser

import click

from .main import main

logger = logging.getLogger("cutctx.cli.license")


@main.group()
def license() -> None:
    """Manage your Cutctx license.

    Activate a license key, check status, or upgrade your plan.

    \b
    Examples:
        cutctx license activate hlk_abc123   Activate a license key
        cutctx license status                Show current license status
        cutctx license upgrade               Open upgrade page in browser
    """


@license.command()
@click.argument("license_key")
@click.option(
    "--cloud-url",
    envvar="PITCHTOSHIP_URL",
    default="https://pitchtoship.com",
    help="PitchToShip license server URL (env: PITCHTOSHIP_URL)",
)
@click.option(
    "--no-browser",
    is_flag=True,
    default=False,
    help="Skip opening the browser for confirmation.",
)
def activate(license_key: str, cloud_url: str, no_browser: bool) -> None:
    """Activate a license key.

    Validates the key against the Cutctx license server and stores it locally.
    The license key is validated immediately and the tier is applied.

    \b
    Examples:
        cutctx license activate hlk_abc123def456
        cutctx license activate hlk_abc123 --cloud-url https://custom.cutctx.dev
    """
    import httpx

    from cutctx import paths
    from cutctx.entitlements import EntitlementTier

    cloud_url = cloud_url.rstrip("/")

    click.echo("Validating license key...")
    click.echo(f"  Cloud URL: {cloud_url}")

    try:
        resp = httpx.post(
            f"{cloud_url}/v1/license/validate",
            json={"license_key": license_key},
            timeout=15.0,
        )
    except httpx.ConnectError:
        click.echo("Error: Could not connect to license server.", err=True)
        click.echo("Check your internet connection and try again.", err=True)
        raise SystemExit(1) from None
    except httpx.TimeoutException:
        click.echo("Error: License server timed out.", err=True)
        raise SystemExit(1) from None

    if resp.status_code == 200:
        data = resp.json()
        status = data.get("status", "invalid")
        plan = data.get("plan", "builder")
        org_name = data.get("org_name", "Unknown")
        org_id = data.get("org_id", "")

        tier = EntitlementTier.from_str(plan)

        # Cache the license locally (with HMAC integrity protection)
        from cutctx.security.state_crypto import write_hmac_json

        cache = {
            "license_key": license_key,
            "status": status,
            "plan": plan,
            "org_id": org_id,
            "org_name": org_name,
            "validated_at": resp.headers.get("date", ""),
        }
        cache_path = paths.license_cache_path()
        write_hmac_json(cache_path, cache)

        click.echo("")
        click.echo("License activated successfully!")
        click.echo(f"  Status:     {status}")
        click.echo(f"  Plan:       {tier.name} ({plan})")
        click.echo(f"  Org:        {org_name}")
        if org_id:
            click.echo(f"  Org ID:     {org_id}")

        # Show features available
        from cutctx.entitlements import EntitlementChecker

        checker = EntitlementChecker(plan)
        features = checker.list_features()
        click.echo(f"  Features:   {len(features)} available")

        click.echo(f"\n  License cached at: {cache_path}")

    elif resp.status_code == 401 or resp.status_code == 403:
        click.echo("Error: Invalid or expired license key.", err=True)
        click.echo(
            "Check your key and try again, or ask your Cutctx administrator for a fresh license.",
            err=True,
        )
        raise SystemExit(1) from None
    else:
        click.echo(f"Error: License server returned status {resp.status_code}.", err=True)
        click.echo(
            "Try again later or open an issue: https://github.com/AryanSingh/headroom/issues",
            err=True,
        )
        raise SystemExit(1) from None


@license.command()
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
def status(as_json: bool = False) -> None:
    """Show current license and trial status.

    Displays the active license tier, org info, trial status, and
    seat usage.
    """
    import json as _json

    from cutctx import paths
    from cutctx.entitlements import EntitlementChecker, EntitlementTier
    from cutctx.seats import SeatManager
    from cutctx.security.state_crypto import read_hmac_json
    from cutctx.trial import TrialManager

    cache_path = paths.license_cache_path()

    # --- Collect data ---

    license_info: dict[str, str | bool | None] = {}
    plan = "builder"

    if cache_path.exists():
        try:
            cache = read_hmac_json(cache_path)
            if cache is None:
                license_info["status"] = "unknown"
                license_info["integrity_failed"] = True
            else:
                plan = cache.get("plan", "builder")
                license_info["status"] = cache.get("status", "unknown")
                license_info["plan"] = plan
                license_info["org_name"] = cache.get("org_name", "Unknown")
                license_info["org_id"] = cache.get("org_id", "")
                license_info["validated_at"] = cache.get("validated_at", "unknown")
                license_info["integrity_failed"] = False
        except (_json.JSONDecodeError, KeyError):
            license_info["status"] = "corrupt"
            license_info["integrity_failed"] = True
    else:
        license_info["status"] = "none"
        license_info["plan"] = "builder"

    tm = TrialManager()
    trial = tm.check_trial()

    checker = EntitlementChecker(plan)
    tier = EntitlementTier.from_str(plan)

    sm = SeatManager()
    state = sm.state

    # --- Build result dict ---

    license_data = {}
    if license_info.get("status") == "active":
        license_data = {
            "status": license_info.get("status"),
            "plan": license_info.get("plan"),
            "org_name": license_info.get("org_name"),
            "org_id": license_info.get("org_id"),
            "validated_at": license_info.get("validated_at"),
        }
    elif license_info.get("status") == "none":
        license_data = {"status": "none", "plan": "builder"}
    elif license_info.get("status") == "unknown":
        license_data = {"status": "unknown", "plan": "builder"}
    elif license_info.get("status") == "corrupt":
        license_data = {"status": "corrupt", "plan": "builder"}

    if license_info.get("integrity_failed"):
        license_data["integrity_failed"] = True

    next_tier_name = None
    missing_features: list[str] = []
    if tier != EntitlementTier.ENTERPRISE:
        next_tier = EntitlementTier(tier.value + 1)
        next_tier_name = next_tier.name
        missing_features = checker.list_missing(next_tier)

    features_data = checker.list_features()

    result = {
        "license": license_data,
        "trial": {
            "activated": trial["activated"],
            "active": trial["active"],
            "expired": trial["expired"],
            "remaining_days": trial.get("remaining_days"),
            "elapsed_days": trial.get("elapsed_days"),
        },
        "features": {
            "available": len(features_data),
            "tier": tier.name,
            "next_tier": next_tier_name,
            "missing": missing_features[:10] if missing_features else [],
        },
        "seats": {
            "used": state.seats_used,
            "limit": state.seats_limit,
            "available": state.seats_available,
            "at_limit": state.is_at_limit,
        },
    }

    if as_json:
        click.echo(_json.dumps(result, indent=2, default=str))
        return

    # --- Formatted output ---

    click.echo("Cutctx License Status")
    click.echo("=" * 50)

    # License info (with HMAC integrity verification)
    if license_info.get("status") == "unknown" and license_info.get("integrity_failed"):
        click.echo("  License:    Unknown (integrity check failed — file may be tampered)")
    elif license_info.get("status") == "active":
        click.echo("  License:    Active")
        click.echo(f"  Plan:       {tier.name} ({plan})")
        click.echo(f"  Status:     {license_info.get('status')}")
        click.echo(f"  Org:        {license_info.get('org_name')}")
        if license_info.get("org_id"):
            click.echo(f"  Org ID:     {license_info.get('org_id')}")
        click.echo(f"  Validated:  {license_info.get('validated_at')}")
    elif license_info.get("status") == "corrupt":
        click.echo("  License:    Unknown (corrupt cache)")
    else:
        click.echo("  License:    None (using free tier)")

    # Trial info
    click.echo("")
    click.echo("Trial Status")
    click.echo("-" * 50)
    if trial["activated"]:
        click.echo("  Status:     Activated (paid license)")
    elif trial["active"]:
        click.echo(f"  Status:     Active ({trial['remaining_days']:.1f} days remaining)")
    elif trial["expired"]:
        click.echo("  Status:     EXPIRED — basic compression only")
        click.echo(f"  Elapsed:    {trial['elapsed_days']:.1f} days")
    else:
        click.echo("  Status:     Active")

    # Feature summary
    click.echo("")
    click.echo("Available Features")
    click.echo("-" * 50)
    click.echo(f"  {len(features_data)} features available")

    # Show missing features for next tier
    if tier != EntitlementTier.ENTERPRISE:
        next_tier = EntitlementTier(tier.value + 1)
        missing = checker.list_missing(next_tier)
        if missing:
            click.echo(f"\n  Upgrade to {next_tier.name} to unlock:")
            for f in missing[:10]:
                click.echo(f"    + {f}")
            if len(missing) > 10:
                click.echo(f"    ... and {len(missing) - 10} more")

    # Seat info
    click.echo("")
    click.echo("Seat Usage")
    click.echo("-" * 50)
    click.echo(f"  Used:       {state.seats_used}/{state.seats_limit}")
    click.echo(f"  Available:  {state.seats_available}")

    if state.is_at_limit:
        click.echo("  Warning:    At seat limit — upgrade for more seats")

    click.echo("")


@license.command()
@click.option(
    "--tier",
    type=click.Choice(["team", "business", "enterprise"], case_sensitive=False),
    default=None,
    help="Target tier to upgrade to. If not specified, suggests the next tier up.",
)
@click.option(
    "--open/--no-open",
    "auto_open",
    default=True,
    help="Automatically open the upgrade page in your browser.",
)
def upgrade(tier: str | None, auto_open: bool) -> None:
    """Open the upgrade page in your browser.

    Generates a checkout URL for upgrading your plan and opens it.
    """
    import json

    from cutctx import paths
    from cutctx.checkout import checkout_url, upgrade_url
    from cutctx.entitlements import EntitlementTier
    from cutctx.security.state_crypto import read_hmac_json

    # Determine current tier
    cache_path = paths.license_cache_path()
    current_plan = "builder"
    org_id = None
    if cache_path.exists():
        try:
            cache = read_hmac_json(cache_path)
            if cache:
                current_plan = cache.get("plan", "builder")
                org_id = cache.get("org_id")
        except (json.JSONDecodeError, KeyError):
            pass

    if tier:
        url = checkout_url(tier, org_id)
        target_name = tier
    else:
        url = upgrade_url(current_plan)
        current_tier = EntitlementTier.from_str(current_plan)
        if current_tier != EntitlementTier.ENTERPRISE:
            target_name = EntitlementTier(current_tier.value + 1).name
        else:
            target_name = "pricing"

    click.echo(f"Current plan:  {current_plan}")
    click.echo(f"Upgrading to:  {target_name}")
    click.echo(f"Checkout URL:  {url}")

    if auto_open:
        try:
            webbrowser.open(url)
            click.echo("\nOpened in browser.")
        except Exception:
            click.echo("\nCould not open browser. Visit the URL above manually.")
    else:
        click.echo("\nVisit the URL above to complete your upgrade.")


@license.command()
@click.option(
    "--tier",
    type=click.Choice(["builder", "team", "business", "enterprise"], case_sensitive=False),
    required=True,
    help="License tier to generate",
)
@click.option(
    "--org",
    required=True,
    help="Organization name",
)
@click.option(
    "--seats",
    type=int,
    default=1,
    help="Number of seats (default: 1)",
)
@click.option(
    "--expiry",
    help="Expiry date (YYYY-MM-DD format, optional)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Generate unsigned key without secret (for testing)",
)
def generate(tier: str, org: str, seats: int, expiry: str | None, dry_run: bool) -> None:
    """Generate a signed license key (admin only).

    Generates an HMAC-SHA256 signed license key for the specified tier.
    Requires CUTCTX_LICENSE_HMAC_SECRET to be set, unless --dry-run is used.

    The key format is: {prefix}-{payload}.{signature}
      - prefix: tier-based (bld-, team-, biz-, ent-)
      - payload: JSON with org, seats, expiry (base64url encoded)
      - signature: HMAC-SHA256 hex of the key portion

    \b
    Examples:
        cutctx license generate --tier team --org acme --seats 10
        cutctx license generate --tier enterprise --org widgetcorp --dry-run
        cutctx license generate --tier business --org startup --expiry 2026-12-31
    """
    import base64
    import hashlib
    import hmac
    import os
    from datetime import datetime

    def encode_payload(org_name: str, num_seats: int, exp_date: str | None = None) -> str:
        """Encode org_name, seats, and optional expiry as base64url JSON."""
        payload = {
            "org": org_name,
            "seats": num_seats,
        }
        if exp_date:
            payload["expiry"] = exp_date

        json_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        b64_bytes = base64.urlsafe_b64encode(json_bytes).rstrip(b"=")
        return b64_bytes.decode("ascii")

    def tier_to_prefix(tier_name: str) -> str:
        """Map tier name to license key prefix."""
        tier_lower = tier_name.lower()
        mapping = {
            "builder": "bld-",
            "team": "team-",
            "business": "biz-",
            "enterprise": "ent-",
        }
        if tier_lower not in mapping:
            raise ValueError(f"Unknown tier: {tier_name}")
        return mapping[tier_lower]

    # Validate expiry format if provided
    if expiry:
        try:
            datetime.strptime(expiry, "%Y-%m-%d")
        except ValueError as e:
            click.echo(f"Error: Invalid expiry date '{expiry}'. Use YYYY-MM-DD format.", err=True)
            raise SystemExit(1) from e

    # Get secret from environment or require --dry-run
    secret = None
    if not dry_run:
        secret = os.environ.get("CUTCTX_LICENSE_HMAC_SECRET")
        if not secret:
            click.echo(
                "Error: CUTCTX_LICENSE_HMAC_SECRET not set.\n"
                "Set the env var or use --dry-run to generate unsigned keys.",
                err=True,
            )
            raise SystemExit(1)

    try:
        prefix = tier_to_prefix(tier)
        payload = encode_payload(org, seats, expiry)
        unsigned_key = f"{prefix}{payload}"

        if secret:
            sig_bytes = hmac.new(
                secret.encode("utf-8"),
                unsigned_key.encode("utf-8"),
                hashlib.sha256,
            ).digest()
            sig_hex = sig_bytes.hex()
            signed_key = f"{unsigned_key}.{sig_hex}"
        else:
            signed_key = None

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e

    # Output
    click.echo("Cutctx License Key Generated")
    click.echo("=" * 60)
    click.echo(f"Tier:               {tier}")
    click.echo(f"Organization:       {org}")
    click.echo(f"Seats:              {seats}")
    if expiry:
        click.echo(f"Expiry:             {expiry}")
    else:
        click.echo("Expiry:             (none)")
    click.echo()

    if dry_run:
        click.echo("DRY RUN (unsigned key)")
        click.echo(f"Key:                {unsigned_key}")
    else:
        click.echo("Signed License Key")
        click.echo(f"Key:                {signed_key}")
        click.echo()
        click.echo("To activate this license, run:")
        click.echo(f"  cutctx license activate {signed_key}")
