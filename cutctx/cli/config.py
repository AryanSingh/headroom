"""Grouped configuration commands."""

from __future__ import annotations

from cutctx.cli.config_check import config_check
from cutctx.cli.main import main


@main.group("config")
def config() -> None:
    """Inspect and validate effective Cutctx configuration."""


config.add_command(config_check, name="doctor")
