# Licensing

Headroom uses an **open-core** licensing model. This file is the **authoritative map** of which parts of the repository are open source and which are proprietary. Where this file conflicts with a stray header or badge, **this file controls**.

> ⚠️ **Legal entity TODO.** The proprietary license names "Headroom Labs" as the copyright holder/licensor, taken from existing repo metadata. Replace it with your actual incorporated entity (e.g. Payzli / the Headroom operating company) in `LICENSE-COMMERCIAL`, `NOTICE`, and the SPDX headers before distributing. **Have counsel review `LICENSE-COMMERCIAL` — it is a template, not legal advice.**

---

## The two licenses

| License | File | Applies to |
|---------|------|------------|
| **Apache License 2.0** (open source) | [`LICENSE`](LICENSE) | The **client**: compression engine, proxy, SDKs, CLI, MCP server, base model, integrations. Adoption surface — stays free and open. |
| **Headroom Commercial License** (proprietary, All Rights Reserved) | [`LICENSE-COMMERCIAL`](LICENSE-COMMERCIAL) | The **commercial core**: control plane, licensing/billing, enterprise admin, the data-flywheel intelligence layer, agent-tuned models. The moat — closed. |

**Default rule:** a path is Apache-2.0 **unless** it is listed as a Commercial Component below (or carries an SPDX `LicenseRef-Headroom-Commercial` header).

SPDX identifiers:
- Open: `Apache-2.0`
- Commercial: `LicenseRef-Headroom-Commercial`

---

## Open-source components (Apache-2.0)

These remain Apache-2.0 to preserve adoption and the inbound traffic the data flywheel depends on:

- `crates/headroom-core/**` — compression engine and algorithms (the client engine)
- `crates/headroom-proxy/**` — the proxy (minus the commercial enforcement hooks listed below)
- `crates/headroom-py/**`, `crates/headroom-parity/**`
- `sdk/**` — Python/TypeScript SDKs
- `headroom/cli/**`, `headroom/mcp_server.py`, `headroom/compress.py`, `headroom/pipeline.py`
- `headroom/ccr/**` — reversible-compression mechanism
- `headroom/proxy/**` (compression/memory injection client glue), `headroom/providers/**`, `headroom/integrations/**`, `headroom/transforms/**`, `headroom/compression/**`, `headroom/cache/**`, `headroom/tokenizer*`, `headroom/relevance/**`
- `plugins/**`, `docs/**`, `examples/**`
- The **base** model `kompress-v2-base` (as published)

---

## Commercial components (proprietary — LICENSE-COMMERCIAL)

### A. Relocated to the `headroom_ee/` package (done)
These were moved out of the Apache `headroom/` package into the proprietary
`headroom_ee/` package (each file carries the `LicenseRef-Headroom-Commercial`
SPDX header). Thin **Apache-2.0 import shims** remain at the historical
`headroom/<name>` paths and transparently re-export the commercial implementation
(via `sys.modules` rebinding) when the `headroom_ee` distribution is installed:
- `headroom_ee/billing/**` — license issuance/DB, Stripe webhook (shim: `headroom/billing/`)
- `headroom_ee/entitlements.py` — feature gating by tier (shim: `headroom/entitlements.py`)
- `headroom_ee/trial.py`, `headroom_ee/seats.py` — trial & seat enforcement (shims at old paths)
- `headroom_ee/sso.py`, `headroom_ee/scim.py`, `headroom_ee/rbac.py` — enterprise identity/access
- `headroom_ee/audit.py`, `headroom_ee/retention.py` — enterprise audit & retention
- `headroom_ee/org.py` — multi-tenant org/workspace/project store (control-plane tenancy)
- `artifacts/openapi-management.yaml` — the Management/Control-Plane API spec

The OSS wheel excludes `headroom_ee/` (see `[tool.maturin] exclude` in `pyproject.toml`);
the commercial distribution is built from `packaging/headroom-ee/pyproject.toml`.

### B. Planned by the moat program (born proprietary as they land)
See [`MOAT/`](MOAT/INDEX.md). These paths are Commercial Components the moment they are created:
- `services/control-plane/**` — license/seat/trial/spend/policy/audit service (MOAT C)
- `services/insight/**` — telemetry corpus + training data aggregation (MOAT A7)
- `services/memory/**` — team memory server of record (MOAT B1)
- `headroom/training/**` — label builder, trainers, eval-gated rollout (MOAT A3–A6)
- `headroom/memory/value.py`, `headroom/memory/curation.py` — the memory **intelligence layer** (value model, curation, dedup/promotion graph)
- `crates/headroom-core/src/signals/learned_scorer.rs` — loader for proprietary keep/drop models
- `crates/headroom-proxy/src/{license/**,policy/**,routing/spend_router.rs,routing/failover.rs,observability/spend_emitter.rs}` — commercial enforcement & control-plane hooks
- All **agent-tuned models** and artifacts (`kompress-agent-*`), the labeled **training corpus**, and any aggregated derived datasets

> Note: the open proxy/core crates may contain small **interface hooks** that call into commercial components at runtime. The hooks (trait definitions, no-op stubs, config plumbing) are Apache-2.0; the commercial implementations behind them are not.

---

## Important legal realities (read before relying on this)

1. **The Apache grant on already-published versions is irrevocable.** Every release shipped under Apache-2.0 — PyPI, npm, crates.io, the HuggingFace model, and every public Git tag through v0.25.0 — remains Apache-2.0 **forever**. Anyone may fork the last Apache-licensed release. This relicensing only binds **future** versions and **newly added** Commercial Components.
2. **You must own or control the copyright to relicense.** Existing `NOTICE`/headers attribute "Headroom Contributors." To enforce the commercial license you need to have authored the relicensed code yourself, or have a Contributor License Agreement (CLA) / assignment from every outside contributor. Audit contributors before relying on this.
3. **Single-package caveat (action required).** Today the proprietary modules in section A physically live inside the same `headroom/` Python package that is published to PyPI under Apache-2.0. Shipping proprietary files inside an Apache-licensed distribution is inconsistent. Before the next public release you must **separate the commercial code** (see "Required next step").
4. **Not legal advice.** This document and `LICENSE-COMMERCIAL` are engineering templates. Have qualified counsel review the license text, the entity name, the jurisdiction, and the contributor situation.

---

## Required next step — package separation

To make the boundary airtight (and avoid shipping proprietary code in the Apache PyPI/npm packages), separate the Commercial Components into their own distribution:

- Move section-A modules into an `ee/` tree or a separate `headroom-commercial` / `headroom-ee` Python package (and a separate service image for `services/**`).
- The open `headroom-ai` / `cutctx-ai` package depends on stable **interfaces**; commercial implementations are loaded only when the commercial package + a valid entitlement (MOAT C1) are present.
- Public OSS artifacts (PyPI, npm, crates.io) contain **only** Apache-2.0 code.

This refactor touches imports, packaging, and tests, so it is intentionally **not** done automatically. It is specced to be handed to an agent as a follow-up (`relicense-split` branch).

---

## Contributing

External contributions to **open-source components** are accepted under Apache-2.0 inbound=outbound. Contributions to **Commercial Components** require a signed CLA assigning rights to the Licensor. See `CONTRIBUTING.md`.
