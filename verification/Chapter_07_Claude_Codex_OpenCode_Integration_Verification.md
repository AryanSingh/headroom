# Chapter 7 -- Claude, Codex & OpenCode Integration Verification

## Objective

Verify that every supported AI harness integrates correctly with the
product and delivers consistent, reliable behaviour across real-world
workflows. This chapter focuses on end-to-end execution rather than
isolated API calls.

## Supported Integrations

Audit every configured integration, including:

-   Claude CLI
-   Claude Desktop (where supported)
-   Codex CLI
-   Codex Desktop (where supported)
-   OpenCode CLI
-   OpenCode Desktop (where supported)
-   Native provider adapters
-   Enterprise provider configurations

## Integration Inventory

Create an inventory before testing.

  -------------------------------------------------------------------------
  Integration   Provider   Models   Auth   Enterprise   Tested   Evidence
  ------------- ---------- -------- ------ ------------ -------- ----------

  -------------------------------------------------------------------------

## Authentication & Session Management

Verify:

-   First-time authentication
-   Token refresh
-   Expired credentials
-   Revoked credentials
-   Multiple accounts
-   Session persistence
-   Logout/login
-   Enterprise authentication

## Provider Discovery

Confirm:

-   Providers are detected correctly
-   Supported models are listed
-   Unsupported models fail gracefully
-   Capabilities (streaming, tools, structured output) are identified
    accurately

## Model Selection

Verify:

-   Manual model selection
-   Default model selection
-   Role-based assignments
-   Provider-specific models
-   Enterprise-only models
-   Invalid model handling

## Real Workflow Scenarios

Execute realistic workflows, such as:

1.  Repository analysis
2.  Multi-file implementation
3.  Test generation
4.  Test execution
5.  Bug diagnosis
6.  Refactoring
7.  Documentation generation
8.  Code review
9.  Long-context reasoning
10. Resume interrupted work

Record the exact model, provider, routing decision, and outcome.

## Tool Calling

Verify:

-   Tool discovery
-   Tool permissions
-   Tool invocation
-   Tool failures
-   Timeouts
-   Cancellation
-   Retry behaviour
-   Structured tool outputs

## Streaming

Validate:

-   Token streaming
-   Partial responses
-   Cancellation
-   Network interruption
-   Resume behaviour
-   Output ordering

## Routing Verification

Confirm that configured routing rules are enforced.

Verify:

-   Explicit routing
-   Automatic routing
-   Worker roles
-   Cost-aware routing
-   Context-aware routing
-   Provider fallback
-   Failure recovery

Do not rely solely on logs---confirm using actual execution.

## Cross-Harness Consistency

Run equivalent tasks across Claude, Codex and OpenCode.

Compare:

-   Functional correctness
-   Routing decisions
-   Tool usage
-   Error handling
-   Session persistence
-   Output quality
-   Recovery behaviour

Document intentional differences separately from defects.

## Enterprise Verification

Using the installed enterprise licence verify:

-   Enterprise providers
-   Enterprise-only models
-   Gated workflows
-   Policy enforcement
-   Licensing persistence

## Failure Testing

Exercise:

-   Provider unavailable
-   Invalid credentials
-   Missing models
-   Rate limiting
-   Timeouts
-   Partial failures
-   Tool failures
-   Corrupted configuration

Verify graceful recovery.

## Performance

Measure:

-   Session startup
-   Provider latency
-   Streaming responsiveness
-   Tool execution latency
-   Large-context performance
-   Recovery time

## Evidence

Capture:

-   Commands
-   Configuration
-   Provider
-   Model
-   Routing decision
-   Payload
-   Expected result
-   Actual result
-   Logs
-   Screenshots (where applicable)
-   Reproduction steps

## Deliverables

1.  Integration inventory
2.  Authentication report
3.  Provider compatibility matrix
4.  Model selection report
5.  Routing verification report
6.  Cross-harness comparison
7.  Enterprise verification report
8.  Performance observations
9.  Integration defect register
10. Evidence index

## Exit Criteria

This chapter is complete only when:

-   Every supported integration has been exercised.
-   Real workflows have been executed on each harness.
-   Routing decisions have been verified with evidence.
-   Enterprise capabilities have been tested.
-   Critical and High findings include reproducible evidence.
