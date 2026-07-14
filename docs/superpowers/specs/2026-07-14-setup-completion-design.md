# Truthful Setup Completion Design

## Problem

`cutctx setup` attempts to detect agents, register MCP integrations, start a
local proxy, and verify its health. Its current summary always presents
“Setup Complete!”, even if the requested proxy does not start. That makes a
partial first-run result look successful and leaves both people and automation
without a reliable completion signal.

## Goal

Make `cutctx setup` an honest, scriptable onboarding entry point: it reports
success only when the requested proxy end state is healthy, gives an exact
recovery path when it is not, and returns a non-zero exit status for an
unsuccessful requested startup.

## Scope

### Included

- Derive a final setup outcome from the requested startup mode and final proxy
  health check.
- Render distinct success and attention-required summaries.
- Show a focused recovery command for failed startup and a troubleshooting
  documentation path.
- Exit non-zero when `--start` was requested and the proxy is not healthy.
- Preserve a successful exit for deliberate `--no-start` usage.
- Cover healthy, already-running, failed-start, and deliberate no-start paths
  with CLI tests.
- Make the README’s primary agent onboarding path use `cutctx setup`.

### Excluded

- Interactive prompts, new configuration formats, or changes to how proxy
  processes are launched.
- Expanding agent or MCP registration support.
- Telemetry, hosted billing, legal/compliance work, and dashboard UI changes.

## User experience

1. A new agent user installs Cutctx and runs `cutctx setup` from the README.
2. The command runs its existing checks and attempts the selected default
   startup path.
3. If the proxy responds to `/livez`, the command prints a clear successful
   completion summary and exits `0`.
4. If it does not respond after a requested startup, the command prints
   “Setup needs attention”, tells the user to run `cutctx proxy --port <port>`
   and links them to the troubleshooting documentation, then exits `1`.
5. If the user supplied `--no-start`, the command describes that startup was
   intentionally skipped and exits `0`; this remains useful for provisioning
   workflows.

## Implementation boundaries

- `cutctx/cli/setup.py` remains responsible for setup orchestration and final
  output; do not move proxy lifecycle behavior into another command.
- Tests should mock installation, detection, registration, startup, and health
  boundaries. They must not launch a real proxy.
- README changes should present `cutctx setup` before the advanced manual
  alternatives, while retaining `wrap`, `proxy`, and global routing examples.

## Error handling

- A failed proxy startup is not masked by a positive completion heading.
- A proxy that starts but fails the final health check receives the same
  attention-required result.
- Existing “already running” behavior remains successful only when the final
  health check is healthy.

## Verification

- Focused Click CLI tests prove all final-state/exit-code combinations.
- Existing top-level CLI help tests continue to pass.
- README review confirms `cutctx setup` is the first agent-oriented action and
  manual deployment modes remain documented.
