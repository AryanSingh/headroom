# Cutctx — Asset Register (Ship vs Serve)

**Purpose:** Classify every valuable asset as "ship" (delivered to customer) or "serve" (kept server-side). This is SP-0 — the highest-leverage protection control.

**Date:** 2026-06-16
**Audience:** Engineering, Legal, Product

---

## Asset Classification

| Asset | Decision | Location | Rationale |
|---|---|---|---|
| **SmartCrusher compression** | Ship (OSS) | `crates/cutctx-core/src/transforms/smart_crusher/` | Open-core; drives adoption |
| **CodeCompressor (AST)** | Ship (OSS) | `crates/cutctx-core/src/transforms/` | Open-core |
| **Diff/Log/Search Compressors** | Ship (OSS) | `crates/cutctx-core/src/transforms/` | Open-core |
| **CacheAligner** | Ship (OSS) | `crates/cutctx-core/src/transforms/` | Open-core |
| **CCR (Cache-Control Reversibility)** | Ship (OSS) | `crates/cutctx-core/src/ccr/` | Open-core |
| **Live-zone engine** | Ship (OSS core) | `crates/cutctx-core/src/transforms/live_zone.rs` | Core algorithm is OSS |
| **Rust proxy binary** | Ship (OSS) | `crates/cutctx-proxy/` | Open-core |
| **Python proxy** | Ship (OSS) | `cutctx/proxy/` | Open-core |
| **Go SDK** | Ship (OSS) | `sdk/go/` | Open-core |
| **Python SDK** | Ship (OSS) | `sdk/python/` | Open-core |
| **Base tokenizer** | Ship (OSS) | `crates/cutctx-core/src/tokenizer/` | Open-core |
| **CLI** | Ship (OSS) | `cutctx/cli/` | Open-core |
| **MCP server** | Ship (OSS) | `cutctx/mcp_server.py` | Open-core |
| **Plugins** | Ship (OSS) | `plugins/` | Open-core |
| **K8s/Helm manifests** | Ship (OSS) | `k8s/`, `helm/` | Open-core |
| | | | |
| **Enterprise audit system** | Ship (EE) | `cutctx_ee/audit.py` | Licensed only |
| **Enterprise RBAC** | Ship (EE) | `cutctx_ee/rbac.py` | Licensed only |
| **Enterprise SSO** | Ship (EE) | `cutctx_ee/sso.py` | Licensed only |
| **Enterprise org model** | Ship (EE) | `cutctx_ee/org.py` | Licensed only |
| **Enterprise SCIM** | Ship (EE) | `cutctx_ee/scim.py` | Licensed only |
| **Enterprise seats** | Ship (EE) | `cutctx_ee/seats.py` | Licensed only |
| **Enterprise retention** | Ship (EE) | `cutctx_ee/retention.py` | Licensed only |
| **Enterprise entitlements** | Ship (EE) | `cutctx_ee/entitlements.py` | Licensed only |
| **Enterprise trial** | Ship (EE) | `cutctx_ee/trial.py` | Licensed only |
| **Enterprise policy** | Ship (EE) | `cutctx_ee/policy/` | Licensed only |
| **Enterprise billing** | Ship (EE) | `cutctx_ee/billing/` | Licensed only |
| | | | |
| **License truth (validity, seats, revocation)** | **Serve** | License API server | Client only caches signed lease |
| **Agent-tuned models (kompress-agent-*)** | **Serve** | `cutctx_ee/insight/` | Never ship weights |
| **Insight corpus** | **Serve** | Server-side only | Never ship to customers |
| **Spend/policy engine** | **Serve** | Control plane | Server-side |
| **Abuse detection** | **Serve** | `cutctx_ee/abuse/` | Server-side analysis |
| **Watermark verification** | **Serve** | License API server | Client embeds; server verifies |
| **CRL (Certificate Revocation List)** | **Serve** | License API server | Client caches with grace |

---

## Verification Script

Run `python3 scripts/assert_no_model_weights.py` to verify:
1. No `.onnx`, `.pt`, `.bin` (model weights) in any shipped artifact
2. No `cutctx_ee` source in OSS wheel
3. No server-only secrets in shipped artifacts

---

## Acceptance Criteria

- [ ] Every "Serve" asset is absent from all shipped artifacts (wheel, Docker image, binary)
- [ ] Every "Ship (EE)" asset is present only in the EE wheel, never in the OSS wheel
- [ ] Agent-tuned model weights are not in any file in the repository
- [ ] Verification script passes in CI on every release
