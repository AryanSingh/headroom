# cutctx/rtk/

## Responsibility
Installs and manages the Rust Token Killer command wrapper.

## Design
A focused installer handles platform detection, checksum-pinned binary acquisition, safe atomic executable placement, and version checks idempotently.

## Flow
Setup resolves the artifact, installs it into an executable path, verifies the command, and reports status.

## Integration
Invoked by setup/install and provider onboarding; integrates with release artifacts and host PATH.
