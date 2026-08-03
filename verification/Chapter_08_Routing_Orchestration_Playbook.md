# Chapter 8 -- Routing & Orchestration Playbook

## Objective

Verify that routing and orchestration consistently select the correct
provider, model, worker, and execution strategy based on configuration,
policy, context, and runtime conditions. Confirm actual execution
matches configured intent.

## Scope

Audit:

-   Model routing
-   Provider routing
-   Worker orchestration
-   Role-based model assignment
-   Cost-aware routing
-   Context-aware routing
-   Capability-aware routing
-   Fallback chains
-   Retry strategies
-   Timeouts
-   Load balancing (if applicable)
-   Context compression
-   Policy enforcement
-   Session continuity

## Architecture Inventory

Document:

-   Orchestrator components
-   Worker types
-   Routing rules
-   Provider adapters
-   Decision points
-   Policy engines
-   Configuration sources
-   Runtime overrides

Create:

| Decision Point \| Inputs \| Expected Decision \| Evidence \|

## Configuration Verification

Verify:

-   Default routing
-   User overrides
-   Project overrides
-   Environment overrides
-   Enterprise policy overrides
-   Invalid configurations
-   Missing configurations

Confirm precedence rules are deterministic.

## Model Assignment

Test:

-   Explicit model selection
-   Automatic model selection
-   Role-to-model mapping
-   Provider-specific models
-   Enterprise-only models
-   Unsupported models

Verify the configured model is the model that actually executes the
request.

## Worker Orchestration

Verify:

-   Task decomposition
-   Worker assignment
-   Sequential execution
-   Parallel execution
-   Dependency ordering
-   Failure isolation
-   Result aggregation
-   Cancellation
-   Resume after interruption

## Routing Scenarios

Execute realistic scenarios:

1.  Simple chat request
2.  Large-context analysis
3.  Multi-file implementation
4.  Test generation
5.  Security review
6.  Documentation generation
7.  Provider outage
8.  Rate limiting
9.  Timeout recovery
10. Enterprise policy enforcement

Record the routing decision for each scenario.

## Fallback & Recovery

Verify:

-   Primary provider failure
-   Secondary provider selection
-   Retry limits
-   Exponential backoff (if applicable)
-   User-visible errors
-   Recovery after provider restoration

Ensure fallback is observable and deterministic.

## Cost & Performance Policies

Verify:

-   Low-cost routing
-   High-quality routing
-   Token optimization
-   Context compression
-   Large-context handling
-   Latency-aware decisions

Confirm policies are enforced rather than merely configured.

## Cross-Harness Consistency

Compare routing behavior across:

-   Dashboard
-   CLI
-   Desktop
-   Claude
-   Codex
-   OpenCode

Equivalent requests should follow equivalent routing policies unless
explicitly configured otherwise.

## Observability

Confirm routing decisions are diagnosable through:

-   Logs
-   Metrics
-   Traces
-   Decision metadata
-   Correlation IDs

Do not expose secrets in telemetry.

## Failure Testing

Exercise:

-   Invalid provider
-   Invalid model
-   Missing credentials
-   Circular routing
-   Worker crash
-   Partial worker failure
-   Orchestrator restart
-   Network interruption
-   Configuration corruption

Verify graceful degradation.

## Performance

Measure:

-   Routing latency
-   Worker startup
-   Scheduling overhead
-   Parallel execution gains
-   Compression overhead
-   Recovery time

## Evidence

Capture:

-   Request
-   Configuration
-   Routing inputs
-   Chosen provider
-   Chosen model
-   Worker assignment
-   Logs
-   Metrics
-   Expected result
-   Actual result
-   Reproduction steps

## Deliverables

1.  Routing architecture map
2.  Decision matrix
3.  Worker orchestration report
4.  Policy verification report
5.  Fallback verification report
6.  Cross-harness consistency report
7.  Performance observations
8.  Routing defect register
9.  Evidence index

## Exit Criteria

Routing and orchestration verification is complete only when:

-   Every routing policy has been exercised.
-   Worker orchestration has been validated with real workflows.
-   Fallback behavior has been verified.
-   Cross-surface consistency has been confirmed.
-   Critical and High findings are supported by reproducible evidence.
