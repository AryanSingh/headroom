"""Main CLI entry point for Cutctx."""

from __future__ import annotations

import sys
from importlib import import_module

import click

CLI_CONTEXT_SETTINGS = {"help_option_names": ["--help", "-?"]}

# Keep `python -m cutctx.cli.main` and `import cutctx.cli.main` on one module
# instance so command modules decorate the active `main` object.
sys.modules.setdefault("cutctx.cli.main", sys.modules[__name__])

_SIDE_EFFECT_COMMAND_MODULES: dict[str, str] = {
    "agent-savings": "agent_savings",
    "benchmark": "evals",
    "billing": "billing",
    "capabilities": "capabilities",
    "capture": "capture",
    "evals": "evals",
    "evidence": "evidence",
    "global": "global_routing",
    "verify": "evals",
    "init": "init",
    "install": "install",
    "integrations": "integrations",
    "intercept": "intercept",
    "learn": "learn",
    "license": "license",
    "mcp": "mcp",
    "memory": "memory",
    "perf": "perf",
    "policies": "policies",
    "profile": "profile",
    "proxy": "proxy",
    "report": "report",
    "routing": "routing",
    "savings": "savings",
    "stack-graph": "stack_graph",
    "tools": "tools",
    "wrap": "wrap",
    "unwrap": "wrap",
}

_MANUAL_COMMAND_MODULES: dict[str, tuple[str, str]] = {
    "audit": ("audit", "audit"),
    "bench": ("bench", "bench"),
    "config-check": ("config_check", "config_check"),
    "config": ("config", "config"),
    "orgs": ("orgs", "orgs"),
    "rbac": ("rbac", "rbac"),
    "setup": ("setup", "setup"),
    "sso-test": ("sso_test", "sso_test"),
}

_ALL_COMMANDS = tuple(sorted(set(_SIDE_EFFECT_COMMAND_MODULES) | set(_MANUAL_COMMAND_MODULES)))
_LOAD_FAILURES: dict[str, str] = {}

# Top-level help should lead with the journey a new operator is on, rather
# than exposing the implementation's alphabetical module layout. Commands
# remain addressable exactly as before; this only changes help presentation.
_COMMAND_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Getting Started", ("setup", "init", "install", "integrations", "wrap")),
    (
        "Daily Use",
        ("proxy", "memory", "capture", "learn", "report", "savings", "perf"),
    ),
    (
        "Optimize and Evaluate",
        ("evidence", "benchmark", "bench", "evals", "verify", "routing", "tools", "stack-graph"),
    ),
    (
        "Administration",
        (
            "config",
            "config-check",
            "global",
            "policies",
            "profile",
            "agent-savings",
            "license",
            "billing",
            "orgs",
            "rbac",
            "audit",
            "mcp",
            "intercept",
            "sso-test",
        ),
    ),
)


def get_version() -> str:
    """Get the current package version."""
    try:
        from cutctx._version import __version__

        return __version__
    except ImportError:
        return "unknown"


def _format_load_error(exc: Exception) -> str:
    if isinstance(exc, ModuleNotFoundError) and exc.name:
        return f"missing optional dependency: {exc.name}"
    return str(exc)


def _make_unavailable_command(name: str, reason: str) -> click.Command:
    @click.command(name=name, context_settings=CLI_CONTEXT_SETTINGS)
    def unavailable_command() -> None:
        click.echo(
            click.style(
                f"`cutctx {name}` is unavailable in this installation: {reason}",
                fg="red",
            )
        )
        raise SystemExit(1)

    unavailable_command.help = f"Unavailable in this installation ({reason})"
    return unavailable_command


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


def _ensure_command_loaded(command_name: str) -> None:
    """Import the module that registers a command on demand."""
    if command_name in main.commands or command_name in _LOAD_FAILURES:
        return

    try:
        if command_name in _SIDE_EFFECT_COMMAND_MODULES:
            import_module(f"cutctx.cli.{_SIDE_EFFECT_COMMAND_MODULES[command_name]}")
        else:
            module_name, attr_name = _MANUAL_COMMAND_MODULES[command_name]
            module = import_module(f"cutctx.cli.{module_name}")
            command = getattr(module, attr_name, None)
            if isinstance(command, click.Command):
                main.add_command(command, name=command_name)
        if command_name in main.commands:
            _apply_help_aliases(main.commands[command_name])
    except Exception as exc:  # pragma: no cover - defensive CLI fallback
        _LOAD_FAILURES[command_name] = _format_load_error(exc)


class LazyCLIGroup(click.Group):
    """Load CLI commands only when they are requested."""

    def list_commands(self, ctx: click.Context) -> list[str]:
        base_commands = set(super().list_commands(ctx))
        return sorted(base_commands | set(_ALL_COMMANDS))

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        _ensure_command_loaded(cmd_name)
        command = super().get_command(ctx, cmd_name)
        if command is not None:
            return command
        reason = _LOAD_FAILURES.get(cmd_name)
        if reason is not None:
            return _make_unavailable_command(cmd_name, reason)
        return None

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Render commands by operator phase instead of alphabetically."""

        available = set(self.list_commands(ctx))
        displayed: set[str] = set()
        for heading, names in _COMMAND_GROUPS:
            rows: list[tuple[str, str]] = []
            for name in names:
                if name not in available:
                    continue
                command = self.get_command(ctx, name)
                if command is None or command.hidden:
                    continue
                rows.append((name, command.get_short_help_str()))
                displayed.add(name)
            if rows:
                with formatter.section(heading):
                    formatter.write_dl(rows)

        # Keep newly added commands visible even if they have not yet been
        # assigned to a journey group.
        other_rows: list[tuple[str, str]] = []
        for name in sorted(available - displayed):
            command = self.get_command(ctx, name)
            if command is not None and not command.hidden:
                other_rows.append((name, command.get_short_help_str()))
        if other_rows:
            with formatter.section("Other Commands"):
                formatter.write_dl(other_rows)


@click.group(
    cls=LazyCLIGroup,
    context_settings=CLI_CONTEXT_SETTINGS,
    invoke_without_command=True,
)
@click.version_option(get_version(), "--version", "-v", prog_name="cutctx")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Cutctx - Context optimization layer for LLM applications.

    Manage memories, run the optimization proxy, and analyze metrics.

    \b
    Examples:
      cutctx setup            Unified setup with agent detection
      cutctx proxy            Start the optimization proxy
      cutctx memory list      List stored memories
      cutctx orgs list        List organizations
      cutctx audit list       List audit events
      cutctx rbac list        List role assignments
      cutctx config doctor    Validate configuration and deployment policy
      cutctx sso-test         Test SSO configuration
    """

    ctx.ensure_object(dict)
    if ctx.invoked_subcommand is None:
        click.echo(click.style("Welcome to Cutctx", bold=True))
        click.echo("Start with one of these commands:")
        click.echo("  cutctx setup          Detect and configure your AI agent")
        click.echo("  cutctx proxy          Start the local optimization proxy")
        click.echo("  cutctx config doctor  Check configuration and deployment safety")
        click.echo("  cutctx wrap claude    Launch Claude Code through Cutctx")
        click.echo()
        click.echo(ctx.get_help())


_apply_help_aliases(main)


if __name__ == "__main__":
    main()
