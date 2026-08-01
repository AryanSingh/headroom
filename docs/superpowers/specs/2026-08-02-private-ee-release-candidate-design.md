# Private EE Release-Candidate Design

**Date:** 2026-08-02  
**Target:** Broad private EE distribution through a validated release candidate

## Objective

Publish only an immutable, compiled `cutctx-ee` wheel that has been built in a
clean CI environment, contains a signed integrity manifest for every native
module, installs successfully in a fresh environment, and passes the
licensing/billing smoke contracts before it is eligible for private-index
publication.

## Scope

- The compiled EE wheel is the release artifact; source-package builds are not
  publishable.
- The integrity manifest is generated from the final compiled modules before
  wheel creation and is included in that wheel.
- Release validation runs against the wheel after installation into a fresh
  environment, rather than against the checkout that produced it.
- The release workflow records artifact hashes and validation results as a
  reviewable evidence bundle.
- Publication remains a separate, explicit workflow step after validation.

## Non-goals

- Changing private-index credentials or publishing a release in this work.
- Replacing the existing commercial licensing model or Stripe integration.
- Claiming legal, support, alert-routing, or customer-email sign-off from code
  evidence alone.

## Architecture

```text
clean checkout
  -> compile native EE modules
  -> generate signed manifest from final modules
  -> package immutable wheel
  -> inspect wheel contents and hashes
  -> install wheel in fresh environment
  -> run EE license + webhook smoke tests
  -> emit release-evidence bundle
  -> manual approval / private-index publication
```

The workflow must fail closed when the signing secret is unavailable, manifest
generation fails, the wheel contains Python EE source, a manifest entry does
not match a bundled native module, or the installed-wheel smoke tests fail.

## Components

### Compiled build

`scripts/compile_ee.py` compiles EE modules, writes the manifest into the
temporary package root, then builds the wheel. Manifest creation precedes wheel
creation so the wheel cannot omit it accidentally.

### Artifact validation

A release gate inspects the wheel without importing source from the checkout.
It verifies:

- no `cutctx_ee/**/*.py` source payloads;
- `MANIFEST.sha256.json` is present;
- every bundled `.so` / `.pyd` has a manifest entry and matching SHA-256;
- the manifest signature validates with the release signing secret.

### Installed-wheel smoke test

The wheel is installed into an isolated virtual environment with the OSS
dependency. Tests run from a location outside the repository so import
resolution cannot fall back to the checkout. The smoke suite covers EE import,
license database initialization, idempotent checkout fulfillment, and webhook
replay protection.

### Evidence bundle

The workflow writes JSON and Markdown evidence containing the git SHA, version,
wheel SHA-256, manifest SHA-256, validation timestamps, and test command
outcomes. It is uploaded with the wheel and becomes the promotion record.

## Failure handling

- Build/manifest validation failures block artifact upload and publication.
- Smoke-test failures preserve the candidate artifact and logs for diagnosis;
  they do not retry with a rebuilt wheel.
- A successful candidate may be promoted only as the exact wheel whose hash is
  recorded in the evidence bundle.

## Verification strategy

1. Unit tests enforce manifest-before-wheel ordering and release-workflow
   configuration.
2. A hermetic artifact-validation test uses a fixture wheel with a signed
   manifest and proves that a changed module or missing manifest fails.
3. CI runs the complete release-candidate workflow in dry-run mode.
4. Final release sign-off uses the emitted evidence bundle, not a rebuild.
