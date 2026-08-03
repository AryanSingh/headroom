---
id: CH-03
kind: chapter
title: CLI Engineering and Audit
purpose: Build and assess command-line interfaces that are safe to automate, diagnosable, and stable for operators and agents.
audience: [CLI maintainers, platform engineers, QA engineers, agent-tool builders]
scope: Command contracts, configuration precedence, non-interactive behavior, output, exit codes, streaming, upgrades, and recovery.
applicability: Use for user-facing CLIs, internal operator tools, and agent-facing commands.
owners: [CLI owner, platform owner]
inputs: [command inventory, help output, configuration reference, automated test fixture]
outputs: [CLI contract matrix, automation evidence, findings, release gate]
dependencies: [NIST-SSDF-1.1]
standards: [NIST-SSDF-1.1]
---

# CLI Engineering and Audit

## Purpose, audience, scope, and applicability

A CLI is an API with a terminal transport. Its flags, stdin/stdout/stderr,
environment behavior, exit codes, and files form a compatibility contract for
humans, CI, scripts, and agents. This chapter covers the operational contract,
not terminal aesthetics alone. Apply it to every command that mutates state,
reads credentials, controls a service, or participates in an automated workflow.

## Concepts and engineering principles

Keep machine output separate from human diagnostics. Stable JSON belongs on
stdout when requested; warnings and remediation belong on stderr. A command
should be non-interactive by default in automation and should fail rather than
silently prompt or select an environment. Configuration precedence is a public
contract: explicit flags override environment, environment overrides a named
profile, and profiles override defaults. Document any intentional exception.

## Roles and accountability

The CLI owner owns syntax and semantic compatibility. The platform owner owns
configuration, credential, and update behavior. The release owner approves
breaking changes and migration messaging. Test owners maintain the matrix across
interactive and non-interactive paths. Support owns known-error guidance and
escalation routing.

## Prerequisites and required inputs

Collect command help, version output, exit-code documentation, configuration
schema, profile precedence, auth behavior, filesystem locations, supported OS
matrix, telemetry policy, upgrade path, and representative scripts using the
CLI. Use a temporary home directory and fixture endpoint for every test that
would otherwise access a real account or configuration.

## Standard operating procedure

1. Inventory verbs, global flags, output formats, aliases, hidden compatibility
   flags, exit codes, and state-mutating commands.
2. Test `--help`, `--version`, invalid arguments, missing required inputs, and
   invalid configuration. Record stdout, stderr, and numeric exit status.
3. Test non-interactive invocation with an empty temporary home. Verify it never
   prompts, opens a browser, or chooses an environment without explicit input.
4. Prove configuration precedence one layer at a time and capture the effective
   configuration in a redacted diagnostic command.
5. Test JSON output as a schema: parse it, reject mixed prose, and version any
   breaking field change.
6. Simulate interruption, partial write, expired credentials, and retry. Verify
   cleanup, idempotency, and recovery instructions.
7. Run upgrade and downgrade compatibility checks for persisted state and old
   automation scripts.

## Worked example

The [Atlas Deploy CLI fixture](../examples/cli-contract/README.md) contains a
small executable `atlasctl` shell command. It proves deterministic profile
precedence, JSON output, an actionable missing-token error, and a nonzero exit
status without network access.

## Automation examples

```shell
temp_home=$(mktemp -d)
HOME="$temp_home" ./atlasctl deploy status --format json
status=$?
test "$status" -eq 0
rm -rf "$temp_home"
```

Use a test harness to assert output and status separately. Do not assert only
that the command printed a familiar phrase: a command may print success and
still exit nonzero, or emit non-JSON diagnostics into a machine stream.

## Audit prompts

Use the linked [Opus](../prompts/opus/ch03-cli-contract.md),
[Sonnet](../prompts/sonnet/ch03-cli-reproduction.md), and
[Haiku](../prompts/haiku/ch03-cli-inventory.md) prompts for contract synthesis,
focused failure review, and mechanical command normalization.

## Workflow checklist

Run [CL-CLI-01](../checklists/cli-engineering.md) before release. It requires
evidence for non-interactive behavior, output format, precedence, and recovery.

## Evidence requirements and retention guidance

Retain the command matrix, fixture scripts, captured stdout/stderr, exit codes,
environment values with secrets removed, version, OS, and source revision. Keep
one representative failure transcript for each documented remediation path.

## Example findings with severity and remediation

**Important — CLI-ATLAS-01.** `atlasctl deploy apply` entered an interactive
confirmation prompt when stdin was not a TTY, causing CI to hang. Remediation:
reject non-interactive apply unless `--yes` is explicitly supplied, add a
timeout-based regression test, and document the intentional safety behavior.

## KPIs and domain scorecard

The [CLI KPI catalog](../scorecards/cli-kpis.md) tracks non-interactive success,
contract-test coverage, ambiguous exit-code rate, and configuration-drift rate.
No average can offset a state-mutating command that can hang unattended.

## Common failure patterns and diagnostic guidance

- Human prose leaks into JSON output. Use a dedicated serializer and stderr for diagnostics.
- A profile silently selects production. Require an explicit profile or confirmed default.
- A retry repeats a mutation. Add idempotency keys and a recoverable status query.
- Help lists flags that the parser ignores. Test help text against the real command parser.

## Exit criteria

Exit when every supported command has documented input/output/error behavior,
automation paths are non-interactive, configuration precedence is tested,
state-mutating operations are recoverable, and blocking CLI findings are closed
or accepted through an expiring exception.

## Related runbooks, controls, examples, and templates

Use the verification-plan, finding, and release-decision templates. The CLI
contract fixture supplies a baseline for later API, agent, and release chapters.
