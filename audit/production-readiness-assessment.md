# Cutctx — Production Readiness Assessment

**Date:** July 4, 2026  
**Codebase:** ~478K LOC (404K Python + 74K Rust), 1,163 Python files + 195 Rust files  
**Audit scope:** Security · Testing · Deployment · Code maturity · Monitoring · Completeness

---

## Readiness Score: 55 / 100

| Dimension | Score | Weight | Weighted |
|---|---|---|---|
| **Security** | 45 | 20% | 9 |
| **Testing** | 65 | 15% | 10 |
| **Deployment** | 35 | 25% | 9 |
| **Code maturity** | 55 | 15% | 8 |
| **Monitoring** | 60 | 15% | 9 |
| **Feature completeness** | 70 | 10% | 7 |
| **Overall** | **55** | 100% | |

### Verdict

**Not production-ready in its current state.** The core compression pipeline and proxy are well-engineered (strong auth, excellent CI/CD, comprehensive metrics), but **8 CRITICAL findings** across security and deployment make it unsafe to deploy in production without remediation. The biggest blockers are:

1. **Kubernetes cannot safely run this** — port mismatch, no persistent storage, UID mismatch, missing secrets
2. **Enterprise data is unprotected** — SQLite databases unencrypted, hardcoded signing key on developer machine
3. **Production crashes are invisible** — no error tracking, no crash reporting, no global exception handler
4. **Rust core has structural reliability debt** — 904 unwrap() and 70+ panic!() in the hot path

---

## Summary of Findings by Severity

### 🔴 CRITICAL (8 findings — block production deployment)

| # | Finding | Category | Detail |
|---|---|---|---|
| C1 | **No persistent storage in k8s** — all state lost on pod restart | Deployment | All SQLite DBs (memory, audit, spend, RBAC, org, SCIM) write to read-only rootfs. PVC not created. 60+ env vars' worth of data gone on every restart. |
| C2 | **k8s port mismatch** — deployment binds 8080, Helm/docker-compose use 8787 | Deployment | `k8s/deployment.yaml` passes `--listen-addr 0.0.0.0:8080` (flag doesn't exist in CLI), `helm/cutctx/values.yaml` uses 8787. Proxy fails to start with raw k8s manifests. |
| C3 | **UID mismatch in k8s** — runs as uid 65534, files owned by uid 1000 | Deployment | `k8s/deployment.yaml` sets `runAsUser: 65534`. Dockerfile creates `nonroot` user at uid 1000. EE modules get EACCES writing to `~/.cutctx/`. |
| C4 | **Helm chart missing EE secret templates** — crashes on first request | Deployment | `CUTCTX_LICENSE_KEY`, `CUTCTX_AUDIT_SECRET_KEY`, `CUTCTX_UPSTREAM_*_API_KEY` have no Secret template. `audit/store.py` raises `RuntimeError` on missing secret. |
| C5 | **Image tag drift** — manifests pinned to v0.29.0, latest is v0.30.0 | Deployment | Both `k8s/deployment.yaml` and `helm/cutctx/values.yaml` reference v0.29.0. Next release won't roll out. |
| C6 | **SQLite databases unencrypted at rest** — policy violation for Restricted data | Security | Memory DB, audit DB, spend ledger, and compression cache DB are plaintext SQLite. Security policy classifies customer prompts/completions as Restricted. An attacker with disk/backup access gets all extracted facts. |
| C7 | **Hardcoded Ed25519 signing key in `.env.secret`** | Security | 64-hex-char 32-byte Ed25519 private key seed persisted on developer machine. If production key, any compromise mints enterprise-tier licenses. |
| C8 | **`server.py` is 6,889 lines** — god file, 22 silent `except: pass` blocks | Code maturity | The proxy's main server file is 10× the recommended max. The 22 silent `except: pass` blocks in the hot path swallow errors silently — dangerous for a request proxy. |

### 🟠 HIGH (15 findings — serious, fix within the same release)

| # | Finding | Category |
|---|---|---|
| H1 | **Stripe webhook missing timestamp tolerance** — replay attacks possible | Security |
| H2 | **Runtime-app admin auth fallback** — no auth if no admin key configured | Security |
| H3 | **`_validate_metadata_key` not wired** — SQL injection risk via where_clause | Security |
| H4 | **`cargo audit` soft-fails in CI** — known CVEs don't block merges | Security/CI |
| H5 | **No `pip-audit` in CI** — Python vulnerabilities untracked | Security/CI |
| H6 | **No error tracking** (Sentry/DataDog) — crashes invisible to operators | Monitoring |
| H7 | **No global exception handler** — no centralized crash reporting | Monitoring |
| H8 | **Rust core: 904 `unwrap()` + 70+ `panic!()`** in source files | Code maturity |
| H9 | **EE `watermark.py:195` license validation stub returns `True`** — security bypass | Code maturity |
| H10 | **EE `memory_service/api.py` has no RBAC or audit emission** | Code maturity |
| H11 | **No external secret management** — static k8s Secret placeholders shipped | Deployment |
| H12 | **k8s NetworkPolicy too permissive** — any namespace can reach proxy | Deployment |
| H13 | **No ServiceMonitor** — Prometheus operator requires manual config | Deployment |
| H14 | **`prometheus-rules.yaml` is a stub** — 2 alerts, no cost/OOM/audit chain alerts | Monitoring |
| H15 | **Backup CronJob references non-existent PVC and S3 bucket** | Deployment |

### 🟡 MEDIUM (18 findings — fix within the next release)

| # | Finding | Category |
|---|---|---|
| M1 | MD5 used for cache keying (policy violation) | Security |
| M2 | Wide-open CORS in runtime-app branch | Security |
| M3 | Audit logger init failure doesn't block proxy startup | Security |
| M4 | Coverage not uploaded from main CI | Testing |
| M5 | Network failures silently downgraded to skip (anti-pattern) | Testing |
| M6 | Single Python version (3.12) in main CI matrix | Testing |
| M7 | Fuzz targets exist but never run in CI | Testing |
| M8 | No performance regression thresholds in benchmark CI | Testing |
| M9 | ~20 proxy modules lack standalone unit tests (integration-only coverage) | Testing |
| M10 | No structured JSON log format for production log shipping | Monitoring |
| M11 | Abuse detection generates alerts but has no delivery channel | Monitoring |
| M12 | Budget/cost alerting mentioned in README but not implemented | Monitoring |
| M13 | FluentBit config only writes to stdout — no Loki/ES/S3 sink | Monitoring |
| M14 | 10 Python god files > 2,000 lines (server.py worst at 6,889) | Code maturity |
| M15 | 312 `# type: ignore` comments | Code maturity |
| M16 | EE test coverage low (3 test files for 42 source modules) | Testing |
| M17 | No anti-affinity / topology spread in k8s | Deployment |
| M18 | Resource limits likely insufficient for EE features under load | Deployment |

### 🔵 LOW (12 findings — backlog items)

| # | Finding | Category |
|---|---|---|
| L1 | ~14 placeholder `pass`/`assert True` test bodies | Testing |
| L2 | No Grafana/Datadog dashboard JSON shipped | Monitoring |
| L3 | Rust OTel export not configured | Monitoring |
| L4 | No panic hook/faulthandler at proxy startup | Monitoring |
| L5 | 51/519 Python files missing module docstring (9%) | Code maturity |
| L6 | Missing READMEs in 5 major component directories | Code maturity |
| L7 | GPU-dependent Kompress tests fully skipped in CI | Testing |
| L8 | `parity-nightly` Rust parity run allowed to fail | Testing |
| L9 | macOS x86_64 not in wheel matrix (documented tradeoff) | Deployment |
| L10 | No SBOM/Provenance on Docker images | Deployment |
| L11 | No Dependabot for Docker/GitHub Actions/Helm | Deployment |
| L12 | No kustomize overlays for staging/prod | Deployment |

---

## Dimension Deep-Dives

### Security (45/100)

**Strengths:**
- CORS defaults closed, admin key auto-generation, constant-time HMAC comparison
- Audit chain with HMAC-SHA256, fail-closed on missing secret
- No `os.system`/`subprocess(shell=True)`/`eval`/`pickle` in source
- Parameterised SQL queries (except 2 f-string where_clause sites)
- Strong PII redaction in logs (API keys, image content)
- DNS-rebinding defense on debug endpoints
- Anti-debug guard for EE code
- Ed25519 license key signing

**Gaps:**
- SQLite at-rest encryption (memory DB, audit DB, spend ledger — all unencrypted plaintext)
- `.env.secret` with real-looking Ed25519 private key on developer machine
- `cargo audit` soft-fails in CI, no `pip-audit`
- MD5 used across 10+ files despite policy explicitly banning it
- Stripe webhook replay attack (no timestamp tolerance check)
- Runtime-app unauthenticated-fallback path
- Metadata key validator exists but is not wired into production code
- Wide-open CORS in runtime-app branch

### Testing (65/100)

**Strengths:**
- ~9,346 tests (8,079 Python + 1,267 Rust)
- CI with 4-shard pytest-split on ubuntu, macOS, Windows
- 22 CI workflows including nightly chaos, weekly benchmarks
- Fuzz targets exist (3 harnesses, cargo-fuzz)
- Integration tests with live LLM tier opt-in (`@pytest.mark.real_llm`)
- Pre-commit hooks with ruff + mypy

**Gaps:**
- Coverage not collected in main CI (only in native-e2e)
- Network timeout → silent skip (masks flaky failures)
- Single Python version (3.12) in matrix
- Fuzz targets never run in CI
- No performance regression thresholds in benchmarks
- ~14 placeholder test bodies (mostly in `test_toin.py`)
- EE module has 3 test files for 42 source modules

### Deployment (35/100)

**Strengths:**
- Multi-stage Dockerfile with distroless and nonroot variants
- Multi-arch builds (amd64 + arm64) on native runners without QEMU
- Cosign keyless signing of Docker images
- 8 Docker image variants (runtime, runtime-nonroot, code, slim, etc.)
- Full wheel matrix (linux x86_64 + arm64, macOS arm64, Windows)
- Release-please for automated version management
- Comprehensive `.env.example` (236 lines, every var documented)
- Health/readiness/liveness/startup probes, HPA, PDB all configured
- SecurityContext: runAsNonRoot, readOnlyRootFS, no privilege escalation

**Gaps (8 CRITICAL findings in this category):**
- See C1-C5 above — the k8s manifests have fundamental issues that prevent any production deployment
- Helm chart missing EE secrets, PVC, ServiceMonitor
- docker-compose has insecure defaults (placeholder Neo4j password, all-interface binding)

### Code Maturity (55/100)

**Strengths:**
- Zero `# FIXME` or `# HACK` markers in production code
- All `@abstractmethod` implementations correctly use `...` marker
- Intentional parity scaffolding (Phase 0 with `todo!()` — documented)
- 1:1 test-to-source file ratio for OSS modules
- Extensive docs (`docs/` has 74 markdown files, `CHANGELOG.md` is 64KB)

**Gaps:**
- `server.py` at 6,889 lines — the single biggest reliability risk in the codebase
- 22 silent `except: pass` blocks in the proxy hot path
- 904 `unwrap()` in Rust with no error context
- 70+ `panic!()` in 24 Rust source files
- EE watermark license validation stub always returns `True`
- EE memory_service has no RBAC or audit emission

### Monitoring (60/100)

**Strengths:**
- Best-in-class 3-tier health checks (livez/readyz/health) with per-component breakdown
- Comprehensive Prometheus exporter (60+ metric families, cardinality discipline)
- OTel metrics and traces with env-var-driven configuration
- Enterprise-grade audit chain (HMAC-SHA256, REST/CLI/MCP, residency proof)
- Rich React dashboard (9 pages) bundled in the proxy
- Strong PII redaction throughout

**Gaps:**
- No error tracking integration (Sentry/DataDog) — crashes invisible
- No global exception middleware
- No structured JSON log format
- Only 2 Prometheus alert rules
- Abuse detection generates alerts but has no delivery channel
- No budget/cost alerts (despite README promise)
- FluentBit writes to stdout only — no log shipping sink

### Feature Completeness (70/100)

- Core compression pipeline: mature, benchmarked, production-validated
- Memory system: comprehensive (30+ files, hybrid retrieval, proxy injection, cross-agent sync)
- Proxy: full multi-provider support, memory injection, guardrails, savings attribution
- Enterprise: SSO, RBAC, audit, SCIM, fleet management, air-gap
- Gaps: Rust compressor ports pending (PR-B4), LangChain provider stubs, EE watermark stub, `docs/components/` and `docs/lib/` empty

---

## Prioritized Action Plan

### Phase 0 — Stop the Bleeding (Week 1)

*Prevent data loss, unauthorized access, and silent failure.*

| Priority | Finding | Effort | Action |
|---|---|---|---|
| 1 | C2 — Port mismatch | 1 hour | Unify port to 8787 across k8s manifest, Helm values, Dockerfile, and docker-compose |
| 2 | C3 — UID mismatch | 1 hour | Change `runAsUser: 1000` in k8s manifest (Helm already correct) |
| 3 | C5 — Image tag drift | 1 hour | Update k8s/Helm to `v0.30.0` |
| 4 | C1 — No PVC | 1 day | Add `PersistentVolumeClaim` template to Helm chart and raw k8s manifests. Mount at `/home/nonroot/.cutctx`. |
| 5 | C4 — EE secrets | 1 day | Add Secret template for `CUTCTX_LICENSE_KEY`, `CUTCTX_AUDIT_SECRET_KEY`, `UPSTREAM_API_KEY` to Helm chart |
| 6 | C8 — silent except:pass | 2 days | Audit the 22 `except: pass` blocks in `server.py`. At minimum, add `logger.exception()`. Best: convert to structured error reporting. |
| 7 | C7 — .env.secret | 1 day | Rotate the key if production. Remove file. Add pre-commit hook blocking `.env*` files. |
| 8 | H1 — Stripe timestamp | 1 hour | Add `abs(time.time() - int(timestamp)) > 300` check |

### Phase 1 — Production Safety (Weeks 2-3)

*Make crashes visible, data secure, and deployment safe.*

| Priority | Finding | Effort | Action |
|---|---|---|---|
| 9 | C6 — SQLite encryption | 1 week | Adopt SQLCipher for memory/audit/spend DBs, or document opt-in path with Fernet key |
| 10 | H6 — Error tracking | 2 days | Add Sentry SDK with `CUTCTX_SENTRY_DSN` env var, optional opt-in |
| 11 | H7 — Global exception handler | 1 day | Add `@app.exception_handler(Exception)` to centralized crash logging |
| 12 | H4 — cargo audit blocking | 1 hour | Remove `continue-on-error: true` from cargo audit |
| 13 | H5 — pip-audit | 1 day | Add `pip-audit` to CI (or use `pip list --outdated` + safety) |
| 14 | H9 — EE watermark stub | 2 days | Wire real DB query for license validation or add fail-closed path |
| 15 | H10 — EE memory-service RBAC | 3 days | Add RBAC check + audit emission to memory_service endpoints |
| 16 | H2 — Runtime-app auth fallback | 1 day | Mirror main app's auto-generation or refuse to start without key |

### Phase 2 — Hardening (Weeks 4-6)

*Structural improvements to reliability and observability.*

| Priority | Finding | Effort | Action |
|---|---|---|---|
| 17 | H8 — Rust unwrap/panic | 3 weeks | Convert high-risk unwrap() to `?` or `context()` in top-10 offender files (content_detector, live_zone, proxy). Add panic hook for graceful shutdown. |
| 18 | C8 (part 2) — server.py decomposition | 4 weeks | Split `server.py` into domain modules: `routes/`, `middleware/`, `config/`, `handlers/`. Target <1,000 lines per file. |
| 19 | M10 — Structured JSON logging | 2 days | Add `python-json-logger` or `structlog` formatter, configurable via `CUTCTX_LOG_FORMAT=json` |
| 20 | M4 — Coverage in main CI | 1 day | Add `--cov=cutctx` to main 4-shard test job, upload to Codecov |
| 21 | M7 — Fuzz in CI | 1 day | Add `cargo fuzz` step to nightly CI. Currently 3 targets, zero runtime coverage. |
| 22 | M14 — Reduce god files | Ongoing | Break down top-10 largest Python files (server.py first). Establish <2K line lint rule. |
| 23 | M3 — Audit logger fail-fast | 1 day | If `audit_enabled=True` and store init fails, refuse to start proxy |
| 24 | H14 — Prometheus alert rules | 3 days | Add alerts for: OOM, pod restart, audit chain verify fail, cost overage, cache bust spike, license expiry, compression ratio drop |
| 25 | M11 — Abuse alert delivery | 1 week | Add webhook/slack channel for AbuseAlert, configurable via `CUTCTX_ALERT_WEBHOOK_URL` |

### Phase 3 — Polish (Weeks 7-10)

*Performance testing, documentation, platform coverage.*

| Priority | Finding | Effort | Action |
|---|---|---|---|
| 26 | M6 — Multi-version CI | 2 days | Add Python 3.10, 3.11, 3.13 to CI test matrix |
| 27 | M8 — Performance regression gates | 1 week | Add fail-if-regression logic to benchmark.yml (p95 latency, compression ratio, throughput) |
| 28 | M5 — Flaky test handling | 2 days | Replace silent skip-on-timeout with `pytest-rerunfailures` + explicit flaky marker |
| 29 | M16 — EE test coverage | 3 weeks | Add tests for EE modules (currently 3 test files for 42 source modules) |
| 30 | M1 — MD5 → SHA-256 | 1 week | Replace `hashlib.md5` calls with `hashlib.sha256(…).hexdigest()[:16]` or amend policy |
| 31 | M17 — Anti-affinity | 1 day | Add `podAntiAffinity` and `topologySpreadConstraints` to k8s/Helm |
| 32 | M18 — Resource limit tuning | 1 week | Load-test EE features and set realistic resource requests/limits |
| 33 | H12 — NetworkPolicy tightening | 2 days | Restrict ingress to ingress-controller namespace, add egress policies |
| 34 | M13 — Log shipping | 3 days | Add Loki or S3 output to FluentBit config |
| 35 | M12 — Budget/cost alerts | 1 week | Wire `cutctx_savings` metrics into Prometheus alerts with threshold |

### Phase 4 — Enterprise Readiness (Weeks 11-16)

*Compliance, secrets management, platform completeness.*

| Priority | Finding | Effort | Action |
|---|---|---|---|
| 36 | H11 — External secret management | 2 weeks | Add ExternalSecret template for ESO, SealedSecret support, and Vault Agent sidecar pattern docs |
| 37 | H15 — Backup CronJob | 1 week | Create PVC, wire IRSA annotation, make bucket name configurable via values |
| 38 | L10 — Docker SBOM/provenance | 3 days | Add syft SBOM generation + cosign attestation to docker.yml |
| 39 | L9 — macOS x86_64 wheel | 1 week (if ORT available) | Re-evaluate ONNX Runtime prebuilt availability for x86_64-apple-darwin |
| 40 | L2 — Grafana dashboard | 2 days | Ship a Grafana dashboard JSON alongside the project (matching Prometheus metrics) |
| 41 | L4 — Panic hook | 1 day | Add `faulthandler.enable()` at proxy startup |
| 42 | L3 — Rust OTel bridge | 1 week | Add `tracing-opentelemetry` to Cargo.toml and wire to existing OTel exporter |

---

## Risk Heatmap

```
                    Effort
              Low    Medium   High    Very High
Imp. Critical  [C2,C3,C5]  [C1,C4,C7] [C6]    [C8.part2]
     High      [H1,H2,H4,  [H6,H7,H9,  [H8]    —
               H5,H14]     H10,H13]
     Medium    [M3,M4,M7,  [M10,M11,   [M1,M16] [C8.part2]
               M17]        M12,M14]
     Low       [L2,L4,     [L3,L9]     [L10]    —
               L12]
```

**Immediate wins (low effort, high impact):** C2, C3, C5, H1, H4, H5 — all under 2 hours, collectively fix 3 CRITICALs and 3 HIGHs.

---

## Verdict

**Score: 55/100 — conditional production-ready with remediation.**

The proxy core, compression pipeline, and CI/CD foundation are solid and well-engineered. The product is **not safe to deploy** in its current state because of 8 CRITICAL deployment and security issues. However, none of these are architectural problems — they are configuration gaps, missing manifests, and developer hygiene issues. With **2-3 weeks of focused remediation** (Phases 0+1), the score can reach **75/100**, which is production-viable for most use cases.

The most concerning long-term issue is the **Rust unwrap/panic count** and the **6,889-line server.py god file** — these represent structural reliability debt that will accumulate if not addressed. Every production incident will be harder to debug because of the silent `except: pass` blocks and lack of error tracking.

---

*Audit methodology: Static analysis of source code, configuration files, CI/CD workflows, Docker/K8s/Helm manifests, and documentation. No dynamic analysis or penetration testing was performed. The `.env.secret` Ed25519 key finding is based on file content analysis — verify whether it is a production key before acting on the recommendation.*
