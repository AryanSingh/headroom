# Release-readiness audit — 2026-07-13

## Scope and decision

This is an evidence-based re-audit of `codex/orchestration-foundation`. It is
not a general-availability declaration: built-image, consented staging,
partner-telemetry, and live-billing evidence are still required before the
stronger commercial claims in `release-evidence-runbook.md` can be made.

## Confirmed Critical and High findings

| Priority | Finding | Resolution and evidence |
| --- | --- | --- |
| Critical | Configured upstream OpenAI credentials were not applied consistently when callers omitted `Authorization`. | Resolved in `c0a56759`; proxy/auth/OpenAPI tests pass and real Chat/Responses requests were exercised with only the configured upstream credential. |
| Critical | Generated OpenAPI could contain duplicate operation IDs and a function-scoped Pydantic model. | Resolved in `c0a56759`; `tests/test_openapi_schema.py` passes. |
| High | Project-local provider configuration was not explicitly loaded by operational CLI entry points. | Resolved in `4ac22f06`; `cutctx config-check --port 0` recognizes local OpenAI configuration and `tests/test_env.py` passes. |
| High | Public health endpoints exposed upstream configuration detail. | Resolved in `e0d63290`; public health is redacted and authenticated configuration health retains operational detail. |
| High | Stateful Kubernetes defaults allowed multiple replicas against an RWO persistent volume. | Resolved in `c7355b0e`; Helm/static manifests default to one replica and supply writable `/tmp` under a read-only root filesystem. |
| High | Dashboard search was unavailable on Overview and did not pass the query into Overview filtering. | Resolved in `06f3b12`; focused regression and full Playwright matrix pass. |
| High | Orchestration form controls lacked programmatic labels. | Resolved in `d4f71285`. |
| High | Query-aware log compression could retain a matching commit without author attribution. | Resolved in `5fccfd11`; `cutctx verify` passes with full critical-item and information recall. |

No unresolved Critical or High product defect was reproduced during this audit.

## Local verification evidence

| Surface | Command or workflow | Result |
| --- | --- | --- |
| Dashboard E2E | `cd dashboard && npm exec playwright test` | 67 passed across all audited routes and 375, 768, 1280, and 1720 pixel breakpoints. |
| Dashboard build/lint | `npm run build`; `npm run lint` | Passed. |
| Proxy/auth/configuration | Targeted OpenAPI, env, auth, provider route, and health tests | 60 passed. |
| Orchestration | API, platform, and workflow suites | 89 passed. |
| Advanced capability bundle | Graphify, Drain3, difftastic, image, compression endpoint, product capability, and dashboard-cache tests | 187 passed, 8 optional/environment skips. |
| Python CI selection | Smart Crusher/Rust parity, diff parity, relevance, CCR, acceptance, critical fixes, and quality retention | 175 passed, 4 skipped. |
| Security and identity | Deployment security, hardening/validation, SSO, and billing-contract tests | 91 passed. |
| Product quality | `cutctx verify --ci --format json` | Passed. Content router: F1 0.9447; information/critical recall 1.0; fidelity 1.0. Smart Crusher: F1/recall/fidelity 1.0. |
| Static checks | Ruff, dashboard Prettier, Cargo formatting and Clippy | Passed. |
| Release wheel | Fresh `maturin build --release` wheel validated with ZIP integrity, installed with pip, imported `cutctx._core` from an isolated environment, and exposed `cutctx --version`. | Passed after correcting a Maturin Deflate/SBOM archive corruption issue. |
| Source distribution | Fresh `maturin sdist` passed the OSS artifact guard; its PEP 639 license metadata resolved to all declared files in the tarball. | Passed after including `LICENSE-COMMERCIAL`, which Maturin declares automatically. |

The repository-wide Python suite collected 8,934 tests and began passing, but
the interactive execution channel terminated before it returned a final exit
status. It is therefore **not** recorded as passing.

## Competitive capability matrix

This deliberately separates coding harnesses from the control plane. Headroom
does not claim to replace an editor or provider-native agent loop.

| Capability | Headroom current position | Codex | Claude Code | Cursor | OpenCode | Product decision |
| --- | --- | --- | --- | --- | --- |
| Native coding UI/agent loop | Delegated to the harness. | CLI, IDE, cloud, desktop/web surfaces. | Terminal, IDE, desktop, web. | Editor/agent, cloud agents, CLI. | TUI, desktop, IDE, web. | Do not imitate the editor; retain adapters and compatible configuration. |
| Multi-provider policy routing | Verified routing receipts, shadow decisions, residency/provider/cost eligibility, recommendation-only scheduler. | Provider-native workflow. | Provider-native/third-party integrations. | Multi-model selection inside Cursor. | Any configured provider. | Differentiator: policy-aware harness-neutral routing, never hidden substitution. |
| Context/token optimization | Verified compression, cache, retrieval, quality gates, and inspector statistics. | Harness context handling. | Prompt caching and context controls. | Model-context configuration. | Harness context/configuration. | Continue evidence-led compression. |
| Safety and approvals | Durable human/verification gates, receipts/audit-chain option, role/profile constraints. | Permission modes. | Permission modes, hooks, skills. | Approval/security agents and agent review. | Permissions and policies. | Maintain explicit gates; no silent cross-harness side effects. |
| Cross-harness orchestration | Codex, Claude Code, OpenCode manifest; no hidden-session sharing. | Codex-specific handoffs. | Claude-specific continuity. | Cursor-specific cloud/IDE workflow. | OpenCode-specific agents/plugins/ACP. | Preserve artifact-based handoffs instead of claiming semantic equivalence. |
| Enterprise proof | Policy bundles, signed receipt/audit chain, encrypted development fallback, external secret-resolver protocol. | Enterprise administration/security. | Administration/enterprise configuration. | Teams/Enterprise and self-hosted cloud agents. | Enterprise configuration. | Requires live KMS/Vault, SSO/SCIM, and audit-export evidence before enterprise GA claims. |

Primary sources read on 2026-07-13:

- [OpenAI Codex documentation](https://developers.openai.com/codex/)
- [Claude Code overview](https://docs.anthropic.com/en/docs/claude-code/overview)
- [Cursor documentation](https://cursor.com/docs)
- [OpenCode documentation](https://opencode.ai/docs/)

## Remaining items

| Severity | Item | Evidence / impact | Recommended next step |
| --- | --- | --- | --- |
| Medium — release blocker | Built Docker image runtime not verified. | `docker ps` cannot reach Docker Desktop's daemon. | Start Docker Desktop; build/run from a clean environment; exercise authenticated health, `/stats`, compression, fallback, and dashboard flows. |
| Medium — release blocker | Consented staging evidence absent. | No staging origin/admin key/scenario file is configured. | Execute `release-evidence-runbook.md` and retain redacted artifacts. |
| Medium — commercial-claim blocker | Two anonymized design-partner snapshots absent. | Broad cost/performance/reliability claims require real privacy-safe data. | Obtain and validate the two snapshots in the release-evidence runbook. |
| Medium — billing integration | Tests validate contracts, not a merchant account and real Stripe Price IDs. | Live billing cannot be asserted. | Provide authorized Stripe test credentials/Price IDs and verify checkout/webhook lifecycle. |
| Low — environment hygiene | Local test environment emits requests and SciPy/NumPy compatibility warnings. | Tests are green, but release logs are noisier. | Pin the compatible release dependency set and rerun affected suites. |
| Low — wheel size trade-off | Wheel members are stored rather than Deflated. | This avoids a reproducible invalid embedded CycloneDX SBOM produced by the local Maturin 1.14 toolchain; the artifact remains valid and installable. | Re-evaluate compression when the Maturin defect is fixed, retaining the artifact-integrity guard. |

## Release verdict

**Local code readiness: conditionally verified.** The confirmed Critical and
High defects are resolved and available source, browser, CLI, and provider
gates are green. **Commercial release readiness is not yet proven** until the
medium-severity external gates above have evidence. Claims must remain limited
to verified behavior and must not assert universal harness parity or unmeasured
production savings.
