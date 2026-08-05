# Chapter 2 -- Product Discovery & Capability Mapping

## Objective

Before testing begins, establish a complete inventory of the product.
The goal of this phase is to ensure **no capability is omitted** from
later verification.

## Discovery Principles

-   Discover, don't assume.
-   Inventory before testing.
-   Record evidence for every discovered capability.
-   Classify unknown items rather than ignoring them.

## Discovery Workflow

1.  Inspect repository layout.
2.  Identify applications and services.
3.  Enumerate packages/modules.
4.  Discover APIs and endpoints.
5.  Enumerate CLI commands.
6.  Inventory desktop windows, dialogs and workflows.
7.  Crawl dashboard routes and navigation.
8.  Identify feature flags.
9.  Identify enterprise-gated functionality.
10. Enumerate integrations and providers.

## Capability Categories

Create inventories for:

-   Applications
-   Packages
-   Libraries
-   APIs
-   Background workers
-   Scheduled jobs
-   Databases
-   Queues
-   Caches
-   CLI commands
-   Desktop workflows
-   Dashboard pages
-   Configuration screens
-   Import/export flows
-   Authentication
-   Authorization
-   Licensing
-   Routing
-   Orchestration
-   Memory
-   Replay
-   Governance
-   Security
-   Notifications
-   Telemetry
-   Provider integrations
-   Feature flags

## Surface Inventory

Every capability should be mapped to one or more surfaces:

  Capability   Dashboard   CLI   Desktop   API   Enterprise   Notes
  ------------ ----------- ----- --------- ----- ------------ -------

## Dependency Mapping

For each capability identify:

-   Upstream dependencies
-   Downstream consumers
-   Configuration required
-   Permissions required
-   External providers
-   Data stores
-   Failure modes

## Risk Classification

Assign:

-   P0 -- Critical
-   P1 -- High
-   P2 -- Medium
-   P3 -- Low

Consider:

-   Security
-   User impact
-   Data integrity
-   Revenue impact
-   Operational importance
-   Release blocking potential

## Capability Matrix

Maintain a living matrix.

  Capability   Module   Priority   Test Cases   Status   Evidence
  ------------ -------- ---------- ------------ -------- ----------

Status values:

-   NOT_STARTED
-   IN_PROGRESS
-   PASSED
-   FAILED
-   BLOCKED
-   NEEDS_RETEST

## Discovery Deliverables

Produce:

1.  Product map
2.  Module inventory
3.  Surface inventory
4.  Dependency graph
5.  Capability matrix
6.  Risk-ranked execution plan
7.  Open questions list

## Common Discovery Issues

Look for:

-   Dead routes
-   Hidden features
-   Placeholder pages
-   Duplicate implementations
-   Unused configuration
-   Stale feature flags
-   Enterprise-only code paths
-   Orphaned APIs
-   CLI commands without UI
-   UI without backend support

## Exit Criteria

Do not begin detailed testing until:

-   Every discovered capability appears in the matrix.
-   Every surface has been inventoried.
-   Risk classification is complete.
-   High-risk capabilities have owners.
-   Unknown areas are explicitly documented.
