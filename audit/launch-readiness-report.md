# Cutctx Launch Readiness Report

**Product:** Cutctx (formerly Headroom) — context compression layer for AI agents
**Repository:** headroomlabs-ai/headroom (upstream) | AryanSingh/headroom (local fork)
**Version:** 0.30.0 (unreleased, current pyproject.toml)
**Assessment Date:** July 4, 2026
**Audience:** Founders / Engineering Lead / Product Lead

---

## Executive Summary

**Verdict: CONDITIONAL GO —OSS RELEASE NOW, COMMERCIAL HOLD**

Cutctx can ship v0.30.0 OSS today with known limitations documented. The engineering work is production-grade for an open-core project at this stage. However, going to market with paying commercial customers requires fixing at minimum:

1. **Billing infrastructure dead code** — 4 out of 6 webhook event handlers are stubs (`invoice.paid` doesn't extend licenses, `subscription.deleted` doesn't deactivate, `subscription.updated` does nothing, `_send_license_email` logs only)
2. **X-Cutctx-Role privilege escalation vector** — any cross-origin attacker can set admin role via HTTP header
3. **GitHub org+domain+HF org don't exist** — `cutctx.com` NXDOMAIN, `github.com/cutctx` 404, `huggingface.co/cutctx` 404
4. **No SAST/SCA in CI** — no Bandit, CodeQL, Trivy, or dependency vulnerability scanning

The product's engineering (compression engine, proxy, security, test suite, CI/CD) is ahead of most pre-revenue tools. The commercial layer (billing, support, onboarding, marketing infrastructure) is behind schedule.

---

## Scorecard

| Dimension | Score | Summary |
|-----------|-------|---------|
| **Product & Features** | 🟢 8/10 | Compression engine is mature, reversible, 10+ algorithms, 30+ integrations. Dashboard is functional but spare. |
| **Code Quality & Testing** | 🟢 8/10 | 7,565 tests passing, rust parity, fuzzing, property tests. Strong CI/CD with 22 workflows. |
| **Security** | 🟡 6/10 | Defense-in-depth on most surfaces, but one privilege-escalation vector (X-Cutctx-Role header), no bug bounty, no SAST in CI. |
| **Billing & Payments** | 🔴 3/10 | Happy path works. 4 of 6 webhook handlers are stubs. No email delivery. No dunning. No cancellation. No upgrade/downgrade. |
| **Documentation** | 🟡 6/10 | Excellent breadth (50+ wiki pages, 60+ docs files). Brand inconsistency (cutctx vs cutctx vs headroom). Dead links. `cutctx.dev` vs `cutctx.com` confusion. |
| **Onboarding & Support** | 🟡 5/10 | CLI install works. Discord exists. No self-serve support portal. No knowledge base. `security@cutctx.dev` domain is NXDOMAIN. |
| **Legal & Compliance** | 🟡 6/10 | Terms, Privacy, SLA, DPA template exist. No SOC 2. No HIPAA. No bug bounty. Pricing sheet is clear. |
| **Marketing & GTM** | 🟡 5/10 | GTM plan exists. Blog posts exist. Pricing defined. But `cutctx.com` doesn't resolve. GitHub org 404s. 3rd-party reviews use old name "Headroom." |
| **Enterprise Readiness** | 🟡 5/10 | SSO, RBAC, SCIM, MFA, audit exist. Air-gap mode, data residency, K8s/Helm ready. No PGP key. No security.txt. No SOC 2. SEats/Builder tier inconsistent with marketing. |
| **Competitive Position** | 🟡 5/10 | Strong technology. But a near-identical OSS competitor (losi10/headroom) exists. Market is crowded with 15+ MCP-native tools. |
| **Overall** | **🟡 5.5/10** | **OSS-ready, not commercial-ready.** |

---

## 1. Product & Features

### Compression Engine (🟢 Strong)
The core compression pipeline is the strongest asset:
- **10+ specialized compressors**: SmartCrusher (JSON), CodeCompressor (tree-sitter AST), Kompress-v2 (150M-param ModernBERT), LogCompressor, DiffCompressor, Drain3, SearchCompressor, ImageCompressor, AudioCompressor, SchemaCompressor, LLMLingua integration
- **CCR (reversible compression)**: originals cached locally, retrievable on demand — corrects the biggest objection to lossy compression
- **CacheAligner**: stabilizes KV-cache prefix for provider-side caching discounts
- **Proven savings**: 47–92% on real workloads (code search, SRE incidents, GitHub triage)
- **Rust core**: pyo3 bindings, tree-sitter + stack-graphs for AST-aware compression
- **30+ integration extras** in pyproject.toml (LangChain, Agno, Langfuse, LiteLLM, LlamaIndex, Strands, MCP, etc.)

### Agent Coverage (🟢 Strong)
Supports Claude Code, Codex, Cursor, Aider, Copilot, Windsurf, Zed, OpenCode, OpenClaw, and more via `cutctx wrap`. Plus VSCode and JetBrains extensions.

### Dashboard (🟡 Basic)
- **9 pages**: Overview, Docs, Governance, Capabilities, Firewall, Orchestrator, Playground, Memory, Replay
- **Strengths**: Dark/light theme, responsive (3 breakpoints), Keyboard shortcuts, reasonable accessibility (aria-labels, roles), zero console.log/todo in source, error boundary wrapping routes, 401 auth-gate screen
- **Weaknesses**: No TypeScript, no UI component library (copy-pasted MetricCard/StatusBullet across pages), no i18n, no lazy loading/code splitting (all pages statically imported), no 404 page, no toast/notification system, no logout button, no onboarding wizard, no dedicated components/hooks/utils directories, form validation is all imperative if-checks, `hero.png` + `react.svg` + `vite.svg` are dead assets

### Memory System (🟢 Strong)
Cross-agent memory with Qdrant (vector) and Neo4j (graph) backends. `cutctx learn` mines failed sessions and writes corrections to CLAUDE.md/AGENTS.md. 36 modules, 472KB of memory code. Deduplication across Claude/Codex/Gemini.

---

## 2. Code Quality & Testing

### Test Suite (🟢 Strong)
- **7,565 passing tests** (per latest verification sweep), 285 skipped (credential-gated: OpenAI, Anthropic, Gemini, AWS Bedrock), 22 warnings
- **401 test files** covering: backends, cache, transforms, CLI, memory, providers, proxy, compression, e2e, parity, fuzzing
- **4-shard pytest-split** in CI, asyncio_mode=auto, custom markers (slow, real_llm, live, no_auto_admin)
- **Rust/Python parity tests**: `test_smart_crusher_rust_parity.py`, `test_diff_compressor_rust_parity.py`
- **Dashboard e2e**: Playwright tests covering auth, capabilities, firewall, overview, playground, replay, UI

### CI/CD (🟢 Strong)
- **22 GitHub Actions workflows** covering CI, release, Docker, Rust, eval, benchmarks, chaos testing, devcontainers, stale, PR health, e2e (Docker + native), supply-chain signing (Ed25519 + cosign), network-diff-capture, docs deployment
- **Least-privilege permissions** on most workflows
- **Hard smoke gates**: `smoke-import-wheels` in release.yml prevents publishing broken wheels
- **concurrency groups** on all state-mutating workflows

### CI/CD Gaps (🟡)
1. **No SAST/SCA in CI** — no Bandit, CodeQL, Trivy, Grype, or `safety` run
2. **No `codeql.yml`** or **Scorecards** workflow
3. **Dependabot missing npm ecosystem** — dashboard React deps not auto-updated
4. **No cargo ecosystem in Dependabot** — Rust crate deps not auto-updated
5. **No pre-commit hooks** for standard hygiene (check-yaml/toml/json, detect-private-key, large-files)
6. **No CI/CD alerting** — no Slack/Discord/PagerDuty notifications on failure
7. **Single Python version (3.12)** in CI test shards despite classifiers claiming 3.10–3.14
8. **Windows e2e excluded** (upstream MSVC CRT conflict) — documented but status unclear
9. **Coverage is informational** — no `fail_under` threshold, no Codecov target percentage

### Current Status (per PRODUCTION_FIX_PLAN.md)
Latest sweep: `7565 passed, 285 skipped, 22 warnings`. Dashboard production build passes. Three strategic gaps closed (WS7, WS8, EE audit chain). PRODUCTION_FIX_PLAN.md states: *"Not ready for a fully trust-based READY verdict while worktree remains dirty, Rust/cargo verification not reproducible, live traffic doesn't show model-routing savings firing."*

---

## 3. Security

### Strengths (🟢)
1. **Layered authentication**: admin key (HMAC compare_digest) + SSO/JWT + TOTP MFA with replay protection
2. **Hardware-bound state encryption**: machine-id + hostname + username triple binding via Fernet
3. **K8s pod security**: non-root (uid 65534), seccomp RuntimeDefault, read-only rootfs, drop ALL caps, no hostNetwork
4. **Cryptographic data-residency attestation**: Ed25519-signed proofs with audit-chain tail hash
5. **Defense-in-depth debugging protection**: `loopback_guard` checks client IP + Host header (DNS rebinding defense)
6. **LLM Firewall**: 27 regex patterns (injection, PII, jailbreak, exfil), streaming redactor, ML classifier
7. **Audit logging**: 50+ AuditAction types, RBAC-gated, includes IP + UA context
8. **All SQL parameterized** — no injection vectors found (one `# nosec B608` site to review)
9. **Stripe webhook**: constant-time HMAC-SHA256 signature verification, server-controlled tier derivation (not from metadata)

### Critical (🔴)
1. **X-Cutctx-Role HTTP header honored** — `RbacChecker.resolve_role()` trusts the `X-Cutctx-Role` header if present. When CORS defaults to `*`, any cross-origin site can set this header via preflight request and escalate to admin. **Must gate behind a trusted-proxy/loopback-only check.**

### High (🟠)
2. **`.env.secret` contains a 64-hex Ed25519 private key in plaintext**: verify this file is gitignored and never pushed to any remote. Rotate key if it has ever left local disk.
3. **No PGP key / security.txt / public bug bounty**: blocks high-assurance enterprise procurement. Documented in security audit as C7/C8 blockers.
4. **SSRF allowlist in structured_output.py** only covers 3 hosts (`api.anthropic.com`, `api.openai.com`, `generativelanguage.googleapis.com`). New providers require code change.
5. **K8s NetworkPolicy egress is 0.0.0.0/0 on 80/443/53** — AWS metadata endpoint 169.254.169.254 reachable. No egress CIDR restriction.

### Medium (🟡)
6. **Key reuse**: `CUTCTX_LICENSE_HMAC_SECRET` used for both HMAC license signing AND Fernet encryption fallback (`secrets_store.py:64`). Separate env vars needed with HKDF domain separation.
7. **No automated SAST/SCA in CI** — no Bandit, Trivy, CodeQL, or dependency vulnerability scanning
8. **No npm ecosystem in Dependabot** — dashboard/marketing dependencies not auto-updated
9. **MFA uses HMAC-SHA1** (RFC 6238 standard, but SHA-1 deprecated; RFC 6238bis recommends SHA-256)
10. **Image not pinned by digest** in `k8s/deployment.yaml` (`v0.29.0` tag is mutable)
11. **Rate limiting**: single "default" bucket for unauthenticated traffic (DoS risk)
12. **Webhook idempotency**: no deduplication store for Stripe event IDs

### Low (🟢)
13. **SQLite license DB unencrypted at rest** (unlike signed-token caches which are Fernet-encrypted)
14. **No CSP/HSTS headers** confirmed in ingress config
15. **No cert pinning** for upstream LLM providers (acceptable — cert rotation common)

---

## 4. Billing & Payments

### What Works (🟢)
- Stripe checkout session completed → webhook → license key generation (HMAC-SHA256 signed) → SQLite persistence
- License validation chain: PitchToShip online → ECDSA signed token → local SQLite fallback
- Ed25519 token signing (`hrk1.*`) and ECDSA P-256 token verification (`pts1.*`)
- Strict mode gate: webhook refuses unsigned events when `CUTCTX_BILLING_STRICT_MODE=1`
- Tier derived from `price.id` (server-controlled), not from `metadata.tier` (client-controlled) — correct security pattern
- Fail-closed for unknown entitlement features
- 60+ features mapped to minimum required tier (BUILDER/TEAM/BUSINESS/ENTERPRISE)

### What's Broken / Stub (🔴)
1. **`_send_license_email` is a `logger.info()` stub** — users never receive their license keys
2. **`invoice.paid` handler returns `{"ok": True, "action": "extended"}` without extending the license DB row** — recurring billing doesn't actually extend the license
3. **`customer.subscription.deleted` is a log-only no-op** — canceled subscriptions leave licenses `active=True` until the 1-year default `expires_at`
4. **`customer.subscription.updated` is a log-only no-op** — tier downgrades/upgrades are not reflected
5. **No webhook idempotency** — duplicate events can create duplicate license rows
6. **No refund/cancellation flow** — no `charge.refunded`, `customer.subscription.paused` handlers
7. **No dunning** — `invoice.payment_failed` not handled, no retry logic, no grace period
8. **No upgrade/downgrade path** — second checkout creates a second license row, not a swap
9. **Seat allocation default (5) read from client-controlled `metadata.seats`** — attacker can set `metadata.seats=9999` for unlimited seats at team pricing

### Pricing Issues (🟡)
10. **Seat limit inconsistency**: `seats.py:28-33` defines Builder = 1 seat (contradicting marketing docs which say free)
11. **No Stripe SDK calls anywhere**: system is fully delegated to PitchToShip SaaS
12. **No test-mode separation**: operators must rely on env var discipline
13. **Hardcoded production URLs**: `https://pitchtoship.com` in multiple locations

---

## 5. Documentation

### Strengths (🟢)
- **50+ wiki pages** (MkDocs/Material), **60+ docs files** (Next.js/Fumadocs site)
- **Comprehensive**: quickstart, getting-started, installation (pip/npm/Docker/persistent), API reference, CLI reference, troubleshooting, architecture, deployment (Docker/K8s/Helm/macOS), security, pricing, enterprise
- **Runable code examples**, CLI output examples, mermaid diagrams, screenshots
- **llms.txt** (67 lines) with curated links to all major docs sections
- **Changelog** (64KB), TERMS.md, PRIVACY.md, SLA.md, ENTERPRISE.md, LICENSING.md
- **Security docs**: SECURITY_POLICY, SOC2_CONTROLS, VENDOR_SECURITY_QUESTIONNAIRE
- **Legal**: TERMS.md, PRIVACY.md, SLA.md, DPA template, MSA template
- **GTM materials**: blog posts (3), acquisition plan, outreach plan, sales playbook, case study template, ROI calculator
- **Artifacts**: pricing sheet, security one-pager, onboarding runbook, pilot offer template, procurement packet

### Critical Issues (🔴)
1. **`cutctx.com` NXDOMAIN** — main product domain doesn't resolve. `cutctx.dev` works but finding inconsistent across docs.
2. **`github.com/cutctx/cutctx` 404** — GitHub org doesn't exist. Actual repo is `headroomlabs-ai/headroom` or `AryanSingh/headroom`.
3. **`security@cutctx.dev` bounces** — email domain is NXDOMAIN. Some files use `@cutctx.com`, others `@cutctx.dev`.
4. **Brand name inconsistency**: product name "Cutctx" but directory "headroom", PyPI has old `headroom-ai` package, 3rd-party reviews use "Headroom". README does document the aliasing, but inconsistency confuses.

### Documentation Gaps (🟡)
5. **No FAQ.md** — FAQ content scattered across PRODUCT_GUIDE.md §20 and troubleshooting section
6. **No UPGRADE.md / MIGRATION.md** — changelog is the only upgrade source
7. **`wiki/` and `docs/` overlap** — getting-started, proxy, MCP, config pages duplicated
8. **`wiki/getting-started.md:11` says `pip install cutctx`** (should be `cutctx-ai`)
9. **`wiki/troubleshooting.md:468` links to `cutctx-sdk` GitHub org (wrong)**
10. **Blog CTAs point to `cutctx.sh`** (dead domain)
11. **K8s manifests reference old brand + personal namespace** (`k8s/deployment.yaml:42` uses `cutctx-proxy:v0.26.0`)
12. **Java SDK still on `com.cutctx.CutctxClient`**
13. **`docs/README.md` has hardcoded filesystem paths from another machine**
14. **Hand-written API reference** — no auto-generation from docstrings/Sphinx/mkdocstrings
15. **Dashboard docs page** flagged for severe mobile cramping (390×844)

---

## 6. Onboarding & Support

### What Works (🟢)
- `pip install cutctx-ai[all]` / `npm install cutctx-ai`
- `cutctx proxy --port 8787` — single command to start
- `cutctx wrap claude` / `cutctx wrap codex` — one-command agent wrapping
- `cutctx init` / `cutctx setup` — guided flows with agent detection
- Docker: `docker run -p 8787:8787 ghcr.io/cutctx/cutctx:latest`
- Devcontainers for both default and memory-stack (Qdrant + Neo4j)
- Discord community link in README
- Example notebooks: 07-context-compression.ipynb, langchain_demo, mcp_demo, strands_demo

### Gaps (🟡)
1. **No self-serve support portal** — contact is `hello@cutctx.dev` (NXDOMAIN for .dev variant) or `hello@cutctx.com`
2. **No knowledge base** — documentation covers tech specs but no "common problems" knowledge base
3. **No onboarding wizard in dashboard** — dashboard assumes proxy is already running
4. **No email delivery infrastructure** — license keys, receipts never sent (stub)
5. **SLA.md** exists but no support ticket system integration
6. **Windows PowerShell install script not published** — documented in getting-started.md
7. **Discord invite** redirects but hasn't been confirmed as an active community

---

## 7. Legal & Compliance

### What Exists (🟢)
- TERMS.md (76 lines, Delaware governing law, 30-day termination, liability cap = 12mo fees)
- PRIVACY.md (101 lines, local-first, no telemetry by default)
- SLA.md (1.7KB)
- DPA_TEMPLATE.md, MSA_TEMPLATE.md, TERMS_OF_SERVICE_DRAFT.md
- LICENSE (Apache-2.0), LICENSE-COMMERCIAL, NOTICE (attributions)
- LICENSING.md: authoritative open-core boundary map
- SECURITY.md (supported versions 0.29.x, 48hr ack, 7d critical fix)
- CODE_OF_CONDUCT.md, CONTRIBUTING.md
- Commercial entity: Payzli Inc. (operating as Cutctx Labs), Delaware, US

### Gaps (🟡)
1. **No SOC 2** — SOC2_CONTROLS.md exists (compliance framework) but no audit. gtm/soc2-roadmap.md exists but is forward-looking.
2. **No HIPAA readiness** — listed as enterprise feature in entitlements.py but no formal HIPAA assessment
3. **No ISO 27001**
4. **No bug bounty** — "evaluating for 2027" per vendor questionnaire
5. **No security.txt** at `/.well-known/security.txt`
6. **No PGP key published** for `security@cutctx.com`
7. **TERMS.md labeled as "draft template"** — not a final legal document
8. **Terms reference "cutctx" not "Payzli Inc."** — legal entity naming inconsistency
9. **No privacy policy version history** or effective date tracking

---

## 8. Marketing & GTM

### What Exists (🟢)
- GTM comprehensive acquisition plan (cutctx-comprehensive-acquisition-plan.md)
- SMB outreach plan (outreach-plan-smb.md)
- 3 blog posts: token-costs, reversible-compression, cross-agent-memory
- lead_gen.py (30KB lead generation tool)
- ROI calculator, case study template, pilot offer template
- Value proposition document
- Pricing sheet: Builder (Free), Team ($18K/yr), Business ($42K/yr), Enterprise ($60-150K+/yr)
- 3rd-party reviews: neural-nexus.net, miyagadget.page (79.8% code compression measured), andrew.ooo

### Critical Gaps (🔴)
1. **`cutctx.com` doesn't resolve** — no landing page, no marketing site
2. **`github.com/cutctx` org doesn't exist** — GitHub presence is under `headroomlabs-ai` (upstream) and personal forks
3. **`huggingface.co/cutctx` org doesn't exist** — model is under `chopratejas/kompress-base`
4. **All blog CTA links point to `cutctx.sh`** (dead domain)
5. **3rd-party reviews use "Headroom"** — brand rename hasn't propagated

### Marketing Gaps (🟡)
6. **No demo video** beyond the GIF in README
7. **No comparisons page** (vs Headroom, vs context-compress, vs lessloss)
8. **No benchmark landing page** — benchmarks exist in wiki/benchmarks.md but no marketing-facing version
9. **No case studies** — template exists, none published
10. **No "pricing" page on website** — pricing exists only in artifacts/pricing-sheet.md
11. **No newsletter / mailing list**
12. **No social media presence** (beyond GitHub and Discord)
13. **No PR / analyst outreach** materials
14. **No self-serve signup flow** — users must email hello@cutctx.com

---

## 9. Enterprise Readiness

### What Works (🟢)
- **SSO**: OIDC/JWT/JWKS/introspection (Okta, Azure AD, Auth0, Google)
- **RBAC**: Viewer/MemoryCurator/Operator/Admin with 40+ permissions, SQLite-backed
- **SCIM**: user/group provisioning
- **MFA**: TOTP with replay protection
- **Audit**: 50+ action types with IP/UA context, RBAC-gated
- **Dedicated routes**: `/v1/dsr/*`, `/v1/residency/*`, `/v1/airgap/*`, `/v1/rate_limit/*`, `/v1/rbac/*`, `/v1/secrets/*`, `/v1/sso/*`, `/v1/memory/*`, `/v1/spend/*`, `/v1/policies/*`, `/v1/admin/mfa/*`
- **Air-gap mode**: `CUTCTX_OFFLINE_MODE=1` with required `CUTCTX_LICENSE_HMAC_SECRET`
- **Data residency**: Ed25519-signed attestation with audit-chain tail hash
- **K8s**: Full manifests (deployment, HPA, PDB, network-policy, prometheus-rules, fluentbit, backup-cronjob, rbac, namespace)
- **Helm chart**: Chart + values + templates
- **Fleet management**: listed in entitlements.py as enterprise feature

### Enterprise Gaps (🟡)
1. **No SOC 2 / HIPAA certs** — documented as "What Still Requires External Work" in ENTERPRISE.md
2. **No PGP key / security.txt** — blocks security-sensitive procurement
3. **No bug bounty** — procurement requirement for many enterprises
4. **No single-tenant / dedicated deployment option** documented beyond air-gap mode
5. **No SIEM integration** (Splunk, Datadog, etc.) beyond OpenTelemetry
6. **No documented backup/DR procedure** beyond k8s backup-cronjob.yaml
7. **No documented scaling limits** (max instances, throughput, concurrent sessions)
8. **No multi-region deployment architecture** documented
9. **No enterprise support portal** — all support is email + Discord
10. **No onboarding sessions** — listed as enterprise add-on, no operational capability

---

## 10. Competitive Position

### Competitive Context
Cutctx enters a market that has crystallized into four categories:
1. **Direct compression tools**: Headroom (losi10/headroom), lessloss, ContextZip, 15+ MCP-native tools
2. **Semantic caching**: GPTCache, PromptCacheAI
3. **Agent memory frameworks**: Mem0, Zep/Graphiti, Letta (ex-MemGPT)
4. **LLM proxy/observability**: Portkey, Helicone, LangSmith (adding compression features)

### Existential Threat: Headroom (losi10/headroom)
**This is the single most important competitor.** Headroom is feature-complete for the same scope (tool outputs, logs, RAG, files, conversation history), claims the same savings range (70–95%), supports the same deployment modes (proxy, library, MCP), and is Apache-2.0 OSS with no commercial tier. The README even compares itself against "Cloud compression APIs" (Compresr, Token Company) — the same positioning Cutctx would use.

**Cutctx must articulate:** "What do we do that Headroom doesn't?" Possible answers:
- Better agent-framework coverage (more `wrap` targets)
- Tighter Codex/Hermes/OpenClaw integration
- Better enterprise controls (SSO/RBAC/SCIM/Audit)
- Faster innovation velocity / roadmap

### Crowded MCP-Native Segment
15+ products launched 2025–2026 targeting tool-output compression specifically (context-compress, universal-context-mode, ContextZip, Token Smithers, MCP Compressor from Atlassian, DietMCP, code-context-engine, mcp-code-context, lean-ctx, sqz, etc.). Most claim 60–99% reduction. Cutctx's advantage: scope (everything, not just tool output) and reversible CCR.

### Market Threats
1. **Bigger context windows** — Gemini 2M, Claude 1M, GPT-5 400K reduce urgency of compression
2. **"Compress everything" is table stakes** — every 2025-2026 entrant claims this
3. **"Local-first" alone is not differentiated** — Headroom, lessloss, Token-Saver all claim local-only
4. **50-90% savings claims are saturated** — need sharper metrics (cost saved, not tokens)
5. **MCP is the de-facto integration surface** — products without MCP-first design are behind

### Cutctx's Defensible Advantages
1. **Rust core** (tree-sitter, stack-graphs, Ed25519 signing) — not pure Python
2. **CCR (reversible compression)** — only product doing this
3. **CacheAligner** — KV-cache prefix stabilization
4. **Enterprise feature set** — SSO, RBAC, SCIM, MFA, audit, data residency, air-gap
5. **Integration breadth** — 30+ extras, 10+ agent wraps, VSCode + JetBrains extensions
6. **`cutctx learn`** — agent self-improvement is unique
7. **Proven third-party benchmarks** — miyagadget.page, neural-nexus.net, andrew.ooo

---

## 11. Risk Register

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| X-Cutctx-Role privilege escalation exploited | Critical | Medium | Gate header behind trusted-proxy config before public launch |
| cutctx.com domain squatting | High | Medium | Secure domain before GA announcement |
| Billing webhook stubs cause revenue leakage | High | High | Fix invoice.paid, subscription.deleted, email delivery before any paid customer |
| GitHub org squatting | High | Medium | Create cutctx org and redirect |
| Headroom (losi10) captures all OSS mindshare | High | Medium | Publish differentiation doc; engage design partners |
| Competitive MCP-native tools fragment market | Medium | High | Double down on cross-agent memory + CCR differentiation |
| .env.secret private key leaked | Critical | Low | Verify gitignore, rotate immediately if pushed |
| Dashboard lacks mobile responsiveness | Low | Medium | Desktop-only acceptable for v1; document as known limitation |
| No SOC 2 blocks enterprise deals | Medium | High | Engage SOC 2 audit in parallel with GA |
| No bug bounty blocks security-sensitive procurement | Medium | Medium | Launch private program with HackerOne/Intigriti |
| Brand confusion (cutctx vs headroom) | Medium | High | Consistent messaging in all channels; accept transition period |
| Windows support gaps | Low | Medium | Document as known limitation |

---

## 12. Go/No-Go Recommendation

### Assessment Criteria

| Criterion | Weight | Score | Weighted |
|-----------|--------|-------|----------|
| Product functions end-to-end | 30% | 8/10 | 2.4 |
| Security (no critical gaps) | 20% | 6/10 | 1.2 |
| Can collect revenue | 15% | 3/10 | 0.45 |
| Documentation supports users | 10% | 6/10 | 0.6 |
| Support channel exists | 5% | 5/10 | 0.25 |
| Legal cover adequate | 10% | 6/10 | 0.6 |
| Go-to-market ready | 10% | 5/10 | 0.5 |
| **Total** | **100%** | | **6.0/10** |

### Verdict: CONDITIONAL GO

**OSS Release (v0.30.0): GO**
The open-source product is ready for release. Compression engine is mature, 7,565 tests pass, security is defense-in-depth, CI/CD is comprehensive. Known issues are documented. Ship it.

**Commercial Sales: NO-GO (with conditions)**
Do not onboard paying customers until:

### Must-Fix Before First Paid Customer (BLOCKERS)
| # | Item | Severity | Owner |
|---|------|----------|-------|
| 1 | **Fix `invoice.paid` webhook** to extend license `expires_at` in DB | Revenue leak | Engineering |
| 2 | **Fix `subscription.deleted`** to deactivate license | Revenue leak | Engineering |
| 3 | **Fix `_send_license_email`** — wire up SendGrid/SES/Postmark | Customer experience | Engineering |
| 4 | **Fix X-Cutctx-Role header** — gate behind `CUTCTX_TRUST_PROXY` env var | Critical security | Engineering |
| 5 | **Install `cutctx.com` DNS** pointing to docs + landing page | Marketing presence | Ops |
| 6 | **Create `github.com/cutctx` org** and transfer repo | Credibility | Ops |
| 7 | **Create `huggingface.co/cutctx` org** and publish model | Credibility | Ops |
| 8 | **Secure `@cutctx.com` email** — verify MX records, fix NXDOMAIN | Communication | Ops |
| 9 | **Add webhook idempotency** using Stripe event IDs | Revenue integrity | Engineering |
| 10 | **Fix seats metadata vulnerability** — derive seats from `price_id` not `metadata.seats` | Security | Engineering |

### Should-Fix Within 30 Days of First Customer (HIGH PRIORITY)
| # | Item | Impact |
|---|------|--------|
| 11 | Add SAST/SCA to CI (Bandit + CodeQL or Trivy) | Security posture for procurement |
| 12 | Add npm + cargo ecosystems to Dependabot | Supply chain security |
| 13 | Implement upgrade/downgrade webhook path | Customer retention |
| 14 | Implement dunning (failed payment retry + grace period) | Revenue protection |
| 15 | Add security.txt + PGP key | Enterprise procurement requirement |
| 16 | Launch private bug bounty (HackerOne/Intigriti) | Enterprise procurement requirement |
| 17 | Resolve brand inconsistency in K8s/Java/Go SDKs | Professionalism |
| 18 | Fix dead links in docs (cutctx.sh → cutctx.dev) | User experience |
| 19 | Set coverage fail_under threshold | Engineering discipline |
| 20 | Add `UPGRADE.md` / `MIGRATION.md` | User experience |

### Could-Fix (Within 90 Days)
| # | Item | Impact |
|---|------|--------|
| 21 | Publish case studies from design partners | Marketing |
| 22 | Benchmark comparison page (vs Headroom, vs lessloss) | Competitive differentiation |
| 23 | Initiate SOC 2 Type I audit | Enterprise readiness |
| 24 | Add CI/CD alerting to Slack/Discord | Operational readiness |
| 25 | Add lazy loading / code splitting to dashboard | Performance |
| 26 | Single Python version matrix in CI (3.10, 3.13, 3.14) | Compatibility |

---

## 13. Recommended Launch Plan

### Phase 1: Blockers (Week 1)
Fix 10 blocker items. Simultaneously secure domain, GitHub org, HF org, email infrastructure.

### Phase 2: v0.30.0 OSS Release (Week 2)
Tag and publish v0.30.0. GitHub release with changelog. Announce on Discord, Twitter/X, Hacker News. Target: "Ship it."

### Phase 3: Design Partner Program (Weeks 3-6)
Onboard 3-5 design partners at reduced pricing ($5-10K vs $18K). Free onboarding + dedicated Slack channel. Gather case study material. Validate billing system end-to-end with real money. Fix blockers 11-20.

### Phase 4: Commercial GA (Week 8+)
Publish case studies. Open paid signups at Team ($18K/yr) tier. Published SOC 2 roadmap. Active bug bounty. Security.txt live. `cutctx.com` marketing site with pricing page.

---

## 14. Quick Reference: Key Numbers

| Metric | Value |
|--------|-------|
| Tests passing | 7,565 |
| Tests skipped | 285 (credential-gated) |
| CI workflows | 22 |
| Wiki docs | 50+ (53 files) |
| Docs pages | 60+ (Fumadocs site) |
| GitHub stars | 0 (on fork, upstream unknown) |
| HF model downloads | 2,889/month |
| Third-party reviews | 3 (neural-nexus, miyagadget, andrew.ooo) |
| Compression compressors | 10+ specialized |
| Integration extras | 30+ in pyproject.toml |
| Pricing tiers | 4 (Builder $0, Team $18K/yr, Business $42K/yr, Enterprise $60-150K+/yr) |
| Commercial entity | Payzli Inc. (operating as Cutctx Labs) |
| Security response SLA | 48hr ack, 7d critical fix |
| Latest pyproject version | 0.30.0 |

---

## Appendix A: Blockers Detail

### Blocker 1: `invoice.paid` handler is a stub
**Current behavior:** `stripe_webhook.py:191-192` returns `{"ok": True, "action": "extended"}` without extending `licenses.expires_at`.
**Fix scope:** Parse `current_period_end` from subscription object, update DB row. ~1 day.

### Blocker 2: `subscription.deleted` handler is a stub
**Current behavior:** `stripe_webhook.py:149-155` is a log-only no-op.
**Fix scope:** Set `licenses.active = 0`, log revocation, emit audit event. ~4 hours.

### Blocker 3: `_send_license_email` is a stub
**Current behavior:** `stripe_webhook.py:172-180` calls `logger.info()` only.
**Fix scope:** Integrate SendGrid/SES/Postmark API. ~2 days plus API key setup.

### Blocker 4: X-Cutctx-Role privilege escalation
**Current behavior:** `cutctx_ee/rbac.py:139-144` accepts `X-Cutctx-Role` header without verifying request source.
**Fix scope:** Add `CUTCTX_TRUST_PROXY` env var (default false); only honor the header when set. ~1 day.

### Blocker 5-8: Infrastructure DNS/GitHub/Email
**Current behavior:** `cutctx.com` NXDOMAIN, `github.com/cutctx` 404, `huggingface.co/cutctx` 404, `@cutctx.dev` bounces.
**Fix scope:** Domain registration, DNS, GitHub org creation, HuggingFace org creation, MX record setup. ~1 day each, can parallelize.

### Blocker 9: Webhook idempotency
**Current behavior:** No deduplication store for Stripe event IDs. Duplicate checkout can create multiple license rows.
**Fix scope:** Add `processed_events` SQLite table with unique constraint on `stripe_event_id`. Check before processing. ~1 day.

### Blocker 10: Seats metadata vulnerability
**Current behavior:** `stripe_webhook.py:98` reads `session.metadata.seats` (client-controlled). No server-side seat limit enforcement.
**Fix scope:** Derive seats from `price_id` → tier → seat limit in `seats.py`. ~4 hours.

---

*Report generated July 4, 2026. Based on codebase audit of commit in `/Users/aryansingh/Documents/Claude/Projects/headroom` (HEAD as of assessment date). All 6 background task results reconciled.*
