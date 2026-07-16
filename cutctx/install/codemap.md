# cutctx/install/

## Responsibility
Plans, executes, verifies, and supervises CutCtx installation across providers.

## Design
Typed desired state, provider adapters, path resolution, supervisors, and health checks form a staged installer. `binary_archive.py` verifies pinned SHA-256 digests, rejects unsafe archive members, and atomically installs third-party executables.

## Flow
The planner detects host/provider, resolves paths, executes actions, persists state, starts supervisors, and validates health.

## Integration
Consumed by setup/install CLI and provider installers; touches configuration, binaries, services, and proxy health.
