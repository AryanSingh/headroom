# Verified Audit Remediation

## Problem

The July 17 commercial audit mixes reproducible defects with conclusions that
the current repository contradicts. Acting on the report as written would put
CCR behind a paid entitlement even though the product guide promises CCR to
Builder users and the proxy enables it by default.

Independent checks found five concrete maintenance defects:

- release synchronization omits Helm and Kubernetes image metadata;
- CI path filters omit `helm/**` and `k8s/**`;
- `ContentRouter.compress()` can return more bytes than it received, although
  the higher-level `cutctx.compress()` API already rejects inflated results;
- the managed RTK installer pins `v0.28.2` while upstream's current verified
  release is `v0.43.0`;
- the audit CLI concatenates filters into query strings instead of passing
  structured HTTP parameters.

The package-version mismatch in the worktree does not itself block a tagged
release because both publishing jobs run `version-sync.py` before
`verify-versions.py`. The scripts still need deployment-manifest coverage so a
release cannot publish packages and leave Helm or Kubernetes on an older tag.

## Decisions

### Preserve feature behavior

CCR remains enabled by default. Its entitlement metadata moves to Builder so
the capability API, documentation, and runtime describe the same product.
Episodic memory remains disabled by default and retains its Business-tier
metadata. This work will not add request-path denials or change startup flags.

### Make version synchronization complete

`scripts/version-sync.py` will update the PyO3 crate, package manifests, plugin
manifests, Helm chart version, Helm app version, Helm image tag, and Kubernetes
image tag. `scripts/verify-versions.py` will parse and compare the same files.
CI will classify Helm and Kubernetes changes as code and end-to-end changes.

The checked-in deployment manifests will move from `0.30.0` to the canonical
`0.31.0` declared in `pyproject.toml`.

### Enforce non-inflation at the router boundary

After routing and reassembly, `ContentRouter.compress()` will compare UTF-8
byte lengths. When output is larger than input, it will return the original
content, mark the result as passthrough, replace inflated routing token counts
with equal before/after counts, and record an `inflation_guard` diagnostic.
Equal-size output remains valid so existing deterministic transforms keep
their behavior.

This complements the existing high-level library guard and protects direct
router consumers, including proxy handler paths and SDK-style integrations.

### Update managed RTK without rejecting system installations

The managed installer will pin RTK `v0.43.0` and use the SHA-256 digests
published on that GitHub release for all supported targets. `get_rtk_path()`
will continue preferring a system binary. A version inspection helper may
surface whether the selected binary differs from the managed pin, but it must
not reject or replace a working system installation.

### Use structured audit query parameters

Audit list, export, and stats requests will pass dictionaries through
`httpx.get(..., params=...)`. Existing option names, URLs, output, and error
handling remain unchanged.

## Tests

- Extend version-sync tests with Helm and Kubernetes fixtures.
- Extend version verification tests to prove deployment drift fails the gate.
- Add workflow assertions for `helm/**` and `k8s/**` path coverage.
- Add a direct `ContentRouter` regression using mixed prose and fenced code
  that currently expands from 8,000 to 8,198 bytes.
- Update RTK installer tests for `v0.43.0`, published checksums, and
  non-blocking system-binary selection.
- Add audit CLI tests that inspect `httpx.get` arguments and verify filter
  values cannot create extra query parameters.
- Update entitlement tests so Builder includes `ccr` and `ccr_marker`, while
  episodic memory remains unavailable below Business.

## Documentation

Add an evidence note under `audit/` that labels the original report's major
claims as confirmed, narrowed, or refuted. The note will cite commands and
source locations without changing or deleting the user-provided audit files.

## Non-goals

- Adding a paid-feature enforcement layer to provider request handlers.
- Changing CCR, episodic-memory, or compression defaults.
- Building new pricing, SLA, compliance, or observability products.
- Treating subjective competitive comparisons as release blockers.
