---
id: EX-CH04-DESKTOP-UPGRADE
kind: worked-example
chapter: CH-04
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
preconditions: [clean desktop profile, version 4.2 fixture with local notes, signed version 4.3 installer]
placement: engineering-handbook/examples/desktop-upgrade
dependencies: [disposable VM or OS profile, installer, local schema checksum tool]
invocation: Install 4.2, create fixture notes, interrupt 4.3 migration, restart 4.3.
expected_output: Notes remain readable and migration journal resumes or safely restores prior schema.
failure_output: Notes are missing or local index is unreadable after restart.
interpretation: A missing/invalid journal makes upgrade interruption a data-loss risk.
remediation: Implement journaled copy/swap, retain backup until post-upgrade health check, and retest interruption.
cleanup: Destroy VM/profile and delete sanitized logs after evidence retention.
---

# Atlas Notes desktop upgrade fixture

The fixture turns power loss during a local-schema migration into a repeatable
test. Capture installer hash, old/new version, local checksum before/after,
interruption point, restart log, and the visible recovery result.
