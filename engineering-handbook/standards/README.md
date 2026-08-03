# Standards registry

`registry.yaml` is the offline authority for standards citations in the manual.
Registry version `2026.1` pins exact editions for this handbook edition. Chapter
authors cite stable source IDs in front matter and paraphrase requirements; the
manual does not reproduce third-party standards wholesale.

## Registry record contract

Every source includes a stable ID, publisher, exact title, edition or version,
publication date, official URL, immutable URL when available, retrieval date,
scope, normative or informative status, control families, copyright/paraphrase
note, and refresh policy.

Official URLs are checked separately by a network-aware release job. The normal
validator is offline: it checks record completeness, duplicate IDs, and whether
handbook references resolve to this registry.

## Refresh policy

The registry owner reviews sources annually, before a manual edition is frozen,
and when a publisher announces a revision. Updating a pinned source changes the
registry version and records the impact on controls, procedures, examples, and
claims. Existing editions continue to cite their original pins.

## NIST SSDF {#nist-ssdf}

The first edition pins NIST SP 800-218, Secure Software Development Framework
Version 1.1, for secure-development governance mappings.
