# cutctx/cli/

## Responsibility
Defines the `cutctx` command-line application and commands for setup, proxying, evaluation, memory, policy, billing, reporting, and provider workflows.

## Design
A central command registry dispatches focused command modules; shared parser/formatting utilities keep input validation and output consistent. Commands remain thin coordinators over service modules.

## Flow
Entrypoints parse global options, dispatch a subcommand, load configuration/state, invoke the relevant service, format results, and return process exit codes. Savings and forecast commands reject unavailable model prices instead of presenting invented cost estimates.

## Integration
Integrates nearly every package subsystem plus provider CLIs, local files, proxy endpoints, and optional enterprise APIs; `_utils` supplies shared CLI helpers.
