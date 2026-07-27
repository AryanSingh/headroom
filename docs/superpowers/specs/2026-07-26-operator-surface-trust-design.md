# Operator Surface Trust — Orchestrator / Capabilities / Governance

**Date:** 2026-07-26  
**Status:** Implemented  
**Scope:** Make dashboard operator surfaces trustworthy against live proxy/CLI data.

## Problem

Verification against a production LaunchAgent proxy (`:8787`) found four trust gaps:

1. **License not applied at runtime** — `cutctx license activate` wrote `~/.cutctx/license_key.txt` and CLI status reported enterprise, but the proxy stayed on `builder` because LaunchAgent omitted `CUTCTX_LICENSE_KEY`. Audit/RBAC returned 403.
2. **/stats contract gap** — `config.rate_limiter` / `config.cache` booleans were published, but top-level live metric objects were missing, so Capabilities/Governance cards looked idle.
3. **Misleading zeros** — Capabilities preferred session counters that reset to 0 while lifetime `savings_by_source` / `opportunity_funnel` held real evidence.
4. **Policies CLI crash** — `cutctx policies show` called `init_db()` (write path) against an existing DB and failed with `readonly database`.

## Design principles

1. **One license resolution path** — config → `CUTCTX_LICENSE_KEY` → `~/.cutctx/license_key.txt` → activated `license_cache.json` (`effective_license_key`). Operators must not need to duplicate secrets into LaunchAgent plists.
2. **/stats is the operator contract** — if a feature is enabled and initialized, its live metrics object is present (even at zero). If disabled, the key is `null` and `config.*` explains why.
3. **Dashboard cards prefer truth over drama** — when the session window is empty, fall back to lifetime/persistent signals and label the window.
4. **Read paths must not require write** — inspect CLIs succeed on locked existing DBs.

## License resolution

```text
ProxyConfig.license_key
  → CUTCTX_LICENSE_KEY
  → ~/.cutctx/license_key.txt
  → license_cache.json payload.license_key
```

- CLI (`cutctx proxy`) resolves via `effective_license_key` before constructing `ProxyConfig`.
- `CutctxProxy.__init__` re-resolves so LaunchAgent / non-CLI starts also pick up activated keys.
- After `UsageReporter.validate_license()`, `_apply_validated_license` remains the single entitlement sync.
- Offline / cloud-unreachable path: `UsageReporter` must read the CLI activation cache shape
  (`write_hmac_json` → `{"payload": {...}}` with HTTP-date `validated_at`) and only apply
  entitlements when cached status is `active` or `trial`.

## `/stats` live-component contract

| Key | When enabled + initialized | When disabled |
|---|---|---|
| `config.rate_limiter` | `true` | `false` |
| `rate_limiter` | object (`active_keys`, `tokens_per_minute`, …) | `null` |
| `config.cache` | `true` | `false` |
| `cache` | object (`entries`, `total_hits`, `total_misses`, `tokens_avoided`, …) | `null` |

Capabilities and Governance read these top-level objects for live cards.

## Dashboard session vs lifetime rule

- Prefer `Math.max(session, lifetime)` for compression and provider-cache tokens.
- Lifetime sources: `savings_by_source`, `opportunity_funnel`, persistent savings.
- Footnotes must say **lifetime** when the session window contributed nothing.
- Governance routing-mode row must not invent `Off` when stats are unavailable (`null` / loading instead).
- Governance 403 surfaces must render required vs current tier from `detail`.

## Policies CLI read-safe open

- Mutating commands (`train`, `reset`, `evict-unsafe`) keep `init_db()` (writable).
- `load_policies` / `show` use `open_policies_db(..., writable=False)` and open existing DBs read-only, skipping schema stamp when the file is not writable.

## Verification checklist

```bash
# License / entitlements
cutctx license status
curl -H "x-cutctx-admin-key: $CUTCTX_ADMIN_API_KEY" http://127.0.0.1:8787/entitlements
# expect current_tier matching activated plan; audit_logs/rbac available on enterprise

curl -H "x-cutctx-admin-key: $CUTCTX_ADMIN_API_KEY" 'http://127.0.0.1:8787/audit/events?limit=2'
curl -H "x-cutctx-admin-key: $CUTCTX_ADMIN_API_KEY" http://127.0.0.1:8787/rbac/roles

# Live metrics
curl -H "x-cutctx-admin-key: $CUTCTX_ADMIN_API_KEY" 'http://127.0.0.1:8787/stats?cached=1' \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["config"], bool(d.get("rate_limiter")), bool(d.get("cache")))'

# Policies inspect
cutctx policies show

# Routing
cutctx routing status
```

Dashboard: open `/dashboard/orchestrator`, `/dashboard/capabilities`, `/dashboard/governance` with a valid admin key and confirm no false Off / idle / zero claims against lifetime evidence.

## Live proxy pickup

`com.cutctx.proxy` runs with WorkingDirectory `$HOME` and loads cutctx from
`~/.cutctx-proxy-venv` (non-editable snapshot). Editing the headroom repo alone
does not change `:8787` until the package is reinstalled into that venv
(`cutctx-promote`, or `pip install --force-reinstall '.[proxy]'` from the repo
into the venv) and the LaunchAgent is restarted. Do not rely on editable
imports: LaunchAgent cwd is not the repo root.

## Out of scope

- Forcing `cutctx mcp install` into Claude Desktop
- Changing global LaunchAgent GUI env inheritance for `OPENAI_BASE_URL` / `ANTHROPIC_BASE_URL`
