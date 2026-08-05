# Chapter 3 -- CLI Audit Playbook

## Objective

Verify that every CLI shipped with the product is reliable, consistent,
secure, and functionally equivalent to the documented behavior. Test
real workflows rather than isolated commands.

## Scope

Audit all supported command-line interfaces, including:

-   Claude CLI integration
-   Codex CLI integration
-   OpenCode CLI integration
-   Native product CLI
-   Administrative and diagnostic commands
-   Installer and bootstrap commands

## Audit Principles

-   Execute commands with real inputs whenever safe.
-   Capture stdout, stderr, exit codes, logs, and timing.
-   Verify backend state, not just terminal output.
-   Test on clean and existing workspaces.
-   Prefer end-to-end scenarios over isolated unit behavior.

## Command Inventory

Create an inventory containing:

  Command   Purpose   Required Auth   Surface   Priority   Tested
  --------- --------- --------------- --------- ---------- --------

Include:

-   Primary commands
-   Subcommands
-   Flags
-   Hidden commands
-   Experimental commands
-   Deprecated commands

## Functional Verification

For every command verify:

-   Help output
-   Required arguments
-   Optional arguments
-   Invalid arguments
-   Missing configuration
-   Authentication
-   Authorization
-   Interactive prompts
-   Non-interactive mode
-   Streaming output
-   Structured output (JSON, etc.)
-   Exit codes
-   Error messages
-   Logging
-   Cleanup

## Configuration Testing

Verify:

-   Default configuration
-   Custom configuration
-   Environment variables
-   Configuration file precedence
-   Missing configuration
-   Invalid configuration
-   Secrets handling

## Authentication

Test:

-   Fresh login
-   Existing session
-   Expired session
-   Revoked credentials
-   Invalid credentials
-   Multiple accounts
-   Enterprise entitlement

## Provider Verification

For every configured provider verify:

-   Connection
-   Authentication
-   Model discovery
-   Request execution
-   Streaming
-   Cancellation
-   Retry
-   Timeout
-   Rate limiting
-   Provider outage
-   Recovery

## Routing Verification

Verify:

-   Explicit model selection
-   Automatic routing
-   Role-based routing
-   Provider fallback
-   Cost-aware routing
-   Capability-aware routing
-   Context-size routing

Confirm the selected model actually handled the request.

## Real Workflow Scenarios

Execute realistic workflows such as:

1.  Analyze a repository
2.  Modify multiple files
3.  Generate tests
4.  Run tests
5.  Explain failures
6.  Resume interrupted session
7.  Replay previous work
8.  Switch providers
9.  Execute tool calls
10. Handle provider outage

## Failure Testing

Verify behavior during:

-   Invalid arguments
-   Missing files
-   Permission denied
-   Read-only filesystem
-   Network interruption
-   Provider unavailable
-   Timeout
-   Cancellation
-   Corrupted configuration
-   Disk full (where safe)

## Performance

Measure:

-   Startup time
-   Command latency
-   Streaming responsiveness
-   Large repository handling
-   Large prompt handling
-   Memory usage

## Regression Checklist

For every fix verify:

-   Original issue reproduced
-   Fix confirmed
-   Related commands unaffected
-   Exit codes preserved
-   Documentation still accurate

## Evidence Requirements

Record:

-   Command executed
-   Inputs
-   Configuration
-   Environment
-   Expected result
-   Actual result
-   Exit code
-   Logs
-   Screenshots (if applicable)

## Deliverables

Produce:

1.  CLI command inventory
2.  Provider compatibility matrix
3.  Authentication report
4.  Routing verification report
5.  Failure scenario report
6.  Performance observations
7.  CLI defect register
8.  Evidence index

## Exit Criteria

CLI audit is complete only when:

-   Every discovered command has been executed or explicitly justified
    as blocked.
-   High-risk workflows have been tested end-to-end.
-   Authentication, routing, provider integration, and recovery have
    been verified.
-   All Critical and High issues include reproducible evidence.
