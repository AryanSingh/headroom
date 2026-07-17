# Compression Routing Audit Remediation

## Goal

Make the two reported compression fixes directly reproducible and correct the
audit so that its claims distinguish verified code behavior from unsupported
benchmark and competitor assertions.

## Design

The code-compressor guard will compare the generated replacement with the
exact source span it replaces. This prevents a large retained prefix from
making a short omitted suffix appear profitable. A Python regression test will
exercise that boundary.

The detector tests will use timestamped log content that also has the
`file:line:` shape. Python and Rust high-level detection must classify it as
build output, preserving the intended precedence.

The audit will identify the working-tree state, record commands actually run,
and scope routing claims to the deterministic orchestration engine versus the
proxy model router. Unsupported performance and competitor comparisons will
be removed or marked as requiring a reproducible benchmark/source.

## Acceptance Criteria

- A compressor test fails against the prior size calculation and passes only
  when replacement size is compared to the replaced source span.
- Python and Rust detector tests cover the timestamp/search collision.
- Targeted Python and Rust tests pass.
- The audit does not state that uncommitted changes are merged or present
  untraceable benchmark figures as verified evidence.
