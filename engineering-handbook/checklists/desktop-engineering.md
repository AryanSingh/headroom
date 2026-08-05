---
id: CL-DESKTOP-01
kind: checklist
title: Desktop lifecycle checklist
chapter: CH-04
controls:
  - id: ENG-DESKTOP-001
    requirement: Supported desktop upgrades preserve readable user state or provide a tested recovery path after interruption.
    applicability: required for applications that persist local user or operational state
    procedure: Interrupt each supported schema upgrade at download, migration, and first-launch stages, then restart.
    expected_result: State resumes, restores, or presents documented recoverable action without silent loss.
    evidence: Version matrix, installer hash, local checksum, logs, and restart result.
    automation: disposable-profile upgrade/interruption suite
    owner: Desktop owner
    frequency: every schema or updater change
    failure_action: block release and repair migration/recovery behavior
    standards: [NIST-SSDF-1.1]
---

# Desktop lifecycle checklist

- [ ] Validate package identity and supported platform/version matrix.
- [ ] Exercise denied permissions, malformed IPC, offline, low-disk, and crash recovery.
- [ ] Test upgrade interruption and uninstall retention/deletion behavior.
