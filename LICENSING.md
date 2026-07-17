# Licensing

Cutctx uses an **open-core** licensing model. This file is the **authoritative map** of which parts of the repository are open source and which are proprietary. Where this file conflicts with a stray header or badge, **this file controls**.

> ℹ️ **Commercial entity status.** The commercial license now names `Payzli Inc. (operating as Cutctx Labs)` as the Licensor in `LICENSE-COMMERCIAL`. Keep that same entity string synchronized anywhere the proprietary distribution identifies its owner, including `packaging/cutctx-ee/pyproject.toml` and commercial SPDX headers. If the operating entity changes, update those references before distribution and have counsel re-review the license text.

---

## The two licenses

| License | File | Applies to |
|---------|------|------------|
| **Apache License 2.0** (open source) | [`LICENSE`](LICENSE) | The **client**: compression engine, proxy, SDKs, CLI, MCP server, base model, integrations. Adoption surface — stays free and open. |
| **Cutctx Commercial License** (proprietary, All Rights Reserved) | [`LICENSE-COMMERCIAL`](LICENSE-COMMERCIAL) | The **commercial core**: control plane, licensing/billing, enterprise admin, the data-flywheel intelligence layer, agent-tuned models. The moat — closed. |

**Default rule:** a path is Apache-2.0 **unless** it is listed as a Commercial Component below (or carries an SPDX `LicenseRef-Cutctx-Commercial` header).

SPDX identifiers:
- Open: `Apache-2.0`
- Commercial: `LicenseRef-Cutctx-Commercial`

---

## Open-source components (Apache-2.0)

These remain Apache-2.0 to preserve adoption and the inbound traffic the data flywheel depends on:

- `crates/cutctx-core/**` — compression engine and algorithms (the client engine)
- `crates/cutctx-proxy/**` — the proxy (minus the commercial enforcement hooks listed below)
- `crates/cutctx-py/**`, `crates/cutctx-parity/**`
- `sdk/**` — Python/TypeScript SDKs
- `cutctx/cli/**`, `cutctx/mcp_server.py`, `cutctx/compress.py`, `cutctx/pipeline.py`
- `cutctx/ccr/**` — reversible-compression mechanism
- `cutctx/proxy/**` (compression/memory injection client glue), `cutctx/providers/**`, `cutctx/integrations/**`, `cutctx/transforms/**`, `cutctx/compression/**`, `cutctx/cache/**`, `cutctx/tokenizer*`, `cutctx/relevance/**`
- `plugins/**`, `docs/**`, `examples/**`
- The **base** model `kompress-v2-base` (as published)

---

## Commercial components (proprietary — LICENSE-COMMERCIAL)

### A. Relocated to the `cutctx_ee/` package (done)
These were moved out of the Apache `cutctx/` package into the proprietary
`cutctx_ee/` package (each file carries the `LicenseRef-Cutctx-Commercial`
SPDX header). Thin **Apache-2.0 import shims** remain at the historical
`cutctx/<name>` paths and transparently re-export the commercial implementation
(via `sys.modules` rebinding) when the `cutctx_ee` distribution is installed:
- `cutctx_ee/billing/**` — license issuance/DB and hosted PitchToShip integration (shim: `cutctx/billing/`); the legacy Stripe webhook is enterprise compatibility only
- `cutctx_ee/entitlements.py` — feature gating by tier (shim: `cutctx/entitlements.py`)
- `cutctx_ee/trial.py`, `cutctx_ee/seats.py` — trial & seat enforcement (shims at old paths)
- `cutctx_ee/sso.py`, `cutctx_ee/scim.py`, `cutctx_ee/rbac.py` — enterprise identity/access
- `cutctx_ee/audit.py`, `cutctx_ee/retention.py` — enterprise audit & retention
- `cutctx_ee/org.py` — multi-tenant org/workspace/project store (control-plane tenancy)
- `artifacts/openapi-management.yaml` — the Management/Control-Plane API spec

The OSS wheel excludes `cutctx_ee/` (see `[tool.maturin] exclude` in `pyproject.toml`);
the commercial distribution is built from `packaging/cutctx-ee/pyproject.toml`.

### B. Planned by the moat program (born proprietary as they land)
See [`MOAT/`](MOAT/INDEX.md). These paths are Commercial Components the moment they are created:
- `services/control-plane/**` — license/seat/trial/spend/policy/audit service (MOAT C)
- `services/insight/**` — telemetry corpus + training data aggregation (MOAT A7)
- `services/memory/**` — team memory server of record (MOAT B1)
- `cutctx/training/**` — label builder, trainers, eval-gated rollout (MOAT A3–A6)
- `cutctx/memory/value.py`, `cutctx/memory/curation.py` — the memory **intelligence layer** (value model, curation, dedup/promotion graph)
- `crates/cutctx-core/src/signals/learned_scorer.rs` — loader for proprietary keep/drop models
- `crates/cutctx-proxy/src/{license/**,policy/**,routing/spend_router.rs,routing/failover.rs,observability/spend_emitter.rs}` — commercial enforcement & control-plane hooks
- All **agent-tuned models** and artifacts (`kompress-agent-*`), the labeled **training corpus**, and any aggregated derived datasets

> Note: the open proxy/core crates may contain small **interface hooks** that call into commercial components at runtime. The hooks (trait definitions, no-op stubs, config plumbing) are Apache-2.0; the commercial implementations behind them are not.

---

## Important legal realities (read before relying on this)

1. **The Apache grant on already-published versions is irrevocable.** Every release shipped under Apache-2.0 — PyPI, npm, crates.io, the HuggingFace model, and every public Git tag through v0.25.0 — remains Apache-2.0 **forever**. Anyone may fork the last Apache-licensed release. This relicensing only binds **future** versions and **newly added** Commercial Components.
2. **You must own or control the copyright to relicense.** Existing `NOTICE`/headers attribute "Cutctx Contributors." To enforce the commercial license you need to have authored the relicensed code yourself, or have a Contributor License Agreement (CLA) / assignment from every outside contributor. Audit contributors before relying on this.
3. **Distribution boundary status.** The proprietary implementation now lives under the separate `cutctx_ee/` package and the commercial distribution is built from `packaging/cutctx-ee/pyproject.toml`. The Apache OSS wheel excludes `cutctx_ee/**/*` and `packaging/**/*` via `[tool.maturin] exclude`, so public artifacts do not ship proprietary files. The source tree still contains both packages side by side for development, which is expected in this workspace layout.
4. **Not legal advice.** This document and `LICENSE-COMMERCIAL` are engineering templates. Have qualified counsel review the license text, the entity name, the jurisdiction, and the contributor situation.

---

## Packaging guardrails

To keep the boundary airtight (and avoid regressions that accidentally re-mix proprietary code into Apache artifacts), preserve the current split distribution model:

- Keep section-A modules in `cutctx_ee/` and ship them only via the separate `cutctx-ee` distribution (and separate service images for `services/**` as they land).
- Keep the open `cutctx-ai` / `cutctx-ai` package depending only on stable **interfaces**; commercial implementations should load only when the commercial package + a valid entitlement (MOAT C1) are present.
- Continue verifying that public OSS artifacts (PyPI, npm, crates.io) contain **only** Apache-2.0 code.

Any future refactor that touches imports, packaging, or release automation should be checked against these guardrails before publication.

---

## Contributing

External contributions to **open-source components** are accepted under Apache-2.0 inbound=outbound. Contributions to **Commercial Components** require a signed CLA assigning rights to the Licensor. See `CONTRIBUTING.md`.
