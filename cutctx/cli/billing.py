"""Billing management CLI commands.

Provides checkout and billing portal commands for managing Cutctx subscriptions
through the PitchToShip billing system.
"""

from __future__ import annotations

import logging
import webbrowser

import click

from .main import main

logger = logging.getLogger("cutctx.cli.billing")


@main.group()
def billing() -> None:
    """Manage your Cutctx billing and subscriptions.

    Open checkout pages for upgrading plans or manage your billing account.

    \b
    Examples:
        cutctx billing checkout --tier team              Open checkout for Team plan
        cutctx billing portal --email user@example.com   Open billing portal
    """


@billing.command()
@click.option(
    "--tier",
    type=click.Choice(["team", "business", "enterprise"], case_sensitive=False),
    default="team",
    help="Target tier to upgrade to (default: team).",
)
@click.option(
    "--email",
    default=None,
    help="Customer email for pre-fill (optional).",
)
@click.option(
    "--billing",
    type=click.Choice(["monthly", "annual"], case_sensitive=False),
    default="annual",
    help="Billing period (default: annual).",
)
@click.option(
    "--no-browser",
    is_flag=True,
    default=False,
    help="Skip opening the browser.",
)
def checkout(tier: str, email: str | None, billing: str, no_browser: bool) -> None:
    """Open the Stripe checkout page for a specific plan.

    Maps the tier to a PitchToShip plan (team -> starter, business -> studio,
    enterprise -> portfolio) and generates a checkout URL via the billing API.
    """
    from cutctx.billing import get_checkout_url, map_tier_to_plan

    # Map tier to plan
    plan = map_tier_to_plan(tier)

    # Get checkout URL from pitchtoship
    checkout_url = get_checkout_url(plan, email=email, billing=billing)

    click.echo(f"Checkout URL: {checkout_url}")

    if not no_browser:
        try:
            webbrowser.open(checkout_url)
            click.echo("Opened in browser.")
        except Exception as e:
            click.echo(f"Could not open browser: {e}", err=True)
            click.echo("Visit the URL above manually.")
    else:
        click.echo("Visit the URL above to complete your purchase.")


@billing.command()
@click.option(
    "--email",
    required=True,
    help="Customer email address.",
)
@click.option(
    "--no-browser",
    is_flag=True,
    default=False,
    help="Skip opening the browser.",
)
def portal(email: str, no_browser: bool) -> None:
    """Open the Stripe billing portal for a customer.

    Allows customers to manage their subscriptions, payment methods,
    invoices, and billing information.

    \b
    Examples:
        cutctx billing portal --email user@example.com
    """
    from cutctx.billing import get_portal_url

    # Get portal URL from pitchtoship
    portal_url = get_portal_url(email)

    click.echo(f"Billing portal URL: {portal_url}")

    if not no_browser:
        try:
            webbrowser.open(portal_url)
            click.echo("Opened in browser.")
        except Exception as e:
            click.echo(f"Could not open browser: {e}", err=True)
            click.echo("Visit the URL above manually.")
    else:
        click.echo("Visit the URL above to manage your billing account.")
