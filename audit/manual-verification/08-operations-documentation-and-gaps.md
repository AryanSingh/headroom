# Enterprise, Operations, Documentation, and Gap Ledger

## Enterprise governance (execute only when EE artifact/configuration is enabled)

### EE-001 — Edition boundary and entitlement discovery

**Priority:** P0. **Actions:** install OSS-only and EE artifacts separately; invoke EE endpoints/CLI/UI/capabilities. **Expected:** OSS does not accidentally ship/load proprietary module; unavailable capability is explicit; EE enables only licensed entitlements. **Pass:** packaging and runtime boundaries match `LICENSING.md`/manifests.

### EE-002 — Tenant identity and isolation

**Priority:** P0. **Actions:** create/use tenant A/B data across proxy, memory, sessions, secrets, spend, audit, ledger; query with each identity and forged IDs/headers. **Expected:** strict tenant separation in data, metrics, exports and caches. **Pass:** no cross-tenant read/write/side-channel.

### EE-003 — RBAC, MFA, SSO/SCIM

**Priority:** P0. **Actions:** for viewer/operator/admin and unauthenticated user, execute every permissioned admin route/UI action; enroll/verify/remove MFA; use valid/invalid/expired JWT/JWKS/OIDC/introspection and SSO config; provision/deprovision via SCIM if present. **Expected:** least privilege, revocation immediate or documented, no role escalation. **Pass:** complete role × route/action matrix attached.

### EE-004 — Policy, firewall, airgap, residency, secrets

**Priority:** P0. **Actions:** create/sign/read policy; test allow/block; check airgap status/policy/check; set residency; CRUD test secrets then attempt unauthorized read/export. **Expected:** enforcement before egress, audit record, secret values never read back unless explicitly authorized. **Pass:** denied paths have no upstream side effect.

### EE-005 — Billing, license, entitlements, spend and ledger

**Priority:** P1. **Actions:** sandbox activate/validate license, seat checkout, trial start/check, Stripe webhook signature/replay/invalid signature, usage event/query/export/dashboard, spend limit. **Expected:** idempotency/signature validation, correct entitlement and usage aggregation, safe failure. **Pass:** no double charge/event or secret disclosure.

### EE-006 — Audit, retention, DSR and tamper evidence

**Priority:** P0. **Actions:** cause admin/data events; query/filter/export audit; verify tamper chain; set retention; export/delete a subject via DSR; restart. **Expected:** immutable/auditable event ordering, retention/DSR scope correct, export redacted/access controlled. **Pass:** evidence is verifiable and tenant-scoped.

### EE-007 — Enterprise orchestration/governance UI

**Priority:** P1. **Actions:** repeat relevant dashboard cases as each role/tenant; verify audit, licensing, spend, governance panels. **Pass:** UI cannot bypass API policy.

## Operations and delivery

### OPS-001 — Clean installation and first run

**Priority:** P0. **Actions:** on clean supported OS images install published wheel/pipx/npm/Docker paths from docs; run version/help, `cutctx setup`, a local compression, proxy startup and dashboard. **Expected:** only declared runtimes/dependencies required; correct version and no source checkout dependency. **Negative:** offline/corporate CA/no Rust/missing optional extra. **Pass:** every advertised install path is reproducible or documented as blocked.

### OPS-002 — Extras, runtime assets, and capability reporting

**Priority:** P1. **Actions:** install each advertised extra/bundle (`recommended`, `full`, ML, memory, image, MCP, OTEL, integrations, production); invoke feature and `capabilities`. **Expected:** asset download/offline/corporate CA/ORT/HF behavior has correct remediation; no false capability claim. **Pass:** manifest/doc matrix complete.

### OPS-003 — Docker/Compose/devcontainer deployment

**Priority:** P0. **Actions:** build/pull image; `docker compose up`; verify healthcheck, ports, volumes, env injection, shutdown/restart, memory-stack/devcontainer variants. **Expected:** containers are non-root/least privileged where documented, persistent data works, secrets not in image/log. **Negative:** unavailable dependency, wrong env, volume permission, image upgrade. **Cleanup:** `docker compose down` plus only named disposable volumes. **Pass:** documented compose instructions work verbatim.

### OPS-004 — Upgrade/rollback and migrations

**Priority:** P0. **Actions:** deploy prior supported version with seeded CCR/memory/config/audit; upgrade RC; run checks; rollback; repeat image and package upgrade. **Expected:** schema/config/data compatibility, explicit migration/backup requirement, no destructive silent migration. **Pass:** recovery plan is executable.

### OPS-020 — Configuration and secret management

**Priority:** P0. **Actions:** test every documented environment variable/config-file option and precedence; file permissions; rotation/revocation; invalid/missing values. **Expected:** effective config is observable without exposing secret; strict validation and safe defaults. **Pass:** config reference has a test row per key.

### OPS-021 — Logging, metrics, traces, alerts and redaction

**Priority:** P0. **Actions:** generate success/failure/auth/policy/routing/memory events; collect logs, Prometheus/OTel/Langfuse where enabled; force exporter outage. **Expected:** correlation, cardinality/redaction and retry/drop behavior match docs; dashboard matches. **Pass:** operators can diagnose P0 journeys without sensitive payload.

### OPS-022 — Backup, restore and disaster recovery claims

**Priority:** P1. **Actions:** use only documented backup/export mechanism for config, CCR, memory, audit/ledger; restore into clean staging; verify integrity/tenant separation. **Expected:** if no supported backup exists, record this explicitly as a documentation/product gap rather than inventing a procedure. **Pass:** every claimed recovery capability is demonstrated.

### OPS-023 — Capacity, limits, and shutdown

**Priority:** P1. **Actions:** load test within approved staging limit; test max body/token/concurrency/session/TTL/cache sizes, SIGTERM during requests, disk-full simulation where safe. **Expected:** bounded resource behavior and documented backpressure/errors. **Pass:** no data corruption/leak and limits are documented.

### OPS-024 — Security regression execution

**Priority:** P0. **Actions:** execute auth/RBAC/tenant/egress/redaction/secret/SSRF-like URL/input/CORS/CSRF/replay tests from all P0 cases. **Expected:** rejected access has no side effect; logs/audit record safe details. **Pass:** no Critical/High security finding remains unowned.

## Documentation verification matrix

For every file below, create a row containing: path, each command/config/endpoint/example/claim, exact linked test ID or new `DOC-*` ID, observed output, match (`Yes`/`No`/`Needs confirmation`), correction owner. Do not mark a document reviewed merely because it was read.

| Documentation area | Verification method |
|---|---|
| Root `README.md`, `PRODUCT_GUIDE.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, release notes, licensing/enterprise/deployment/billing/artifact docs | DOC-001: run every install/quickstart/compatibility/security/benchmark claim or label external/historical claim with evidence and date. |
| `docs/content/docs/*.mdx` — installation, Docker, quickstart, proxy, API, configuration, auth, errors, metrics, CCR, memory, cache, routing presets, orchestration, MCP, integrations, simulations, benchmarks, limitations, releases, SLA and all remaining pages | DOC-002–007: execute each code block and validate each config/env/endpoint against current public API; attach generated doc inventory. |
| `sdk/**/README*`, `sdks/**/README*`, examples | DOC-008: clean-install then compile/run each sample. |
| `plugins/**/README*`, plugin manifests, `extensions/**/README*` | DOC-009: host install/config/uninstall matrix. |
| Dockerfiles, Compose, devcontainer, manifests (`pyproject.toml`, Cargo/package/go modules) | DOC-010: reconcile stated versions/extras/scripts/files with artifact. |
| Test docs/fixture instructions and benchmark methodology | DOC-011: reproduce deterministic path; identify live credential/dataset prerequisite and historical-only claims. |
| API docs/OpenAPI/route reference | DOC-012: compare method/path/request/response/auth against mounted route inventory PX-035. |

## Gap ledger and release blockers

Record each item as: `Gap ID | capability/doc path | status (Blocked/Failed/Needs confirmation) | severity | why | exact missing prerequisite/owner | release decision | due date`. Mandatory initial entries:

| Gap ID | Initial status | Required resolution |
|---|---|---|
| GAP-001 | Needs confirmation | Attachment was truncated after “Service failure, recovery,”; this pack includes recovery/observability journey but original trailing wording is unavailable. Confirm no omitted requested bullet. |
| GAP-002 | Needs confirmation | Real upstream behavior, rate limits and billing require sandbox credentials for every enabled provider. |
| GAP-003 | Needs confirmation | OS/IDE/host matrix needs physical/VM validation; source inspection cannot prove keychain/secret-service integration. |
| GAP-004 | Needs confirmation | EE licensing/IdP/Stripe/retention paths require enterprise staging configuration. |
| GAP-005 | Needs confirmation | “Exhaustive” route/documentation sweep requires generated inventories at RC time because routes/docs can change after this plan. |

## Coverage conclusion

This plan covers every repository product area discovered from the root/nested maps, manifests, public entry points, dashboard routes, CLI registry, documentation catalog, route families, SDKs, plugins, IDE extensions, native components, and EE package. Complete execution coverage is conditional on generating the per-release route/doc/plugin inventory and on access to the listed external services. No unavailable credential, platform, or optional component may be counted as verified; it must remain in the gap ledger with a release-owner decision.
