# Pilot Onboarding Checklist

## Before the session

- Confirm the signed pilot agreement and payment status.
- Issue the license and send it through the approved secret channel.
- Complete the environment worksheet.
- Pin the Cutctx package version or container digest.
- Confirm a backup destination and rollback owner.

## Installation

1. Install the pinned release.
2. Configure provider and Cutctx credentials through the customer's secret
   manager or local secure environment.
3. Run `cutctx config-check` and resolve each error.
4. Start the loopback proxy or customer-managed deployment.
5. Verify `/livez` and `/readyz`.
6. Configure Codex and Claude Code to use the supported proxy endpoint.
7. Run `cutctx mcp install --gateway` when Claude Desktop tool-output
   compression is part of the pilot.
8. Run `cutctx mcp status` and restart Claude Desktop or Claude Code when the
   status output requests it.

## Handoff

- Run the customer acceptance test with the customer present.
- Show the operator where health, logs, metrics, and dashboard data live.
- Review backup, restore, upgrade, rollback, and uninstall procedures.
- Confirm the support channel and response target in writing.
- Record the accepted release version, date, and customer approver.

