# Full Release Audit Remediation Design

**Date:** 2026-08-04  
**Repository:** headroom / CutCtx  
**Working branch:** `audit-fixes-2026-08-03`

## Objective

Close the complete backlog from `AUDIT_INDEPENDENT_2026-08-03.md`. The work covers recorded defects and areas where the audit produced no execution evidence. The final report must distinguish a verified fix from a test limitation or an external blocker.

The existing remediation branch contains seven commits for the audit findings. The working tree also contains uncommitted changes from Claude's audit session. The implementation must preserve and reconcile that work.

## Scope

The closeout includes:

- C1 through C7 and H1 through H19;
- every Medium/Low item in section 4 of the audit;
- every unverified area in section 8;
- the onboarding, error handling, dashboard, desktop, and commercial observations in section 9 where the audit identifies a product defect or missing evidence;
- release evidence for Python, Rust, dashboard, SDK, extension, packaging, and deployment surfaces.

Competitive review and UX assessment produce evidence and remediation tasks. They do not justify unrelated product redesign.

## Principles

### Evidence before edits

The scheduler first reconstructs a canonical issue matrix. Each row records the original claim, relevant commit, current code path, decisive test, and status. A correct behavior needs evidence, not a code change.

### Test-driven fixes

Each confirmed defect follows this sequence:

1. Add a focused regression test against real behavior.
2. Run it and confirm that it fails for the audit finding.
3. Implement the smallest production change that makes it pass.
4. Run adjacent suites and refactor while they stay green.

The Deepwork ledger records RED and GREEN commands. Production behavior changes without a witnessed RED result do not qualify as remediation under this design.

### Isolation

Tests use temporary home directories, databases, ports, credentials, provider-capture servers, and containers. They must not target the operator's existing `~/.cutctx` data, tenant records, audit databases, or provider configuration.

Live-provider canaries are reserved for claims that a local capture server cannot establish. They use task-configured credentials and must not print or persist secrets.

### Honest closure

Each audit row ends in one of four states:

- **Verified:** execution evidence establishes the required behavior.
- **Fixed:** a witnessed failing test now passes, with adjacent regression evidence.
- **Unsupported by design:** the product rejects the operation with documented behavior and tests.
- **Blocked:** an external dependency prevents a decision, and the report names the missing condition.

An unexecuted scenario remains open.

## Workstream Architecture

### Phase 0: Audit reconstruction and baseline

Build the canonical matrix from:

- `AUDIT_INDEPENDENT_2026-08-03.md`;
- `audit/independent-2026-08-03/` evidence;
- commits from `4a37ad9f` through `88093e7a`;
- the current working-tree diff;
- existing tests and release scripts.

The baseline must load Python source instead of stale compiled EE overlays. It must identify the item Claude counted as the remaining entry after reporting 18 of 19 fixes verified.

Deliverables:

- issue matrix with exact verification commands;
- environment and fixture plan;
- list of confirmed release blockers;
- mapping from each blocker to one bounded implementation lane.

### Phase 1: Release-blocking correctness and security

Re-test all Critical and High remediations. Address regressions and unresolved findings, including:

- single-shot context preservation;
- cost-routing enforcement, spend calculation, and model context limits;
- credential override-file lifecycle and secret handling;
- audit integrity, retention, authentication status codes, and configuration parsing;
- CLI failure semantics and first-run installation behavior.

The phase closes only after focused suites, adjacent suites, static checks, and independent review pass.

### Phase 2: Cross-surface governance

Verify the same effective state and authorization across API, CLI, dashboard, and desktop for:

- policies and denied models;
- RBAC and tenant scope;
- memory and review state;
- orchestration configuration;
- entitlement denial;
- spend caps and ledger totals;
- metrics and feature flags.

Tests must exercise public boundaries. An internal unit test cannot establish cross-surface parity by itself.

### Phase 3: Providers and resilience

Cover Anthropic, OpenAI, Gemini, and Vertex handlers for input validation, firewall enforcement, timeouts, malformed upstream responses, streaming, and retry behavior.

Exercise Claude streaming, tool calls, resume, and proxy-death recovery. Run equivalent recovery scenarios for other supported agents where disposable configuration makes the test safe.

### Phase 4: Distribution surfaces

Validate:

- Python, TypeScript, Go, and Java SDKs;
- VS Code and JetBrains extensions;
- Docker images and Compose flows;
- Helm and Kubernetes manifests;
- wheel and enterprise-artifact freshness;
- install, wrap, and first-run workflows.

Deployment checks use local disposable runtimes unless the user authorizes a named remote environment.

### Phase 5: UX and commercial review

Complete browser and desktop journeys for loading, success, empty, error, and recovery states. Verify the audit's dead-control and accessibility findings against the current build before editing.

Preserve the current dashboard's layout, hierarchy, spacing, motion, and interaction model. Route changes to visual intent through a design specialist. Mechanical wiring and tests may use a bounded fixer lane.

Review buyer-facing savings, routing, and ROI claims against the reconciled accounting model. Complete a focused competitive assessment using current primary sources when those sources affect product claims.

### Phase 6: Release decision

Run the complete project-specific release evidence path:

- full Python suite and coverage, including `cutctx_ee` and safety-critical modules;
- pinned Ruff checks and formatting;
- type checks and security scans configured by the repository;
- Rust workspace tests;
- dashboard tests and production build;
- SDK and extension test/build matrices;
- packaging and enterprise freshness checks;
- Docker, Helm, and Kubernetes smoke tests;
- provider and agent canaries that remain necessary after local verification.

The final report links every claim to command output or preserved evidence. The release verdict names any remaining external blockers.

## Delegation Model

The root agent acts as scheduler, evidence reconciler, and user-facing coordinator. Terra agents own bounded lanes with non-overlapping files or verification responsibility.

An oracle lane reviews:

- the implementation plan before execution;
- the result of each phase;
- the final evidence matrix and release verdict.

Implementation lanes must receive the relevant audit evidence, source files, test targets, ownership boundary, and requirement to preserve concurrent work. The scheduler does not advance while a relevant lane remains active or its output remains unreconciled.

The collaboration service must provide a Terra or Luna subagent before production implementation starts. The service rejected initial dispatch attempts during design; the Deepwork ledger records that blocker.

## Existing Working Tree

The scheduler treats current uncommitted files as pre-existing work. Before assigning a lane, the scheduler records overlapping paths and either assigns ownership to the existing change or selects a non-overlapping task.

Generated dashboard assets require source-to-bundle provenance. A production build may regenerate hashes, but the implementation must verify that `cutctx/dashboard/index.html` references the new assets and that package tests load them.

## Phase Gates

Each phase requires:

1. reconciled research in `.slim/deepwork/release-audit-closeout.md`;
2. an oracle-reviewed phase plan;
3. recorded TDD evidence for production changes;
4. focused and adjacent validation;
5. an oracle review of the result;
6. remediation of actionable review findings.

The scheduler can then open the next phase.

## Success Criteria

The work succeeds when:

- the canonical matrix covers each audit defect and unverified area;
- confirmed defects have regression tests that failed before their fixes;
- all runnable verification paths pass in isolated environments;
- cross-surface behavior agrees for governance, memory, orchestration, entitlements, spend, and metrics;
- supported providers, SDKs, extensions, and deployment artifacts pass their evidence paths;
- the UX and competitive reviews produce resolved findings or explicit follow-ups;
- the final release report separates verified claims from external blockers;
- an independent oracle accepts the evidence and verdict.

## Out of Scope

- unrelated refactors or redesigns;
- mutation of production or personal operator data;
- remote deployment without a named environment and user authorization;
- claims about third-party services that local or live evidence did not establish.
