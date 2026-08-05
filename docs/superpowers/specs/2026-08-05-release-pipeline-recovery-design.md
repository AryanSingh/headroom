# Release Pipeline Recovery Design

**Date:** 2026-08-05

**Status:** Approved for implementation

## Goal

Restore a release path in which repository checks pass for the same commit, the authenticated staging gate runs only after deterministic evidence passes, and publication workflows inspect the artifacts they ship.

## Current failures

The release candidate at `a04f103b` exposes four failure classes:

1. CI jobs lack dependencies or install the wrong package shape. Graphiti jobs omit `pytest-asyncio`; native wrapper jobs omit runtime dependencies; installed-wheel test jobs exclude the EE workspace while running EE entitlement contracts.
2. Product and test contracts disagree. Enterprise routes return `200` under builder-tier tests that require `403`; the committed OpenAPI document differs from the runtime route set; dashboard fixtures use ambiguous selectors or stale expectations.
3. One Rust concurrency test fails because an expired read can remove a value refreshed by another task.
4. Publication configuration is incomplete. Supply-chain signing scans checked-in reports instead of release assets, and PyPI has no trusted-publisher record matching the workflow identity.

## Repair boundaries

### Phase 1: CI environment and deterministic fixture repair

Add each job's direct test dependencies to its installation step. Keep dependency changes local to the jobs that consume them. Do not weaken assertions, mark release gates optional, or add failure allowances.

Update dashboard tests to use semantic roles or scoped locators. Keep the rendered UI unchanged unless the failing evidence proves a product defect. Update a screenshot only after inspecting the new image and confirming that source changes intentionally altered the approved surface.

### Phase 2: Entitlement and package-boundary repair

Run entitlement tests against the package topology they claim to validate:

- OSS-only installed-wheel checks must verify that commercial modules stay absent and commercial routes fail closed.
- Workspace tests that include `cutctx_ee` must verify tier and feature enforcement through the commercial implementations.

Fix the shared entitlement gate or route registration boundary if a builder license reaches an enterprise implementation. Do not make tests accept `200` for protected routes. Regenerate `artifacts/openapi.json` only after the route topology and entitlement behavior pass focused tests.

### Phase 3: Type and concurrency repair

Resolve each new mypy error at its source with explicit types, input normalization, or initialized attributes. Preserve the ratchet baseline and do not add new suppressions unless a third-party type defect has no local typed boundary.

For the Rust cache, bind expiration removal to the value or generation observed by the reader. A stale reader must not remove a concurrent refresh. The existing failing race test remains the regression test and must pass repeatedly.

### Phase 4: Release workflow repair

Change supply-chain signing to obtain assets from the GitHub Release identified by the event or manual tag input. Download into a dedicated directory that does not overlap the repository's tracked `artifacts/` directory. Fail when the release contains no downloadable assets. Scan and sign only those downloaded files.

Remove the whole-repository forbidden-path scan from the release signing job. The repository already has separate secret-pattern and hygiene checks; release signing must answer whether shipped artifacts contain secrets, development paths, or source leakage.

Keep PyPI publication on trusted publishing. The repository workflow must declare the expected `pypi` environment and OIDC permissions. The PyPI project owner must create or update the external publisher record with these claims:

- Owner: `AryanSingh`
- Repository: `headroom`
- Workflow: `release.yml`
- Environment: `pypi`

## Verification path

Each repair starts with a focused test that reproduces the CI failure. Configuration-only workflow changes use static workflow contract tests that fail against the current YAML before the workflow changes.

The local release gate consists of:

1. Ruff 0.9.4 check and format validation.
2. Mypy ratchet with a cleared cache.
3. Focused entitlement, installed-wheel, OpenAPI, Graphiti, native installer, and dashboard tests.
4. Full dashboard Chromium E2E and inspected screenshot evidence.
5. Rust workspace tests, including repeated execution of the cache race regression.
6. Python release-relevant tests and package build/leak checks.
7. Workflow YAML validation and release-workflow contract tests.

After the local gate passes, push one commit series and evaluate GitHub Actions for the exact head SHA. Run the authenticated staging blocker only after its fixture-evidence dependency succeeds. Do not create or promote another release until CI, Rust, Product Release Evidence, packaging, and signing are green.

## Rollback and safety

The work changes tests, runtime authorization, cache concurrency, and release automation. Keep commits separated by subsystem so a reviewer can revert one repair without undoing unrelated fixes. Do not delete the existing `v0.31.0` release or overwrite published package files. PyPI and other registries remain external systems; repository changes cannot substitute for their account-level publisher configuration.

## Completion criteria

- Enterprise routes fail closed for licenses without the required entitlement.
- OSS-only and EE-inclusive test environments exercise their intended package boundaries.
- Dashboard fixture and visual suites pass without broad selector relaxations.
- Graphiti and native wrapper jobs install all direct test dependencies.
- The mypy ratchet reports no new errors.
- The Rust stale-reader race passes repeatedly.
- OpenAPI generation produces no committed diff after verification.
- Supply-chain signing downloads, scans, signs, and verifies real release assets.
- GitHub Actions pass for one exact candidate SHA.
- The authenticated staging evidence job runs and succeeds before promotion.
