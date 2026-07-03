# Design-Partner Demo Script

End-to-end walkthrough showing Cutctx as a context control plane for design
partners. Estimated time: 30 minutes.

## Prerequisites

- Cutctx installed from the local checkout or package.
- Admin key configured as `CUTCTX_ADMIN_KEY`.
- Target provider/model API key configured for the proxy backend.
- Dashboard assets rebuilt after frontend changes: `make build-dashboard`.

## Step 1: Start Proxy

```bash
cutctx proxy \
  --enable-learned-policies \
  --port 8080
```

Look for:

- Proxy starts cleanly.
- Dashboard reachable at `http://localhost:8080`.
- `/stats` returns `intelligence.policies.enabled: false` before training.

## Step 2: Show Compression Visibility

Open dashboard Overview at `http://localhost:8080`.

Look for:

- Savings-source panel explains direct compression, provider cache, and
  semantic-cache attribution.
- Compression autopilot panel shows WS19 status when enabled.
- Learned-policies panel shows disabled/empty-state guidance before training.
- Recent requests populate once traffic flows through proxy.

## Step 3: Train Learned Policies

Create sample outcome events:

```bash
cat > /tmp/events.jsonl <<'EOF'
{"tool_name":"grep","content_type":"tool_output","repo":"demo","original_tokens":1000,"compressed_tokens":200,"retrieved":false,"guard_failed":false}
{"tool_name":"grep","content_type":"tool_output","repo":"demo","original_tokens":900,"compressed_tokens":150,"retrieved":false,"guard_failed":false}
{"tool_name":"read_file","content_type":"tool_output","repo":"demo","original_tokens":1000,"compressed_tokens":700,"retrieved":true,"guard_failed":false}
EOF

cutctx policies train --events /tmp/events.jsonl --db /tmp/policies.db
cutctx policies show --db /tmp/policies.db
```

Look for:

- CLI output showing learned policy rows.
- `grep / tool_output` leaning more aggressive than `read_file / tool_output`.
- With the default policy DB, `/stats` exposes `intelligence.policies` counts
  and distributions.
- Overview learned-policies panel shows active policy visibility.

## Step 4: Show Context Policy Enforcement

WS4 policy enforcement is opt-in through `CUTCTX_CONTEXT_POLICY`; default proxy
behavior remains unchanged.

Create policy file:

```yaml
# /tmp/context-policy.yaml
version: "1"
redact_rules:
  - name: mask_api_keys
    pattern: "sk-[A-Za-z0-9]+"
    replacement: "sk-***"
    scope: content
block_rules:
  - name: block_passwd_files
    pattern: "/etc/passwd"
    reason: "Password file access blocked by security policy"
```

Restart the proxy with policy enforcement and replay alpha enabled:

```bash
CUTCTX_CONTEXT_POLICY=/tmp/context-policy.yaml \
CUTCTX_REPLAY=1 \
cutctx proxy \
  --enable-learned-policies \
  --port 8080
```

Look for:

- Requests mentioning `sk-abc123` are redacted to `sk-***` before upstream
  forwarding.
- Requests mentioning `/etc/passwd` return a 403 `context_policy_blocked`
  response.

## Step 5: Show Org-Scoped Memory Export

```bash
cutctx memory export --output /tmp/all-memories.json
cutctx memory export --workspace-id demo-ws --output /tmp/ws-memories.json
cutctx memory export --project-id demo-proj --output /tmp/proj-memories.json
```

Look for:

- Exported memory objects include `workspace_id` and `project_id` when
  available.
- Filtered exports only include matching memories.

## Step 6: Show Current Audit Signals

```bash
curl -s http://localhost:8080/stats | python3 -m json.tool | grep -A 10 '"policies"'
cutctx report agent-context --format markdown --days 7
```

Look for:

- `/stats` returns `intelligence.policies` counts and distributions.
- Agent Context Report summarizes savings attribution, governance posture, and
  assurance/replay readiness.

## Step 7: Show Session Replay Alpha

After sending a blocked or redacted request with
`x-cutctx-session-id: demo-session`, open dashboard Replay or call:

```bash
curl -s http://localhost:8080/v1/sessions/demo-session/replay \
  -H "x-cutctx-admin-key: $CUTCTX_ADMIN_KEY" \
  | python3 -m json.tool
```

Look for:

- Policy block/redaction events with matched rules.
- Honest alpha scope: policy decisions are replayed now; compressed,
  retrieved, injected, and CCR lifecycle replay remains follow-up work.

## Close With Buyer Value

- Cost control: savings attribution separates direct compression, provider
  cache, and semantic cache.
- Governance path: WS4 policy enforcement is live in proxy routes with policy
  replay alpha.
- Data portability: WS5 org-scoped memory export is available.
- Roadmap pull: WS7 assurance and broader WS8 replay remain the next enterprise
  proof surfaces.
