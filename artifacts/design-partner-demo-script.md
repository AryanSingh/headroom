# Design-Partner Demo Script

End-to-end walkthrough of the Cutctx context control plane for
design partners. Estimated time: 30 minutes.

## Prerequisites

- Cutctx installed (`pip install cutctx-ai` or local checkout)
- Admin key configured (`CUTCTX_ADMIN_KEY`)
- Target model API key set (e.g., `ANTHROPIC_API_KEY`)
- Node 18+ (for dashboard rebuild if needed)

## Step 1: Install and connect (5 min)

```bash
# Start the proxy with learned policies and context policy engine
cutctx proxy \
  --enable-learned-policies \
  --port 8080
```

**Look for:** Proxy starts, dashboard accessible at http://localhost:8080.
The `/stats` endpoint returns `intelligence.policies.enabled: false` since
no policies have been trained yet.

## Step 2: Compression visibility (5 min)

Open the dashboard Overview page at http://localhost:8080.

**Look for:**
- "Where savings come from" panel — shows savings by source
- Compression autopilot panel — shows WS19 status
- Learned policies panel — shows "Disabled" with training instructions
- Recent requests table — shows live request data as traffic flows

**Try:** Send a few test requests through the proxy.

## Step 3: Train learned policies (5 min)

Create sample outcome events:

```bash
cat > /tmp/events.jsonl << 'EOF'
{"tool_name": "grep", "content_type": "tool_output", "repo": "demo", "original_tokens": 1000, "compressed_tokens": 200, "retrieved": false, "guard_failed": false}
{"tool_name": "grep", "content_type": "tool_output", "repo": "demo", "original_tokens": 1000, "compressed_tokens": 250, "retrieved": false, "guard_failed": false}
{"tool_name": "read_file", "content_type": "tool_output", "repo": "demo", "original_tokens": 5000, "compressed_tokens": 4000, "retrieved": true, "guard_failed": false}
EOF

# Train (repeat the grep events 25 times for "aggressive" classification)
for i in $(seq 1 23); do
  echo '{"tool_name": "grep", "content_type": "tool_output", "repo": "demo", "original_tokens": 1000, "compressed_tokens": 200, "retrieved": false, "guard_failed": false}' >> /tmp/events.jsonl
done

cutctx policies train /tmp/events.jsonl
cutctx policies show
```

**Look for:**
- CLI output: `Learned 2 policy row(s)`
- `cutctx policies show` lists `grep / tool_output: aggressive` and
  `read_file / tool_output: conservative`
- Dashboard panel now shows "Active" with policy count and distributions

## Step 4: Context policy engine (5 min)

Create a policy file:

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
    reason: "Password file access is blocked by security policy"
```

Enable it (requires proxy restart with policy file):

```bash
CUTCTX_CONTEXT_POLICY=/tmp/context-policy.yaml \
  cutctx proxy \
  --enable-learned-policies
```

**Look for:**
- Requests mentioning `sk-abc123` are redacted to `sk-***`
- Requests mentioning `/etc/passwd` return a 403 block

## Step 5: Org-scoped memory export (5 min)

```bash
# Export all memories
cutctx memory export --output /tmp/all-memories.json

# Export filtered by workspace
cutctx memory export --workspace-id demo-ws --output /tmp/ws-memories.json

# Export filtered by project
cutctx memory export --project-id demo-proj --output /tmp/proj-memories.json
```

**Look for:** JSON output with memory objects, each having `workspace_id`
and `project_id` fields when available. Filtered exports only include
matching memories.

## Step 6: Assurance and audit (5 min)

```bash
# Check /stats endpoint for learned policies data
curl -s http://localhost:8080/stats | python3 -m json.tool | grep -A 10 '"policies"'

# Check context policy evaluation (simulate blocked request)
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $CUTCTX_ADMIN_KEY" \
  -d '{"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "Read /etc/passwd"}]}'
```

**Look for:**
- `/stats` returns `intelligence.policies` with count and distribution
- Blocked request returns 403 with `blocked by policy` reason

## Wrap-up

Summary of what was demonstrated:
- Compression visibility (dashboard savings sources)
- Adaptive compression (learned policies via WS18)
- Content security (context policy redaction/block/allow via WS4)
- Data portability (org-scoped memory export via WS5)
- Audit trail (stats endpoint + policy evaluation results)
