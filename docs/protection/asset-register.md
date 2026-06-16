# CutCtx — Asset Register (Ship vs Serve)

**Purpose:** Classify every valuable asset as "ship" (delivered to customer) or "serve" (kept server-side). This is SP-0 — the highest-leverage protection control.

**Date:** 2026-06-16
**Audience:** Engineering, Legal, Product

---

## Asset Classification

| Asset | Decision | Location | Rationale |
|---|---|---|---|
| **SmartCrusher compression** | Ship (OSS) | `crates/headroom-core/src/transforms/smart_crusher/` | Open-core; drives adoption |
| **CodeCompressor (AST)** | Ship (OSS) | `crates/headroom-core/src/transforms/` | Open-core |
| **Diff/Log/Search Compressors** | Ship (OSS) | `crates/headroom-core/src/transforms/` | Open-core |
| **CacheAligner** | Ship (OSS) | `crates/headroom-core/src/transforms/` | Open-core |
| **CCR (Cache-Control Reversibility)** | Ship (OSS) | `crates/headroom-core/src/ccr/` | Open-core |
| **Live-zone engine** | Ship (OSS core) | `crates/headroom-core/src/transforms/live_zone.rs` | Core algorithm is OSS |
| **Rust proxy binary** | Ship (OSS) | `crates/headroom-proxy/` | Open-core |
| **Python proxy** | Ship (OSS) | `headroom/proxy/` | Open-core |
| **Go SDK** | Ship (OSS) | `sdk/go/` | Open-core |
| **Python SDK** | Ship (OSS) | `sdk/python/` | Open-core |
| **Base tokenizer** | Ship (OSS) | `crates/headroom-core/src/tokenizer/` | Open-core |
| **CLI** | Ship (OSS) | `headroom/cli/` | Open-core |
| **MCP server** | Ship (OSS) | `headroom/mcp_server.py` | Open-core |
| **Plugins** | Ship (OSS) | `plugins/` | Open-core |
| **K8s/Helm manifests** | Ship (OSS) | `k8s/`, `helm/` | Open-core |
| | | | |
| **Enterprise audit system** | Ship (EE) | `headroom_ee/audit.py` | Licensed only |
| **Enterprise RBAC** | Ship (EE) | `headroom_ee/rbac.py` | Licensed only |
| **Enterprise SSO** | Ship (EE) | `headroom_ee/sso.py` | Licensed only |
| **Enterprise org model** | Ship (EE) | `headroom_ee/org.py` | Licensed only |
| **Enterprise SCIM** | Ship (EE) | `headroom_ee/scim.py` | Licensed only |
| **Enterprise seats** | Ship (EE) | `headroom_ee/seats.py` | Licensed only |
| **Enterprise retention** | Ship (EE) | `headroom_ee/retention.py` | Licensed only |
| **Enterprise entitlements** | Ship (EE) | `headroom_ee/entitlements.py` | Licensed only |
| **Enterprise trial** | Ship (EE) | `headroom_ee/trial.py` | Licensed only |
| **Enterprise policy** | Ship (EE) | `headroom_ee/policy/` | Licensed only |
| **Enterprise billing** | Ship (EE) | `headroom_ee/billing/` | Licensed only |
| | | | |
| **License truth (validity, seats, revocation)** | **Serve** | License API server | Client only caches signed lease |
| **Agent-tuned models (kompress-agent-*)** | **Serve** | `headroom_ee/insight/` | Never ship weights |
| **Insight corpus** | **Serve** | Server-side only | Never ship to customers |
| **Spend/policy engine** | **Serve** | Control plane | Server-side |
| **Abuse detection** | **Serve** | `headroom_ee/abuse/` | Server-side analysis |
| **Watermark verification** | **Serve** | License API server | Client embeds; server verifies |
| **CRL (Certificate Revocation List)** | **Serve** | License API server | Client caches with grace |

---

## Verification Script

Run `python3 scripts/assert_no_model_weights.py` to verify:
1. No `.onnx`, `.pt`, `.bin` (model weights) in any shipped artifact
2. No `headroom_ee` source in OSS wheel
3. No server-only secrets in shipped artifacts

---

## Acceptance Criteria

- [ ] Every "Serve" asset is absent from all shipped artifacts (wheel, Docker image, binary)
- [ ] Every "Ship (EE)" asset is present only in the EE wheel, never in the OSS wheel
- [ ] Agent-tuned model weights are not in any file in the repository
- [ ] Verification script passes in CI on every release
