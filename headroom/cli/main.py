"""Main CLI entry point for CutCtx."""

import click

CLI_CONTEXT_SETTINGS = {"help_option_names": ["--help", "-?"]}


def get_version() -> str:
    """Get the current version."""
    try:
        from headroom._version import __version__

        return __version__
    except ImportError:
        return "unknown"


@click.group(context_settings=CLI_CONTEXT_SETTINGS)
@click.version_option(get_version(), "--version", "-v", prog_name="cutctx")
@click.pass_context
def main(ctx: click.Context) -> None:
    """CutCtx - The Context Optimization Layer for LLM Applications.

    Manage memories, run the optimization proxy, and analyze metrics.

    \b
    Examples:
        cutctx setup                Unified setup with agent detection
        cutctx proxy                Start the optimization proxy
        cutctx memory list          List stored memories
        cutctx orgs list            List organizations
        cutctx audit list           List audit events
        cutctx rbac list            List role assignments
        cutctx config-check         Validate configuration
        cutctx sso-test             Test SSO configuration
    """
    ctx.ensure_object(dict)


# Import subcommands - these register themselves with the main group
def _register_commands() -> None:
    """Register all subcommand groups."""
    from . import (
        agent_savings,  # noqa: F401
        audit,  # noqa: F401
        bench,  # noqa: F401
        capture,  # noqa: F401
        config_check,  # noqa: F401
        evals,  # noqa: F401
        init,  # noqa: F401
        install,  # noqa: F401
        learn,  # noqa: F401
        license,  # noqa: F401
        mcp,  # noqa: F401
        orgs,  # noqa: F401
        perf,  # noqa: F401
        proxy,  # noqa: F401
        rbac,  # noqa: F401
        report,  # noqa: F401
        savings,  # noqa: F401
        setup,  # noqa: F401
        sso_test,  # noqa: F401
        tools,  # noqa: F401
        wrap,  # noqa: F401
    )

    # Memory CLI requires numpy/hnswlib — optional
    try:
        from . import memory  # noqa: F401
    except ImportError:
        pass


_register_commands()


def _apply_help_aliases(command: click.Command) -> None:
    """Ensure `-?` works everywhere in the Click command tree."""
    context_settings = dict(command.context_settings or {})
    help_option_names = list(context_settings.get("help_option_names", []))
    if "--help" not in help_option_names:
        help_option_names.append("--help")
    if "-?" not in help_option_names:
        help_option_names.append("-?")
    context_settings["help_option_names"] = help_option_names
    command.context_settings = context_settings

    if isinstance(command, click.Group):
        for child in command.commands.values():
            _apply_help_aliases(child)


_apply_help_aliases(main)

if __name__ == "__main__":
    main()
