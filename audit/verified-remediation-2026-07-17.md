# July 17 Audit: Independent Verification and Remediation

This note records an independent check of the actionable claims in
`full-product-commercial-audit-2026-07-17.md`. The original report remains
unchanged.

## Verdicts

| Claim | Verdict | Evidence and action |
|---|---|---|
| Package version drift blocks the release | Narrowed | The worktree contained `0.31.0` and `0.30.0` package metadata, but both release jobs run `scripts/version-sync.py` before `scripts/verify-versions.py`. The tagged release path would repair package drift before checking it. Deployment manifests and the `cutctx-py` entry in `Cargo.lock` were outside the complete invariant, so synchronization and verification now cover them. |
| Helm and Kubernetes metadata are stale | Confirmed | `helm/cutctx/Chart.yaml`, `helm/cutctx/values.yaml`, and `k8s/deployment.yaml` referenced `0.30.0`. They now use `0.31.0`. |
| CI ignores deployment-only changes | Confirmed | The `code` and `e2e` filters in `.github/workflows/ci.yml` omitted `helm/**` and `k8s/**`. Both filters now include those paths. |
| CCR creates a paid-feature revenue leak | Refuted as stated | `PRODUCT_GUIDE.md` lists memory and CCR in Builder and says the free tier includes CCR. Runtime defaults match that promise. `cutctx_ee/entitlements.py` contradicted both sources by labeling CCR as Team. The metadata now labels `ccr` and `ccr_marker` as Builder. Runtime defaults did not change. |
| Episodic memory is freely enabled by default | Refuted | `ProxyConfig.episodic_memory_enabled` defaults to `False`. The management API rejects Builder attempts to enable it. Direct startup configuration remains available, preserving current behavior. |
| ContentRouter can expand a payload | Confirmed, impact narrowed | A repeated mixed prose and fenced-code input expanded from 8,000 to 8,198 UTF-8 bytes through direct `ContentRouter.compress()`. The public `cutctx.compress()` API already reverted inflated results. `ContentRouter` now enforces the same byte invariant for direct callers. |
| Managed RTK is stale | Confirmed | The repository pinned `v0.28.2`; the upstream GitHub release API reports `v0.43.0` as the latest release published on 2026-06-28. The managed pin and all five target checksums now match that release. System RTK installations remain preferred and a mismatch produces a warning, not rejection. |
| Audit CLI filters use unsafe query concatenation | Confirmed | `cutctx/cli/audit.py` interpolated `action` and `actor` into URLs. The CLI now passes `params=` dictionaries, so strings such as `org.created&limit=9999` remain one filter value. |
| Request-level traces and a forensics view do not exist | Refuted | `cutctx/proxy/server.py` exposes `/transformations/traces/{request_id}` and returns routing, compression, attribution, latency, cache, cost, fallback, tags, and optional message payloads. `dashboard/src/pages/Overview.jsx` implements `RequestTraceInspector`. |
| Enterprise docs claim completed SOC 2 or HIPAA certification | Refuted | `ENTERPRISE.md`, `PRODUCT_GUIDE.md`, `docs/security-and-privacy.md`, and `docs/security/VENDOR_SECURITY_QUESTIONNAIRE.md` state that formal certification is incomplete or requires external work. |
| No tier comparison exists | Refuted | `ENTERPRISE.md` contains a commercial tier table and `PRODUCT_GUIDE.md` contains pricing plus per-tier feature lists. Publication and sales usability remain product questions, not missing repository content. |

## Reproduction and verification commands

```bash
rtk proxy .venv/bin/python scripts/verify-versions.py
rtk proxy .venv/bin/pytest scripts/tests/test_version_sync.py scripts/tests/test_verify_versions.py -q
rtk proxy .venv/bin/pytest tests/test_release_workflows.py -q
rtk proxy .venv/bin/pytest tests/test_transforms_content_router.py tests/test_compression_safety_rails.py -q
rtk proxy .venv/bin/pytest tests/test_rtk_installer.py tests/test_cli_audit.py -q
rtk proxy .venv/bin/pytest tests/test_entitlements.py tests/test_entitlement_boundaries.py tests/test_management_api_entitlements.py -q
```

The RTK release tag and asset digests came from:

```bash
rtk gh api repos/rtk-ai/rtk/releases/tags/v0.43.0 \
  --jq '.assets[] | {name,digest}'
```

## Behavior preserved

- CCR injection, response handling, and context tracking remain enabled by default.
- Episodic memory remains disabled by default.
- Provider request handlers do not gain new entitlement denials.
- A system-installed RTK binary remains preferred over the managed download.
