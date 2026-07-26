# Verification of Release-Audit Claims — 2026-07-22

## Scope and method

This is an independent verification of the two newly added audit documents:
`audit/release-audit.md` and `audit/licensing-enforcement-verification.md`.
Claims were checked against the current source, focused regression tests, and
the documented default deployment configuration. The release audit itself is
not treated as evidence.

## Verified licensing evidence

The licensing-focused command from the verification note passes with **74
tests**, not the 51 reported in that document. The implementation and focused
tests cover entitlement request handling, management APIs, local license
validation, seat leases, billing clients, and signed user tokens.

## Release-audit claim review

| Claim | Result | Evidence |
| --- | --- | --- |
| `learn_share` is a public CLI command that crashes | Refuted | There is no `learn_share` command. `cutctx learn --apply` imports a local Twitter-intent helper. `CUTCTX_LEARN_SHARE=1` on `--aggregate` deliberately fails with an explicit no-egress message, covered by `tests/test_cli_learn.py`. |
| Memory sync is entirely stubbed | Refuted | The `...` methods are the abstract `AgentMemoryAdapter` interface. `sync`, `sync_import`, `sync_export`, and team sync are implemented below it; `tests/test_memory_sync.py` passes. |
| `MemoryBackend` methods are missing implementations | Refuted | The cited bodies are a `typing.Protocol`, not a concrete runtime backend. |
| LangChain retriever is stubbed | Refuted | The cited exceptions belong to fallback base classes when LangChain is absent. `CutctxDocumentCompressor.compress_documents` is implemented. |
| SmartCrusher `rotate_window` is unimplemented | Refuted | No `rotate_window` implementation exists at the cited location. The exception rejects unsupported custom `relevance_config`/`scorer` overrides to avoid silently changing caller behavior. |
| DSR audit/spend deletion is unshipped | Refuted | DSR cascade and endpoint coverage exists in `tests/test_dsr_cascade_e2e.py` and `tests/test_dsr_endpoints.py`; audit deletion has a deliberate DSR carve-out. |
| Python proxy lacks health checks or container health checks | Refuted | The proxy exposes `/health` and `/readyz`; Docker, Compose, Kubernetes, and CI use `/readyz`. |
| `SECURITY.md` has a stale fork URL | Refuted | Its advisory link matches the configured `AryanSingh/headroom` origin. |
| Provider routes are unauthenticated by default | Qualified and remediated | The default bind is loopback, where zero-config local use is intentional. Before this verification, an explicitly non-loopback bind could also start without a provider-route key. It now fails closed until `CUTCTX_PROXY_API_KEY` is configured. |

## Changes made

1. Provider HTTP and WebSocket routes now require a configured
   `CUTCTX_PROXY_API_KEY` whenever the proxy is bound to a non-loopback host.
   The default loopback developer flow is unchanged.
2. The proxy deployment documentation now describes the required key and TLS
   boundary for network exposure.
3. The licensing verification note’s stale test count is corrected from 51 to
   74.

## Evidence run

```sh
pytest -q \
  tests/test_entitlement_request_path.py \
  tests/test_management_api_entitlements.py \
  tests/test_license_validation_contract.py \
  cutctx_ee/tests/test_license_e2e.py \
  cutctx_ee/tests/test_license_db.py \
  cutctx_ee/tests/test_billing_client.py \
  cutctx_ee/tests/test_pitchtoship_client.py \
  cutctx_ee/tests/test_seat_lease.py \
  cutctx_ee/tests/test_user_tokens.py \
  tests/test_memory_sync.py \
  tests/test_capability_extensions.py \
  tests/test_dsr_endpoints.py \
  tests/test_dsr_cascade_e2e.py \
  tests/test_proxy_client_auth.py \
  tests/test_agent_client_auth.py \
  tests/test_cross_harness_client_auth_e2e.py \
  tests/test_cli_learn.py
```

The release audit contains additional product, legal, operational, benchmark,
and accessibility assertions that were not independently verified in this
pass. They should remain hypotheses until each has comparable code, test, or
external evidence.
